"""No-network tests for the context-enriched Novel Test."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = REPO_ROOT / "benchmarks" / "novel"
sys.path.insert(0, str(BENCHMARK_DIR))

import context_builders as builders  # noqa: E402
import novel_test as bench  # noqa: E402


VALID_PAYLOAD = {
    "category": "unknown_hardware_fault",
    "cause": "The supplied evidence is insufficient for a unique cause.",
    "action": "Inspect detector and DAQ evidence identified by the summaries.",
    "confidence": 0.35,
    "supporting_historical_runs": [],
    "reasoning_summary": "The supplied context does not uniquely identify a cause.",
}

BASELINE_PROMPT_HASHES = {
    "1620": "fc7333091a38cdf2a736e18577eb603d5f72fc33bf710adb33d75fb8ac568663",
    "1640": "2de08b9d2010a44cab734b4c6e5111cf38d88c52ace6f4890f5e1125d49b2890",
    "1642": "aea9c3d71b1eee1c15b75464dfe8a74f17e514cd8da99134d7fabff1929c0dd3",
    "1702": "ae29a832665b415525c77577a38b2cfc7a2421ecd849f3afaa17aacd88792a7d",
    "1703": "22bc1212b177e54813c5621b3612b58a89bf2a3642b69a5efa2b7ff02c475953",
    "2126": "e91337dba20887af9015f6349d466c36b226876ae55a968f9e4af3bee1c080d5",
}


class ContextNovelBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = bench.load_manifest(context_mode="full")
        cls.cases, cls.kb_path, cls.kb_hash = bench.prepare_all_cases(
            cls.manifest, context_mode="full"
        )
        cls.by_run = {case.target_run: case for case in cls.cases}

    def test_01_exactly_six_context_targets(self) -> None:
        self.assertEqual(list(self.manifest["targets"]), bench.EXPECTED_TARGETS)
        self.assertEqual(len(self.cases), 6)

    def test_02_explicit_context_exclusions_are_exact(self) -> None:
        actual = {run: spec["exclude_runs"] for run, spec in self.manifest["targets"].items()}
        self.assertEqual(actual, bench.CONTEXT_EXPECTED_EXCLUSIONS)
        self.assertEqual(actual[1640], [1640, 1642, 1637])
        self.assertEqual(actual[1642], [1642, 1640, 1637])
        self.assertEqual(actual[1702], [1702, 1703])
        self.assertEqual(actual[1703], [1703, 1702])

    def test_03_exclusions_remove_no_additional_cases(self) -> None:
        original = bench.recognition.load_kb(self.kb_path)
        original_runs = [bench.recognition.singleton_run(entry) for entry in original]
        for case in self.cases:
            expected = [run for run in original_runs if run not in case.exclude_runs]
            self.assertEqual(case.visible_historical_runs, expected)

    def test_04_target_and_family_entries_are_absent(self) -> None:
        for case in self.cases:
            visible = {bench.recognition.singleton_run(entry) for entry in case.filtered_kb}
            self.assertTrue(set(case.exclude_runs).isdisjoint(visible), case.target_run)

    def test_05_target_id_is_masked_in_every_context_section(self) -> None:
        for case in self.cases:
            pattern = bench.recognition.run_token_pattern(case.target_run)
            for section in (
                case.anomaly_summary,
                case.trigger_summary,
                case.lvds_summary,
                case.daq_config_summary,
                case.serialized_prompt,
            ):
                self.assertIsNone(pattern.search(section), case.target_run)
            self.assertIn("CASE_TARGET", case.serialized_prompt)

    def test_06_prompt_has_exact_context_structure(self) -> None:
        headings = (
            "CURRENT AUTODQM ANOMALY EVIDENCE",
            "TRIGGER CONTEXT",
            "LVDS CONTEXT",
            "DAQ / CONFIG CONTEXT",
            "HISTORICAL CASES",
            "## Task",
        )
        for case in self.cases:
            positions = [case.user_prompt.index(heading) for heading in headings]
            self.assertEqual(positions, sorted(positions))

    def test_07_ground_truth_annotation_is_absent(self) -> None:
        for case in self.cases:
            self.assertTrue(all(case.audit["target_ground_truth_fields_absent"].values()))
            self.assertTrue(case.audit["target_kb_entry_absent"])
            self.assertTrue(case.audit["required_family_entries_absent"])

    def test_08_recovery_ground_truth_is_absent(self) -> None:
        for case in self.cases:
            recovery = bench.normalized_text(case.forbidden_target_texts["recovery"])
            self.assertNotIn(recovery, bench.normalized_text(case.serialized_prompt))

    def test_09_elog_and_provenance_are_absent(self) -> None:
        for case in self.cases:
            lowered = case.serialized_prompt.lower()
            self.assertNotIn("elog", lowered)
            self.assertNotIn("run log message", lowered)
            self.assertTrue(case.audit["no_elog_or_provenance_text_present"])

    def test_10_context_sources_are_available_and_allowlisted(self) -> None:
        expected = {"trigger", "lvds", "daq_config"}
        for case in self.cases:
            self.assertEqual(set(case.context_availability), expected)
            self.assertTrue(all(case.context_availability.values()), case.target_run)
            self.assertEqual(set(case.audit["context_source_types"]), expected)

    def test_11_source_paths_and_filenames_are_not_model_visible(self) -> None:
        for case in self.cases:
            self.assertTrue(case.audit["target_source_path_and_filename_absent"])
            self.assertNotIn("/afs/", case.serialized_prompt)
            self.assertNotIn("/eos/", case.serialized_prompt)
            for paths in case.context_source_paths.values():
                for path in paths:
                    self.assertNotIn(path, case.serialized_prompt)
                    self.assertNotIn(Path(path).name, case.serialized_prompt)

    def test_12_trigger_context_builder(self) -> None:
        frame = pd.DataFrame(
            {
                "subrunnum": [1, 2, 3],
                "triggerRate_tot": [10.0, 11.0, 40.0],
                "triggerCounts_tot": [1000, 1001, 1002],
                "triggerRate_bit1": [5.0, 5.5, 20.0],
                "triggerRate_bit2": [0.0, 0.0, 0.0],
            }
        )
        config = {"cfg_trigger_bit0": 1.0, "cfg_prescale_bit0": 0.5}
        summary = builders.build_trigger_summary(frame, config)
        self.assertIn("Total trigger rate", summary)
        self.assertIn("bit1", summary)
        self.assertIn("physical", summary)
        self.assertIn("subrun 3", summary)

    def test_13_lvds_context_builder_and_mapping(self) -> None:
        data = {"subrunnum": [1, 2, 3], "total": [1000, 1000, 1000]}
        for pin in range(48):
            data[f"LVDSpin{pin}"] = [0, 0, 0] if pin == 0 else [100, 110, 105]
        summary = builders.build_lvds_summary(pd.DataFrame(data))
        self.assertIn("pin0->channels 0/1", summary)
        self.assertIn("Total LVDS counts", summary)
        self.assertLessEqual(len(summary), builders.MAX_SECTION_CHARS)

    def test_14_daq_config_context_builder(self) -> None:
        config = {
            **{f"cfg_trigger_bit{i}": float(i in (0, 1)) for i in range(16)},
            **{f"cfg_prescale_bit{i}": 1.0 for i in range(16)},
            **{f"cfg_mask_ch{i}": float(i != 3) for i in range(64)},
            "cfg_dead_time": 142.0,
        }
        summary = builders.build_daq_config_summary(config, {0: -0.015, 1: -0.020})
        self.assertIn("Enabled trigger paths", summary)
        self.assertIn("Masked physical pins: 3", summary)
        self.assertIn("DAQ trigger thresholds", summary)
        self.assertIn("queue occupancy", summary)

    def test_15_missing_context_is_safe(self) -> None:
        self.assertEqual(builders.build_trigger_summary(None), "Trigger context: unavailable")
        self.assertEqual(builders.build_lvds_summary(None), "LVDS context: unavailable")
        self.assertEqual(
            builders.build_daq_config_summary(None, None), "DAQ/config context: unavailable"
        )

    def test_16_context_is_summary_not_raw_csv(self) -> None:
        for case in self.cases:
            for summary in (case.trigger_summary, case.lvds_summary, case.daq_config_summary):
                self.assertLessEqual(len(summary), builders.MAX_SECTION_CHARS)
                self.assertNotIn("subrunnum,", summary)
                self.assertNotIn("triggerRate_bit1,triggerCounts_bit1", summary)
            self.assertTrue(case.audit["context_summaries_compact"])

    def test_17_structured_json_parsing(self) -> None:
        parsed = bench.parse_response_text(json.dumps(VALID_PAYLOAD))
        self.assertEqual(parsed.category, VALID_PAYLOAD["category"])
        with self.assertRaises(bench.ResponseParsingError):
            bench.parse_response_text(json.dumps({**VALID_PAYLOAD, "recovery": "not allowed"}))

    def test_18_context_resume_skips_completed_case(self) -> None:
        case = self.cases[0]
        calls = 0

        def fake_call(_system: str, _user: str, _model: str):
            nonlocal calls
            calls += 1
            return {"usage": {}}, bench.NovelResponse.model_validate(VALID_PAYLOAD)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            bench, "prepare_all_cases", return_value=([case], self.kb_path, self.kb_hash)
        ):
            result_dir = Path(tmp) / "result"
            bench.run_benchmark(
                "mock", "luna", result_dir, api_call=fake_call,
                sleep_fn=lambda _: None, context_mode="full"
            )
            bench.run_benchmark(
                "mock", "luna", result_dir, api_call=fake_call,
                sleep_fn=lambda _: None, context_mode="full"
            )
        self.assertEqual(calls, 1)

    def _records(self) -> dict[int, dict]:
        parsed = bench.NovelResponse.model_validate(VALID_PAYLOAD)
        return {
            case.target_run: bench.completed_record(case, parsed, {"model_id": "mock"})
            for case in self.cases
        }

    def test_19_yaml_and_report_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bench.write_outputs(root, self._records(), "luna_context")
            predictions = yaml.safe_load((root / "novel_predictions.yaml").read_text())
            report = (root / "report.md").read_text()
        self.assertEqual(len(predictions), 6)
        self.assertTrue(all(set(row) == {"run", "category", "cause", "action"} for row in predictions))
        self.assertEqual(report.count("## Run "), 6)
        self.assertNotIn("Recovery:", report)

    def test_20_api_key_is_never_saved(self) -> None:
        case = self.cases[0]
        secret = "sk-context-NEVER-SAVE-991"

        def fake_call(_system: str, _user: str, _model: str):
            return {"usage": {}}, bench.NovelResponse.model_validate(VALID_PAYLOAD)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            bench, "prepare_all_cases", return_value=([case], self.kb_path, self.kb_hash)
        ), mock.patch.dict(os.environ, {"OPENAI_API_KEY": secret}):
            root = Path(tmp) / "result"
            bench.run_benchmark(
                "mock", "luna", root, api_call=fake_call,
                sleep_fn=lambda _: None, context_mode="full"
            )
            combined = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in root.rglob("*") if path.is_file()
            )
        self.assertNotIn(secret, combined)

    def test_21_context_dry_run_has_six_cases_and_zero_api_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(bench, "openai_call") as api:
            root = Path(tmp) / "dry"
            bench.dry_run(root, context_mode="full")
            config = json.loads((root / "run_config.json").read_text())
            results = json.loads((root / "results.json").read_text())
            for run in bench.EXPECTED_TARGETS:
                self.assertTrue((root / "prompts" / f"target_{run}.txt").is_file())
                self.assertTrue((root / "contexts" / f"target_{run}_trigger.txt").is_file())
                self.assertTrue((root / "contexts" / f"target_{run}_lvds.txt").is_file())
                self.assertTrue((root / "contexts" / f"target_{run}_daq_config.txt").is_file())
        api.assert_not_called()
        self.assertEqual(config["api_calls"], 0)
        self.assertEqual(config["context_mode"], "full")
        self.assertEqual(results["summary"]["preflight_passed"], 6)

    def test_22_baseline_prompt_hashes_remain_unchanged(self) -> None:
        manifest = bench.load_manifest(context_mode="baseline")
        cases, _, _ = bench.prepare_all_cases(manifest, context_mode="baseline")
        actual = {str(case.target_run): case.prompt_sha256 for case in cases}
        self.assertEqual(actual, BASELINE_PROMPT_HASHES)


if __name__ == "__main__":
    unittest.main()
