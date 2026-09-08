import csv
import tempfile
import unittest
from pathlib import Path

from condor.kb_scan.campaign import _successful_scan_status, _validate_detector_outputs


def write_digitizer(path: Path, has_event: bool) -> None:
    text = "event_id,channel\n"
    if has_event:
        text += "1,0\n"
    path.write_text(text)


def write_anomaly_log(path: Path, filenames) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["filename", "channel"])
        writer.writeheader()
        for filename in filenames:
            writer.writerow({"filename": filename, "channel": 0})


class DetectorOutputValidationTests(unittest.TestCase):
    def test_mixed_valid_and_empty_inputs_complete(self):
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            inputs = [tmp / f"Digitizer_run100_subrun{i}.csv" for i in (1, 2, 3)]
            write_digitizer(inputs[0], True)
            write_digitizer(inputs[1], True)
            write_digitizer(inputs[2], False)
            paths = tmp / "paths.txt"
            paths.write_text("\n".join(str(path) for path in inputs))
            log = tmp / "anomaly.csv"
            write_anomaly_log(log, [inputs[0].name, inputs[1].name])

            accounting = _validate_detector_outputs(100, inputs, log, paths)

            self.assertEqual(accounting["n_input_subruns"], 3)
            self.assertEqual(accounting["n_valid_subruns"], 2)
            self.assertEqual(accounting["n_empty_subruns"], 1)
            self.assertEqual(accounting["empty_subruns"], [3])
            self.assertEqual(_successful_scan_status(accounting), "completed")

    def test_all_empty_inputs_are_a_valid_data_state(self):
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            inputs = [tmp / f"Digitizer_run101_subrun{i}.csv" for i in (1, 2)]
            for path in inputs:
                write_digitizer(path, False)
            paths = tmp / "paths.txt"
            paths.write_text("\n".join(str(path) for path in inputs))

            accounting = _validate_detector_outputs(101, inputs, tmp / "missing.csv", paths)

            self.assertEqual(accounting["n_valid_subruns"], 0)
            self.assertEqual(accounting["empty_subruns"], [1, 2])
            self.assertEqual(_successful_scan_status(accounting), "no_valid_data")

    def test_nonempty_missing_output_fails(self):
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            input_path = tmp / "Digitizer_run102_subrun1.csv"
            write_digitizer(input_path, True)
            paths = tmp / "paths.txt"
            paths.write_text(str(input_path))
            with self.assertRaisesRegex(RuntimeError, "non-empty input"):
                _validate_detector_outputs(102, [input_path], tmp / "missing.csv", paths)


if __name__ == "__main__":
    unittest.main()
