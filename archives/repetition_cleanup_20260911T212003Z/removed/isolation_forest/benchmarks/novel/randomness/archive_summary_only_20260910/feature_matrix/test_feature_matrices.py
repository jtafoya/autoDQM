"""No-network tests for aggregation and deliberately conservative text linking."""
import unittest
import numpy as np
from build_feature_matrices import aggregate, extract_mentions


def pred(reasoning, action="", category="example"):
    return {"category": category, "cause": "unknown", "action": action, "reasoning_summary": reasoning}


class MatrixTests(unittest.TestCase):
    def test_nan_denominators_and_strict_threshold(self):
        cube = np.array([[[0., np.nan, 8.]], [[9., np.nan, -9.]], [[np.nan, np.nan, np.nan]]])
        maximum, frequency, n, above = aggregate(cube, 8.)
        np.testing.assert_allclose(maximum, [[9., np.nan, 9.]], equal_nan=True)
        np.testing.assert_allclose(frequency, [[.5, np.nan, .5]], equal_nan=True)
        np.testing.assert_array_equal(n, [[2, 0, 2]])
        np.testing.assert_array_equal(above, [[1, 0, 1]])

    def test_maximum_is_not_plot_clipped(self):
        maximum, frequency, n, above = aggregate(np.array([[[-1e6]], [[2.]]]), 8.)
        self.assertEqual(maximum[0, 0], 1e6)
        self.assertEqual(frequency[0, 0], .5)

    def test_no_cartesian_cell_expansion(self):
        hits = extract_mentions(pred("OBSERVED: channels 32/33 are missing. occupancy and nPulses_median vary."), ["occupancy", "nPulses_median"], 1)
        self.assertEqual({x["item"] for x in hits if x["kind"] == "channel"}, {"32", "33"})
        self.assertEqual({x["item"] for x in hits if x["kind"] == "feature"}, {"occupancy", "nPulses_median"})
        self.assertFalse(any(x["kind"] == "cell" for x in hits))

    def test_exact_target_observation_link(self):
        hits = extract_mentions(pred("OBSERVED: channel 32 has extreme deviations in occupancy, pulse count and height."), ["occupancy", "nPulses_median"], 1)
        cells = {x["item"] for x in hits if x["kind"] == "cell"}
        self.assertEqual(cells, {"ch32:occupancy"})

    def test_historical_and_recommended_checks_do_not_mark_cells(self):
        hits = extract_mentions(pred("OBSERVED: run 1604 had channel 0 nPulses_median deviations.", "Inspect occupancy on channel 33."), ["occupancy", "nPulses_median"], 1)
        self.assertFalse(any(x["kind"] == "cell" for x in hits))
        self.assertTrue(any(x["historical_or_ambiguous"] for x in hits))
        self.assertTrue(any(x["scope"] == "recommended_check" for x in hits))

    def test_category_underscores_are_lexical_separators(self):
        hits = extract_mentions(pred("", category="intermittent_digitizer_channel_pair_readout_fault"), ["occupancy"], 3)
        self.assertTrue(any(x["kind"] == "context" and x["item"].startswith("readout failure") for x in hits))


if __name__ == "__main__":
    unittest.main()
