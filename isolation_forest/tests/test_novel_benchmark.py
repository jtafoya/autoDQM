"""No-network tests for the novel-failure generation benchmark."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = REPO_ROOT / "benchmarks" / "novel"
sys.path.insert(0, str(BENCHMARK_DIR))

import novel_test as bench  # noqa: E402


VALID_PAYLOAD = {
    "category": "unknown_hardware_fault",
    "cause": "The supplied evidence is insufficient for a unique cause.",
    "action": "Inspect the channels identified by the anomaly summary.",
    "confidence": 0.35,
    "supporting_historical_runs": [],
    "reasoning_summary": "The anomaly has no close visible historical-family match.",
}


class NovelBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = bench.load_manifest()
        cls.cases, cls.kb_path, cls.kb_hash = bench.prepare_all_cases(cls.manifest)
        cls.by_run = {case.target_run: case for case in cls.cases}

    def test_01_exactly_six_targets(self) -> None:
        self.assertEqual(list(self.manifest["targets"]), bench.EXPECTED_TARGETS)
        self.assertEqual(len(self.cases), 6)

    def test_02_explicit_exclusion_sets_are_exact(self) -> None:
        actual = {run: spec["exclude_runs"] for run, spec in self.manifest["targets"].items()}
        self.assertEqual(actual, bench.EXPECTED_EXCLUSIONS)

    def test_03_1640_excludes_1642(self) -> None:
        self.assertEqual(self.by_run[1640].exclude_runs, [1640, 1642])

    def test_04_1642_excludes_1640(self) -> None:
        self.assertEqual(self.by_run[1642].exclude_runs, [1642, 1640])

    def test_05_1702_excludes_1703(self) -> None:
        self.assertEqual(self.by_run[1702].exclude_runs, [1702, 1703])

    def test_06_1703_excludes_1702(self) -> None:
        self.assertEqual(self.by_run[1703].exclude_runs, [1703, 1702])

    def test_07_singleton_exclusions_remove_only_themselves(self) -> None:
        self.assertEqual(self.by_run[1620].exclude_runs, [1620])
        self.assertEqual(self.by_run[2126].exclude_runs, [2126])

    def test_08_target_and_family_entries_are_absent(self) -> None:
        for case in self.cases:
            visible = {bench.recognition.singleton_run(entry) for entry in case.filtered_kb}
            self.assertTrue(set(case.exclude_runs).isdisjoint(visible), case.target_run)

    def test_09_no_unrequested_entries_are_removed(self) -> None:
        original = bench.recognition.load_kb(self.kb_path)
        original_runs = [bench.recognition.singleton_run(entry) for entry in original]
        for case in self.cases:
            expected = [run for run in original_runs if run not in case.exclude_runs]
            self.assertEqual(case.visible_historical_runs, expected)

    def test_10_target_run_id_is_masked_as_case_target(self) -> None:
        for case in self.cases:
            self.assertIn("CASE_TARGET", case.serialized_prompt)
            self.assertIsNone(
                bench.recognition.run_token_pattern(case.target_run).search(case.serialized_prompt)
            )

    def test_11_target_cause_action_and_recovery_are_absent(self) -> None:
        for case in self.cases:
            self.assertTrue(all(case.audit["target_ground_truth_fields_absent"].values()))

    def test_12_target_paths_and_source_metadata_are_not_visible(self) -> None:
        for case in self.cases:
            self.assertTrue(case.audit["target_source_path_and_filename_absent"])
            self.assertNotIn(case.target_evidence_source, case.serialized_prompt)
            self.assertNotIn("anomaly_log.csv", case.serialized_prompt)

    def test_13_no_direct_detector_or_elog_context_is_added(self) -> None:
        for case in self.cases:
            self.assertEqual(
                set(case.audit["direct_context_not_added"]), set(bench.DIRECT_CONTEXT_COMPONENTS)
            )
            self.assertTrue(all(case.audit["direct_context_not_added"].values()))
            self.assertTrue(case.audit["prompt_only_allowlisted_components"])

    def test_14_exact_prompt_serialization_passes_full_audit(self) -> None:
        for case in self.cases:
            bench.assert_case_safe(case)
            self.assertEqual(case.audit["prompt_sha256"], case.prompt_sha256)

    def test_15_prompt_uses_existing_frozen_anomaly_report(self) -> None:
        for case in self.cases:
            source = Path(case.target_evidence_source)
            self.assertTrue(source.is_file())
            self.assertIn("production run-level anomaly snapshot", case.user_prompt)
            self.assertIn("Subruns in log:", case.user_prompt)

    def test_16_structured_output_parser_works(self) -> None:
        plain = bench.parse_response_text(json.dumps(VALID_PAYLOAD))
        fenced = bench.parse_response_text("```json\n" + json.dumps(VALID_PAYLOAD) + "\n```")
        self.assertEqual(plain.category, VALID_PAYLOAD["category"])
        self.assertEqual(fenced.confidence, 0.35)

    def test_17_schema_rejects_recovery_and_invalid_confidence(self) -> None:
        with self.assertRaises(bench.ResponseParsingError):
            bench.parse_response_text(json.dumps({**VALID_PAYLOAD, "recovery": "invented"}))
        with self.assertRaises(bench.ResponseParsingError):
            bench.parse_response_text(json.dumps({**VALID_PAYLOAD, "confidence": 1.2}))

    def test_18_supporting_runs_must_be_visible(self) -> None:
        case = self.by_run[1640]
        parsed = bench.NovelResponse.model_validate(
            {**VALID_PAYLOAD, "supporting_historical_runs": [1642]}
        )
        with self.assertRaises(bench.ResponseParsingError):
            bench.validate_prediction(case, parsed)

    def test_19_resume_skips_completed_case(self) -> None:
        case = self.cases[0]
        call_count = 0

        def fake_call(_system: str, _user: str, _model: str):
            nonlocal call_count
            call_count += 1
            return {"usage": {}}, bench.NovelResponse.model_validate(VALID_PAYLOAD)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            bench, "prepare_all_cases", return_value=([case], self.kb_path, self.kb_hash)
        ):
            result_dir = Path(tmp) / "result"
            bench.run_benchmark("mock-model", "luna", result_dir, api_call=fake_call, sleep_fn=lambda _: None)
            bench.run_benchmark("mock-model", "luna", result_dir, api_call=fake_call, sleep_fn=lambda _: None)
            self.assertEqual(call_count, 1)

    def completed_records(self) -> dict[int, dict]:
        records = {}
        for case in self.cases:
            parsed = bench.NovelResponse.model_validate(VALID_PAYLOAD)
            records[case.target_run] = bench.completed_record(case, parsed, {"model_id": "mock"})
        return records

    def test_20_yaml_has_six_entries_and_exact_fields(self) -> None:
        records = self.completed_records()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bench.write_outputs(root, records, "luna")
            payload = yaml.safe_load((root / "novel_predictions.yaml").read_text())
        self.assertEqual([entry["run"] for entry in payload], bench.EXPECTED_TARGETS)
        self.assertEqual(len(payload), 6)
        for entry in payload:
            self.assertEqual(set(entry), {"run", "category", "cause", "action"})

    def test_21_report_has_six_sections_without_ground_truth(self) -> None:
        report = bench.render_report(self.completed_records(), "luna")
        for run in bench.EXPECTED_TARGETS:
            self.assertEqual(report.count(f"## Run {run}\n"), 1)
        self.assertNotIn("Ground truth", report)
        self.assertNotIn("Correct", report)
        self.assertNotIn("Recovery:", report)

    def test_22_api_key_is_never_written(self) -> None:
        case = self.cases[0]
        secret = "sk-test-NEVER-WRITE-77b1"

        def fake_call(_system: str, _user: str, _model: str):
            return {"id": "mock", "usage": {}}, bench.NovelResponse.model_validate(VALID_PAYLOAD)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            bench, "prepare_all_cases", return_value=([case], self.kb_path, self.kb_hash)
        ), mock.patch.dict(os.environ, {"OPENAI_API_KEY": secret}):
            root = Path(tmp) / "result"
            bench.run_benchmark("mock-model", "luna", root, api_call=fake_call, sleep_fn=lambda _: None)
            combined = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in root.rglob("*")
                if path.is_file()
            )
        self.assertNotIn(secret, combined)

    def test_23_openai_adapter_uses_strict_schema_without_network(self) -> None:
        response = SimpleNamespace(output_text=json.dumps(VALID_PAYLOAD))
        client = mock.Mock()
        client.responses.create.return_value = response
        with mock.patch("openai.OpenAI", return_value=client):
            raw, parsed = bench.openai_call("system", "user", "mock-model")
        self.assertIs(raw, response)
        self.assertEqual(parsed.category, VALID_PAYLOAD["category"])
        schema = client.responses.create.call_args.kwargs["text"]["format"]
        self.assertEqual(schema["type"], "json_schema")
        self.assertTrue(schema["strict"])
        self.assertNotIn("recovery", json.dumps(schema["schema"]))

    def test_24_dry_run_makes_zero_api_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            bench, "openai_call"
        ) as api:
            root = Path(tmp) / "dry"
            bench.dry_run(root)
            config = json.loads((root / "run_config.json").read_text())
        api.assert_not_called()
        self.assertEqual(config["api_calls"], 0)
        self.assertEqual(len(config["prompt_sha256"]), 6)

    def test_25_result_records_contain_no_ground_truth_or_scoring(self) -> None:
        records = self.completed_records()
        serialized = json.dumps(records)
        self.assertNotIn("ground_truth", serialized)
        self.assertNotIn("field_status", serialized)
        self.assertNotIn("canonical_category", serialized)

    def test_26_full_mock_luna_sol_runs_write_identical_prompt_hashes(self) -> None:
        call_count = 0

        def fake_call(_system: str, _user: str, _model: str):
            nonlocal call_count
            call_count += 1
            return {"id": "mock", "usage": {}}, bench.NovelResponse.model_validate(VALID_PAYLOAD)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            bench, "prepare_all_cases", return_value=(self.cases, self.kb_path, self.kb_hash)
        ):
            root = Path(tmp)
            luna, sol = root / "luna", root / "sol"
            bench.run_benchmark("mock-luna", "luna", luna, api_call=fake_call, sleep_fn=lambda _: None)
            bench.run_benchmark("mock-sol", "sol", sol, api_call=fake_call, sleep_fn=lambda _: None)
            luna_config = json.loads((luna / "run_config.json").read_text())
            sol_config = json.loads((sol / "run_config.json").read_text())
            for result_dir in (luna, sol):
                predictions = yaml.safe_load((result_dir / "novel_predictions.yaml").read_text())
                self.assertEqual(len(predictions), 6)
                self.assertEqual((result_dir / "report.md").read_text().count("## Run "), 6)
        self.assertEqual(call_count, 12)
        self.assertEqual(luna_config["prompt_sha256"], sol_config["prompt_sha256"])


if __name__ == "__main__":
    unittest.main()
