"""No-network tests for the known-failure recognition benchmark."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = REPO_ROOT / "benchmarks" / "recognition"
sys.path.insert(0, str(BENCHMARK_DIR))

import recognition_test as bench  # noqa: E402


VALID_PAYLOAD = {
    "category": "daq_auto_restart",
    "cause": "unknown",
    "action": "unknown",
    "recovery": "normal operation resumes",
    "confidence": 0.8,
    "supporting_historical_runs": [1604],
    "reasoning_summary": "The detector evidence resembles the visible historical case.",
}


class RecognitionBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = bench.load_manifest()
        cls.cases, cls.kb_path, cls.kb_hash = bench.prepare_all_cases(cls.manifest)
        cls.by_run = {case.target_run: case for case in cls.cases}

    def test_01_manifest_contains_exactly_nine_targets(self) -> None:
        self.assertEqual([item["run"] for item in self.manifest["targets"]], bench.EXPECTED_TARGETS)
        self.assertEqual(len(self.manifest["targets"]), 9)

    def test_02_families_and_peer_sets_are_exact(self) -> None:
        actual = {item["run"]: item["expected_peers"] for item in self.manifest["targets"]}
        self.assertEqual(actual, bench.EXPECTED_PEERS)

    def test_03_bad_data_runs_are_excluded_from_every_context(self) -> None:
        for case in self.cases:
            runs = {bench.singleton_run(entry) for entry in case.filtered_kb}
            self.assertTrue(runs.isdisjoint(bench.EXPECTED_BAD_DATA), case.target_run)

    def test_04_target_entry_is_removed_from_every_context(self) -> None:
        for case in self.cases:
            runs = {bench.singleton_run(entry) for entry in case.filtered_kb}
            self.assertNotIn(case.target_run, runs)

    def test_05_target_number_is_masked_from_final_prompt(self) -> None:
        for case in self.cases:
            self.assertIsNone(bench.run_token_pattern(case.target_run).search(case.serialized_prompt))

    def test_06_expected_same_family_peers_are_visible(self) -> None:
        for case in self.cases:
            visible = [peer for peer in case.expected_peers if bench.run_token_pattern(peer).search(case.serialized_prompt)]
            self.assertEqual(visible, case.expected_peers)

    def test_07_singletons_and_distractors_never_become_targets(self) -> None:
        non_targets = set(self.manifest["non_target_runs"])
        targets = {item["run"] for item in self.manifest["targets"]}
        self.assertTrue(non_targets.isdisjoint(targets))
        self.assertTrue({1605, 1620, 1747}.issubset({bench.singleton_run(e) for e in self.cases[0].filtered_kb}))

    def test_08_hidden_ground_truth_text_is_not_appended_to_prompt(self) -> None:
        entries = bench.load_kb(self.kb_path)
        sentinel = "GROUND_TRUTH_ONLY_SENTINEL_91f83"
        for entry in entries:
            if entry["run"] == 1500:
                entry["cause"] = sentinel
                entry["action"] = sentinel
                entry["recovery"] = sentinel
        spec = next(item for item in self.manifest["targets"] if item["run"] == 1500)
        case = bench.prepare_case(
            self.manifest,
            spec,
            entries,
            snapshot_loader=lambda _path, run: f"snapshot source run {run}",
        )
        self.assertNotIn(sentinel, case.serialized_prompt)
        self.assertEqual(case.ground_truth["cause"], sentinel)

    def test_09_valid_and_fenced_json_response_parsing(self) -> None:
        plain = bench.parse_response_text(json.dumps(VALID_PAYLOAD))
        fenced = bench.parse_response_text("```json\n" + json.dumps(VALID_PAYLOAD) + "\n```")
        self.assertEqual(plain.category, "daq_auto_restart")
        self.assertEqual(fenced.supporting_historical_runs, [1604])

    def test_10_malformed_output_is_a_parsing_failure(self) -> None:
        with self.assertRaises(bench.ResponseParsingError):
            bench.parse_response_text("not JSON")
        invalid = dict(VALID_PAYLOAD, confidence=2.0)
        with self.assertRaises(bench.ResponseParsingError):
            bench.parse_response_text(json.dumps(invalid))

    def test_11_category_normalization_and_alias_scoring(self) -> None:
        self.assertEqual(bench.normalize_category(" Broken-PMT Base "), "broken_pmt_base")
        self.assertTrue(bench.category_is_correct("BROKEN PMT-BASE", ["broken_PMT_base"]))
        self.assertFalse(bench.category_is_correct("dead_channels", ["broken_PMT_base"]))

    def test_12_unknown_ground_truth_fields_are_not_scorable(self) -> None:
        self.assertEqual(bench.ground_truth_field_status("unknown"), "not_scorable")
        self.assertEqual(bench.ground_truth_field_status(" Unknown "), "not_scorable")
        self.assertEqual(bench.ground_truth_field_status("check cables"), "ground_truth_available")

    def make_completed_record(self, case: bench.PreparedCase, category: str | None = None) -> dict:
        payload = dict(VALID_PAYLOAD)
        payload["category"] = category or case.canonical_category
        payload["supporting_historical_runs"] = case.expected_peers
        parsed = bench.RecognitionResponse.model_validate(payload)
        return bench.completed_record(case, parsed, {"model_id": "mock-model"})

    def test_13_report_generation_includes_details_and_incomplete_status(self) -> None:
        records = [self.make_completed_record(self.cases[0])]
        report = bench.render_report(records)
        self.assertIn("1/1 completed (incomplete)", report)
        self.assertIn("Ground truth", report)
        self.assertIn("Prediction", report)
        self.assertIn("not_scorable", report)

    def test_14_luna_sol_comparison_contains_all_nine_targets(self) -> None:
        luna_records = [self.make_completed_record(case) for case in self.cases]
        sol_records = [self.make_completed_record(case, "wrong_category") for case in self.cases]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            luna_dir, sol_dir = root / "luna", root / "sol"
            luna_dir.mkdir()
            sol_dir.mkdir()
            bench.write_json(luna_dir / "run_config.json", {"model_id": "mock-luna"})
            bench.write_json(sol_dir / "run_config.json", {"model_id": "mock-sol"})
            bench.write_json(luna_dir / "results.json", {"tests": luna_records})
            bench.write_json(sol_dir / "results.json", {"tests": sol_records})
            destination = bench.compare_results(luna_dir, sol_dir, root / "comparison.md")
            text = destination.read_text(encoding="utf-8")
            self.assertIn("9/9", text)
            for run in bench.EXPECTED_TARGETS:
                self.assertIn(f"### Target {run}", text)

    def test_15_resume_skips_successfully_completed_calls(self) -> None:
        case = self.cases[0]
        call_count = 0

        def fake_call(_system: str, _user: str, _model: str):
            nonlocal call_count
            call_count += 1
            return {"usage": {"input_tokens": 1, "output_tokens": 1}}, bench.RecognitionResponse.model_validate(VALID_PAYLOAD)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            bench, "prepare_all_cases", return_value=([case], self.kb_path, self.kb_hash)
        ):
            result_dir = Path(tmp) / "result"
            bench.run_benchmark("mock-model", "luna", result_dir, api_call=fake_call, sleep_fn=lambda _: None)
            bench.run_benchmark("mock-model", "luna", result_dir, api_call=fake_call, sleep_fn=lambda _: None)
            self.assertEqual(call_count, 1)

    def test_16_api_key_is_never_written_to_outputs(self) -> None:
        case = self.cases[0]
        secret = "sk-test-DO-NOT-WRITE-4a8f"

        def fake_call(_system: str, _user: str, _model: str):
            return {"id": "mock", "usage": {}}, bench.RecognitionResponse.model_validate(VALID_PAYLOAD)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            bench, "prepare_all_cases", return_value=([case], self.kb_path, self.kb_hash)
        ), mock.patch.dict(os.environ, {"OPENAI_API_KEY": secret}):
            result_dir = Path(tmp) / "result"
            bench.run_benchmark("mock-model", "luna", result_dir, api_call=fake_call, sleep_fn=lambda _: None)
            combined = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in result_dir.rglob("*")
                if path.is_file()
            )
            self.assertNotIn(secret, combined)

    def test_17_failed_api_calls_are_not_scored_as_wrong(self) -> None:
        case = self.cases[0]

        def failed_call(_system: str, _user: str, _model: str):
            raise ConnectionError("mock network failure")

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            bench, "prepare_all_cases", return_value=([case], self.kb_path, self.kb_hash)
        ):
            result_dir = Path(tmp) / "result"
            bench.run_benchmark("mock-model", None, result_dir, api_call=failed_call, sleep_fn=lambda _: None)
            payload = json.loads((result_dir / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["tests"][0]["status"], "api_failed")
            self.assertEqual(payload["summary"]["completed"], 0)

    def test_18_openai_adapter_uses_strict_structured_output_without_network(self) -> None:
        fake_response = SimpleNamespace(output_text=json.dumps(VALID_PAYLOAD))
        fake_client = mock.Mock()
        fake_client.responses.create.return_value = fake_response
        with mock.patch("openai.OpenAI", return_value=fake_client):
            raw, parsed = bench.openai_call("system", "user", "mock-model")
        self.assertIs(raw, fake_response)
        self.assertEqual(parsed.category, "daq_auto_restart")
        kwargs = fake_client.responses.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "mock-model")
        self.assertEqual(kwargs["instructions"], "system")
        self.assertEqual(kwargs["input"], "user")
        self.assertEqual(kwargs["text"]["format"]["type"], "json_schema")
        self.assertTrue(kwargs["text"]["format"]["strict"])

    def test_19_filtered_kb_preserves_original_order_and_wording(self) -> None:
        original = bench.load_kb(self.kb_path)
        for case in self.cases:
            expected = [
                entry
                for entry in original
                if bench.singleton_run(entry) != case.target_run
                and bench.singleton_run(entry) not in bench.EXPECTED_BAD_DATA
            ]
            self.assertEqual(case.filtered_kb, expected)


if __name__ == "__main__":
    unittest.main()
