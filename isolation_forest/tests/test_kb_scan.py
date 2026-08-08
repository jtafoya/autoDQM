import copy
import sys
import unittest
from pathlib import Path

ISOLATION_FOREST_DIR = Path(__file__).resolve().parents[1]
if str(ISOLATION_FOREST_DIR) not in sys.path:
    sys.path.insert(0, str(ISOLATION_FOREST_DIR))

from src.kb_scan import (
    build_expanded_kb,
    build_incident_ranges,
    build_neighbor_audit,
    classify_run,
)


SIMILARITY = {
    "threshold": 0.70,
    "weights": {
        "channels": 0.35,
        "features": 0.25,
        "methods": 0.15,
        "scores": 0.15,
        "alert_behavior": 0.10,
    },
    "score_scales": {"max_z": 10.0, "if_score": 0.10, "alert_streak": 5.0},
}


def signature(channel="1", feature="pulse", method="statistical", max_z=20.0, if_score=-0.6):
    return {
        "anomalous_channel_subrun_frequency": {channel: 0.8},
        "anomalous_channel_counts": {channel: 8},
        "triggered_feature_frequency": {feature: 1.0},
        "triggered_feature_counts": {feature: 8},
        "detection_method_fractions": {method: 1.0},
        "detection_method_counts": {method: 8},
        "max_z_distribution": {"median": max_z, "p90": max_z + 2},
        "if_score_distribution": {"median": if_score, "p90": if_score + 0.01},
        "alert_fraction": 0.5,
        "longest_consecutive_alert_streak": 3,
    }


def summary(run, valid, alerts, state="completed"):
    result = classify_run(run, valid, alerts, 10, 3)
    result["scan_status"] = "too_short" if result["short_run"] else state
    return result


class RunClassificationTests(unittest.TestCase):
    def test_case_a_streak_two_is_not_primary(self):
        row = classify_run(1, range(1, 11), [4, 5], 10, 3)
        self.assertFalse(row["primary_bad_run"])
        self.assertEqual(row["longest_consecutive_alert_streak"], 2)

    def test_case_b_streak_three_is_primary(self):
        row = classify_run(1, range(1, 11), [4, 5, 6], 10, 3)
        self.assertTrue(row["primary_bad_run"])
        self.assertEqual(row["longest_consecutive_alert_streak"], 3)

    def test_case_c_nonconsecutive_alerts_are_not_primary(self):
        row = classify_run(1, range(1, 11), [4, 6, 7], 10, 3)
        self.assertFalse(row["primary_bad_run"])
        self.assertEqual(row["longest_consecutive_alert_streak"], 2)

    def test_case_d_short_alerting_run_is_not_standalone(self):
        summaries = {1800: summary(1800, range(1, 9), range(1, 9))}
        neighbors = build_neighbor_audit(summaries, {1800: signature()}, SIMILARITY)
        ranges, members = build_incident_ranges(summaries, {1800: signature()}, neighbors, 3)
        self.assertFalse(summaries[1800]["primary_bad_run"])
        self.assertEqual(ranges, [])
        self.assertEqual(members, [])


class RangeFormationTests(unittest.TestCase):
    def base_summaries(self):
        return {
            1744: summary(1744, range(1, 11), [3, 4, 5]),
            1745: summary(1745, range(1, 9), range(1, 9)),
            1746: summary(1746, range(1, 11), [3, 4, 5]),
        }

    def test_case_e_compatible_short_bridge_is_absorbed(self):
        summaries = self.base_summaries()
        signatures = {1744: signature(), 1745: signature(), 1746: signature()}
        neighbors = build_neighbor_audit(summaries, signatures, SIMILARITY)
        ranges, members = build_incident_ranges(summaries, signatures, neighbors, 3)
        self.assertEqual((ranges[0]["run_start"], ranges[0]["run_end"]), (1744, 1746))
        self.assertEqual(ranges[0]["short_run_bridge_runs"], "1745")
        role = {row["run"]: row["membership_reason"] for row in members}
        self.assertEqual(role[1745], "short_run_bridge")

    def test_case_f_incompatible_signatures_do_not_bridge(self):
        summaries = self.base_summaries()
        signatures = {
            1744: signature(),
            1745: signature(),
            1746: signature("99", "other", "isolation_forest", 200.0, -2.0),
        }
        neighbors = build_neighbor_audit(summaries, signatures, SIMILARITY)
        ranges, _ = build_incident_ranges(summaries, signatures, neighbors, 3)
        self.assertEqual([(row["run_start"], row["run_end"]) for row in ranges], [(1744, 1744), (1746, 1746)])
        self.assertFalse(neighbors[0]["merge_decision"])

    def test_case_g_missing_run_is_never_bridged(self):
        summaries = self.base_summaries()
        summaries[1745] = summary(1745, [], [], state="incomplete")
        summaries[1745]["scan_status"] = "incomplete"
        signatures = {1744: signature(), 1746: signature()}
        neighbors = build_neighbor_audit(summaries, signatures, SIMILARITY)
        ranges, _ = build_incident_ranges(summaries, signatures, neighbors, 3)
        self.assertEqual([(row["run_start"], row["run_end"]) for row in ranges], [(1744, 1744), (1746, 1746)])
        self.assertIn("not observed short", neighbors[0]["decision_reason"])


class KnowledgeBaseTests(unittest.TestCase):
    def test_case_h_manual_annotation_is_preserved(self):
        manual = [{
            "run": 2126,
            "category": "LVDS_noise",
            "cause": "human diagnosis",
            "action": "human action",
            "recovery": "human recovery",
        }]
        original = copy.deepcopy(manual)
        ranges = [{
            "run_start": 2126,
            "run_end": 2126,
            "representative_runs": "2126",
            "mean_alert_fraction": 0.5,
            "median_alert_fraction": 0.5,
            "minimum_neighbor_similarity": 1.0,
            "dominant_anomalous_channels": "0;1",
            "dominant_triggered_features": "pulse",
            "dominant_detection_methods": "statistical",
        }]
        members = [{"run_start": 2126, "run_end": 2126, "run": 2126, "membership_reason": "primary_bad"}]
        expanded = build_expanded_kb(manual, ranges, members, "test_campaign")
        self.assertEqual(expanded[0]["category"], original[0]["category"])
        self.assertEqual(expanded[0]["cause"], original[0]["cause"])
        self.assertEqual(expanded[0]["action"], original[0]["action"])
        self.assertEqual(expanded[0]["recovery"], original[0]["recovery"])
        self.assertNotEqual(expanded[0]["category"], "Undefined")
        self.assertEqual(len(expanded), 1)


if __name__ == "__main__":
    unittest.main()
