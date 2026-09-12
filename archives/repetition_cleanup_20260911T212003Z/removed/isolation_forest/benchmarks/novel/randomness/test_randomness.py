"""Offline integration tests: real preparation and SDK serialization, mocked HTTP."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
import randomness_check as study


PREDICTION = {"category": "free text", "cause": "example cause", "action": "example action",
              "confidence": 0.5, "supporting_historical_runs": [], "reasoning_summary": "test"}


def response(text=None, status=200):
    if status != 200:
        return httpx.Response(status, json={"error": {"message": "fixture error", "type": "server_error"}})
    return httpx.Response(200, json={
        "id": "resp_offline_fixture", "object": "response", "created_at": 0,
        "model": "gpt-5.6-sol", "status": "completed", "error": None,
        "output": [{"id": "msg_fixture", "type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": text if text is not None else json.dumps(PREDICTION),
                                 "annotations": []}]}],
    })


class RandomnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = "gpt-5.6-sol"
        cls.reference = study.load_reference(cls.model)
        cls.cases = {run: study.load_case(run, cls.reference) for run in study.novel.EXPECTED_TARGETS}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="offline_test_", dir=study.HERE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test-not-a-real-key"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.case = self.cases[1640]

    def test_exact_original_adapter_payload_and_no_sampling_override(self):
        result = study.invoke(self.case, self.model, self.root / "trial_1")
        seen = {}

        class Capture:
            @property
            def responses(self):
                return self

            def create(self, **kwargs):
                seen.update(kwargs)
                raise study.CapturedWithoutNetwork()

        with patch("openai.OpenAI", return_value=Capture()):
            with self.assertRaises(study.CapturedWithoutNetwork):
                study.novel.openai_call(self.case.system_prompt, self.case.user_prompt, self.model)
        payload = study.read_json(self.root / "trial_1/request_payload.json")
        self.assertEqual(payload, seen)
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["network_attempts"], 0)
        self.assertEqual(result["input_sha256"], study.digest(seen))
        self.assertTrue(all(not value["sent"] for value in result["sampling_parameters"].values()))

    def test_thirty_fresh_calls_no_cached_responses_and_identical_inputs(self):
        seen = []

        def handler(request):
            seen.append(json.loads(request.content))
            payload = {**PREDICTION, "cause": f"fixture cause {len(seen)}"}
            return response(json.dumps(payload))

        original = study.invoke

        def invoke(*args, **kwargs):
            if kwargs.get("execute"):
                kwargs["transport"] = httpx.MockTransport(handler)
            return original(*args, **kwargs)

        prepared = []

        def prepare(run, reference):
            prepared.append(run)
            return copy.deepcopy(self.cases[run])

        with patch.object(study, "load_case", side_effect=prepare), patch.object(study, "invoke", side_effect=invoke):
            status = study.run_study(self.model, self.root / "study", execute=True)
        self.assertEqual(status, 0)
        self.assertEqual(len(seen), 30)
        self.assertEqual(len(prepared), 36)  # Six preflight builds plus thirty trial rebuilds.
        results = study.read_json(self.root / "study/results.json")
        self.assertEqual(len({r["prediction"]["cause"] for r in results["trials"]}), 30)
        for run in results["runs"]:
            self.assertTrue(run["all_input_hashes_match"])
            self.assertEqual(run["n_unique_exact_diagnoses"], 5)
            self.assertEqual(run["dominant_count"], "")
        for trial in results["trials"]:
            base = self.root / "study" / f"run{trial['run']}" / f"trial_{trial['trial']}"
            self.assertEqual(study.read_json(base / "request_payload.json"), seen[(study.novel.EXPECTED_TARGETS.index(trial['run']) * 5) + trial['trial'] - 1])
            self.assertTrue((base / "raw_response_body.bin").is_file())
            self.assertTrue((base / "parsed_response.json").is_file())

    def test_input_change_stops_before_network(self):
        expected = study.invoke(self.case, self.model, self.root / "preflight")
        expected["input_sha256"] = "wrong"
        seen = []
        result = study.invoke(self.case, self.model, self.root / "trial_1", execute=True,
                              expected=expected, transport=httpx.MockTransport(lambda req: seen.append(req)))
        self.assertEqual(result["status"], "input_changed")
        self.assertEqual(result["network_attempts"], 0)
        self.assertEqual(seen, [])

    def test_http_error_is_saved_without_retry(self):
        calls = []

        def handler(request):
            calls.append(request)
            return response(status=500)

        result = study.invoke(self.case, self.model, self.root / "trial_1", execute=True,
                              transport=httpx.MockTransport(handler))
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["http_status"], 500)
        self.assertTrue((self.root / "trial_1/raw_response_body.bin").is_file())

    def test_parse_failure_retains_complete_raw_response(self):
        result = study.invoke(self.case, self.model, self.root / "trial_1", execute=True,
                              transport=httpx.MockTransport(lambda req: response("not JSON")))
        self.assertEqual(result["status"], "failed")
        self.assertEqual((self.root / "trial_1/output_text.txt").read_text(), "not JSON")
        self.assertTrue((self.root / "trial_1/raw_response.json").is_file())
        self.assertTrue((self.root / "trial_1/sdk_response.json").is_file())

    def test_target_and_family_leakage_is_rejected(self):
        case = copy.deepcopy(self.case)
        case.user_prompt += "\ncase_run_1640"
        with self.assertRaises(AssertionError):
            study.novel.assert_case_safe(case)
        reference = copy.deepcopy(self.reference)
        reference["prompt_sha256"]["1640"] = "wrong"
        with self.assertRaisesRegex(ValueError, "differs from the original"):
            study.load_case(1640, reference)

    def test_no_overwrite_and_no_model_or_trial_drift(self):
        path = self.root / "trial_1"
        study.invoke(self.case, self.model, path)
        original = (path / "request_body.json").read_bytes()
        with self.assertRaises(FileExistsError):
            study.invoke(self.case, self.model, path)
        self.assertEqual((path / "request_body.json").read_bytes(), original)
        with self.assertRaises(ValueError):
            study.load_reference("different-model")
        with self.assertRaises(ValueError):
            study.run_study(self.model, self.root / "bad", trials=4)

    def test_exact_not_semantic_comparison_and_markdown_escaping(self):
        records = [{"run": 1640, "trial": i, "status": "completed", "input_sha256": "same",
                    "request_matches_reference": True, "prediction": {**PREDICTION,
                    "cause": "trigger mask mismatch" if i < 5 else "trigger-mask mismatch",
                    "action": "check | mask\nthen <inspect>"}} for i in range(1, 6)]
        study.summarize(self.root, records, 5, self.model)
        rows = study.read_json(self.root / "results.json")["runs"]
        row = next(r for r in rows if r["run"] == 1640)
        self.assertEqual(row["n_unique_exact_diagnoses"], 2)
        self.assertEqual(row["consistency_rate"], "")
        report = (self.root / "randomness_summary.md").read_text()
        self.assertIn("&#124;", report)
        self.assertIn("&lt;inspect&gt;", report)


if __name__ == "__main__":
    unittest.main()
