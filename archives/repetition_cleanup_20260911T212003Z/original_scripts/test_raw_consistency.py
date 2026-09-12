"""Offline regression tests. Synthetic outputs are never real study results."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from common import canonical, write, read, at_path
from prepare_inputs import metric_stats, pooled, ranges, raw_summary, anomaly_summary
from run_study import Diagnosis, invoke, validate_citations, token_check, compare


def fake_prediction():
    return {'category': 'SYNTHETIC TEST ONLY', 'cause': 'Not a detector diagnosis',
        'action': 'No real action recommended', 'confidence': 0., 'supporting_historical_runs': [],
        'reasoning_summary': 'Synthetic fixture for offline rendering.',
        'semantic_description': {'component': 'test', 'failure_mechanism': 'test', 'action_intent': 'test'},
        'signatures': [{'signature_id': 'S1', 'observation': 'Synthetic fixture cites a supplied mean.',
            'role': 'supports', 'citations': [{'evidence_id': 'R-000-00', 'field': 'mean', 'value_json': '2.5'}],
            'cause_link': 'Fixture only; does not support a real cause.',
            'action_link': 'Verify rendering; not a detector action.'}], 'missing_information': []}


class Tests(unittest.TestCase):
    def test_stats_missing_zero_and_pooling(self):
        a = metric_stats(np.array([[0., np.nan], [2., np.inf]]))
        b = metric_stats(np.array([[10., 3.]]))
        p = pooled(np.stack([a[0], b[0]]))
        self.assertEqual(p['n'], 3)
        self.assertEqual(p['mean'], 4)
        self.assertAlmostEqual(p['std_population'], np.std([0,2,10]), places=5)
        self.assertEqual(a[1, 0], 0)
        self.assertTrue(np.isnan(a[1, 1]))
        self.assertEqual(a[0, 10], 1)

    def test_ranges_numeric(self):
        self.assertEqual(ranges([10, 2, 1, 4]), [[1,2], [4,4], [10,10]])

    def test_citation_checks(self):
        prediction = fake_prediction()
        record = {'id': 'R-000-00', 'mean': 2.5}
        self.assertTrue(validate_citations(prediction, [record], [])['all_references_valid'])
        prediction['signatures'][0]['citations'][0]['value_json'] = '9'
        self.assertFalse(validate_citations(prediction, [record], [])['all_references_valid'])
        prediction['signatures'][0]['citations'][0]['evidence_id'] = 'R-999-00'
        self.assertFalse(validate_citations(prediction, [record], [])['all_references_valid'])
        prediction['signatures'] = []
        self.assertFalse(validate_citations(prediction, [record], [])['all_references_valid'])

    def test_token_guard(self):
        self.assertFalse(token_check({'input': 'x'*100}, 20)['within_conservative_guard'])

    def test_render_distributions_presence_and_links(self):
        from render_signatures import plot_record, save_text_figure
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            header={'histogram_edges_by_metric':{'x':[0,1,2]}, 'time_bin_subrun_ranges':[[1,1],[2,2]],
                    'quantile_probabilities':[0,.5,1]}
            plot_record({'kind':'raw_metric','metric':'x','histogram_counts':[2,2],
                         'time_bin_mean':[None,1.]},header,d/'metric.png','SYNTHETIC TEST',True)
            plot_record({'kind':'raw_presence','occupancy_quantiles':[0,.5,1],
                         'time_bin_occupancy':[0,1],'present_subruns':1,'total_subruns':2},
                        header,d/'presence.png','SYNTHETIC TEST',False)
            save_text_figure(d/'links.png','SYNTHETIC TEST',[('Cause link','test '*200)],'Fixture only')
            self.assertTrue(all((d/p).stat().st_size>1000 for p in ['metric.png','presence.png','links.png']))

    def test_dry_run_no_network(self):
        payload = {'model': 'gpt-5.6-sol', 'instructions': 'test', 'input': 'test'}
        with tempfile.TemporaryDirectory() as tmp:
            with patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
                a = invoke(payload, Path(tmp)/'one')
                b = invoke(payload, Path(tmp)/'two')
            self.assertEqual(a['status'], 'dry_run')
            self.assertEqual(a['network_attempts'], 0)
            self.assertEqual(a['request_body_sha256'], b['request_body_sha256'])

    def test_mock_response_saved_no_retry(self):
        import httpx
        seen = []
        def respond(request):
            seen.append(1)
            return httpx.Response(200, json={'id':'resp_mock', 'object':'response', 'created_at':0,
                'status':'completed', 'model':'gpt-5.6-sol', 'output':[{'id':'msg_mock','type':'message',
                'role':'assistant','status':'completed','content':[{'type':'output_text','text':canonical(fake_prediction()),'annotations':[]}]}]})
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'OPENAI_API_KEY': 'offline-placeholder'}):
            result = invoke({'model': 'gpt-5.6-sol', 'input':'test'}, Path(tmp)/'trial', True, httpx.MockTransport(respond))
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(len(seen), 1)
            self.assertTrue((Path(tmp)/'trial/raw_response_body.bin').exists())
        seen.clear()
        def fail(request):
            seen.append(1)
            return httpx.Response(429, json={'error': {'message':'offline test', 'type':'rate_limit'}})
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'OPENAI_API_KEY':'offline-placeholder'}):
            result = invoke({'model':'gpt-5.6-sol','input':'test'}, Path(tmp)/'trial', True, httpx.MockTransport(fail))
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(len(seen), 1)

    def test_all_files_histograms_and_absence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root/'1600'
            folder.mkdir()
            base = {'event_id':['e0','e1'], 'channel':[0,0], 'layer':[0,0], 'supermodule':[0,0],
                    'row':[0,0], 'column':[0,0], 'nPulses':[0,2], 'TDC':[1,2]}
            pd.DataFrame(base).to_csv(folder/'Digitizer_run1640_subrun1.csv', index=False)
            base['nPulses'] = [3,5]
            pd.DataFrame(base).to_csv(folder/'Digitizer_run1640_subrun10.csv', index=False)
            out = root/'out'; out.mkdir()
            records, meta = raw_summary(1640, out, root)
            index = {r['id']:r for r in records}
            self.assertEqual(meta['file_count'],2)
            self.assertEqual(index['R-000-00']['mean'],2.5)
            self.assertEqual(sum(index['R-000-00']['histogram_counts']),4)
            self.assertEqual(index['P-001']['present_subruns'],0)
            self.assertEqual(index['P-001']['occupancy_quantiles'],[0]*7)
            self.assertIsNone(index['R-001-00']['mean'])
            self.assertEqual(meta['time_bin_subrun_ranges'],[[1,1],[10,10]])

    def test_full_anomaly_no_top_n(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'anomaly.csv'
            data = [{'filename':'Digitizer_run1640_subrun1.csv','channel':c,'anomalous':True,
                     'method':'statistical','max_z':c,'if_score':-.5,'triggered_features':'a;b'} for c in range(12)]
            pd.DataFrame(data).to_csv(path,index=False)
            records = anomaly_summary(path,1640,[1])
            self.assertEqual(len(records),13)
            self.assertEqual(records[-1]['anomalous_rows'],12)
            self.assertEqual(records[0]['triggered_feature_counts'],{'a':1,'b':1})

    def test_semantics_not_string_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            study=Path(tmp)
            write(study/'study_config.json',{'runs':[1640],'trials':3})
            for t,text in enumerate(['PMT base failed','Failure of PMT base','PMT base fault'],1):
                folder=study/'run1640'/f'trial_{t}'; folder.mkdir(parents=True)
                prediction=fake_prediction(); prediction['cause']=text
                write(folder/'diagnosis.json',prediction)
                write(folder/'metadata.json',{'status':'completed','input_sha256':'same','request_body_sha256':'same'})
            r=compare(study)
            self.assertEqual(r[0]['fields']['cause']['semantic_consistency'],'pending_human_review')
            review=read(study/'semantic_review.json')
            review['runs']['1640'].update(reviewer='test reviewer',rationale='Fixture synonyms',cause_groups=['base','base','base'])
            write(study/'semantic_review.json',review)
            self.assertEqual(compare(study)[0]['fields']['cause']['semantic_consistency'],'consistent')


if __name__ == '__main__': unittest.main()
