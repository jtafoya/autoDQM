"""Recovery-state safety tests using temporary synthetic fixtures only."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from common import write, read, sha, canonical
from test_raw_consistency import fake_prediction
from resume_study import classify, archive_failure, execute


class ResumeTests(unittest.TestCase):
    def fixture(self, root, status='failed', http=520):
        d=root/'run1640'/'trial_2'; d.mkdir(parents=True)
        write(d/'metadata.json',{'status':status,'http_status':http})
        (d/'request_body.json').write_text('{"input":"fixture"}')
        (d/'raw_response_body.bin').write_bytes(b'original gateway failure')
        return d

    def test_missing(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(classify(Path(t)/'missing'),'not_started')

    def test_transport_archive_preserves_original_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); d=self.fixture(root)
            expected={p.name:sha(p) for p in d.iterdir()}
            result=archive_failure(d,root/'recovery')
            self.assertFalse(d.exists())
            self.assertEqual(result['sha256'],expected)
            self.assertEqual({p.name:sha(p) for p in Path(result['archived']).iterdir()},expected)

    def test_completed_never_archived(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); d=self.fixture(root,'completed',200)
            pred=fake_prediction()
            write(d/'diagnosis.json',pred)
            write(d/'raw_response.json',{'status':'completed','output':[{'content':[{'type':'output_text','text':canonical(pred)}]}]})
            write(d/'signature_records.json',{})
            self.assertEqual(classify(d),'completed')
            with self.assertRaises(ValueError): archive_failure(d,root/'recovery')
            self.assertTrue((d/'diagnosis.json').exists())

    def test_unknown_partial_and_auth_not_retried(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); d=self.fixture(root,http=401)
            with self.assertRaises(ValueError): classify(d)
            write(d/'metadata.json',{'status':'preparing'})
            with self.assertRaises(ValueError): classify(d)

    def test_existing_output_not_replaced(self):
        with tempfile.TemporaryDirectory() as t:
            d=self.fixture(Path(t))
            (d/'output_text.txt').write_text('some output exists')
            with self.assertRaises(ValueError): classify(d)

    def test_execute_stops_after_one_new_failure_preserving_audit(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); d=self.fixture(root)
            config={'inputs':str(root/'inputs')}
            tasks=[{'run':1640,'trial':2,'state':'retry_transport_failure'}]
            def fail(payload,directory,**kwargs):
                directory.mkdir()
                write(directory/'metadata.json',{'status':'failed','http_status':520})
                return {'status':'failed'}
            with patch.dict('os.environ',{'OPENAI_API_KEY':'offline-test'}), \
                 patch('resume_study.plan',return_value=(config,{1640:{'instructions':'test','input':'test'}},{1640:'wire'},tasks)), \
                 patch('resume_study.invoke',side_effect=fail) as call, patch('resume_study.compare'):
                with self.assertRaises(RuntimeError): execute(root)
                self.assertEqual(call.call_count,1)
            archived=list(root.glob('recovery_attempts/*/run1640/trial_2/raw_response_body.bin'))
            self.assertEqual(len(archived),1)
            self.assertEqual(archived[0].read_bytes(),b'original gateway failure')
            self.assertEqual(read(d/'metadata.json')['status'],'failed')

    def test_all_completed_causes_no_new_calls(self):
        with tempfile.TemporaryDirectory() as t:
            with patch.dict('os.environ',{'OPENAI_API_KEY':'offline-test'}), \
                 patch('resume_study.plan',return_value=({}, {}, {}, [{'state':'completed'}])), \
                 patch('resume_study.invoke') as call:
                execute(Path(t))
                call.assert_not_called()


if __name__=='__main__': unittest.main()
