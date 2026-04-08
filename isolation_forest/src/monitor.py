"""
Monitor a directory for new Digitizer CSV files and log per-channel anomalies.

Uses polling (compatible with AFS and network filesystems where inotify is unreliable).
Each new Digitizer_*.csv file found is processed once; results are appended to a CSV log.

Usage:
    python -m src.monitor --watch-dir /eos/.../live --log-file logs/anomalies.csv

Log columns:
    timestamp          UTC ISO-8601
    filename           base name of the processed file
    channel            detector channel ID
    anomalous          True/False
    method             which detection layer triggered (or "")
    triggered_features semicolon-separated feature names that exceeded z_threshold
    max_z              largest |z-score| across all features for this channel
    if_score           Isolation Forest anomaly score (more negative = more anomalous)
"""

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .reference import ReferenceModel
from .detector import AnomalyDetector


LOG_FIELDS = [
    "timestamp", "filename", "channel",
    "anomalous", "method", "triggered_features", "max_z", "if_score",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def process_file(
    filepath: str,
    detector: AnomalyDetector,
    log_path: str,
    file_alert_threshold: float = 0.20,
) -> None:
    """
    Analyze one file and append per-channel results to the log.

    file_alert_threshold : fraction of channels that must be anomalous before
        the file is printed as [ALERT]. Individual channel anomalies are always
        logged, but low counts (likely spurious) are printed as [WARN] instead.
        Set to 0.0 to alert on any single anomalous channel.
    """
    filename = Path(filepath).name
    timestamp = _utc_now()

    try:
        results = detector.analyze_file(filepath)
    except Exception as exc:
        print(f"[ERROR] {filename}: {exc}", file=sys.stderr)
        return

    anomalies = results[results["anomalous"]]
    n_total = len(results)
    n_bad = len(anomalies)
    frac_bad = n_bad / n_total if n_total > 0 else 0.0

    if n_bad == 0:
        print(f"[OK]    {timestamp}  {filename}  —  {n_total} channels, all nominal")
    elif frac_bad >= file_alert_threshold:
        bad_channels = sorted(anomalies.index.tolist())
        print(
            f"[ALERT] {timestamp}  {filename}  —  "
            f"{n_bad}/{n_total} ({frac_bad:.0%}) anomalous channels: {bad_channels}"
        )
        for ch in bad_channels:
            row = anomalies.loc[ch]
            print(
                f"         ch{ch:>3d}  method={row['method']:<20s}  "
                f"max_z={row['max_z']:<8}  if_score={row['if_score']:<10}  "
                f"features=[{row['triggered_features']}]"
            )
    else:
        bad_channels = sorted(anomalies.index.tolist())
        print(
            f"[WARN]  {timestamp}  {filename}  —  "
            f"{n_bad}/{n_total} ({frac_bad:.0%}) anomalous channels (below alert threshold): "
            f"{bad_channels}"
        )

    # Append to log
    log_path_obj = Path(log_path)
    write_header = not log_path_obj.exists()
    with open(log_path, "a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=LOG_FIELDS)
        if write_header:
            writer.writeheader()
        for channel, row in results.iterrows():
            writer.writerow(
                {
                    "timestamp": timestamp,
                    "filename": filename,
                    "channel": channel,
                    "anomalous": row["anomalous"],
                    "method": row["method"],
                    "triggered_features": row["triggered_features"],
                    "max_z": row["max_z"],
                    "if_score": row["if_score"],
                }
            )


def watch_directory(
    watch_dir: str,
    detector: AnomalyDetector,
    log_path: str,
    poll_interval: float = 5.0,
    process_existing: bool = False,
    file_alert_threshold: float = 0.20,
) -> None:
    """
    Poll watch_dir for new Digitizer_*.csv files and process each one.

    Files already present when the monitor starts are skipped unless
    --process-existing is passed.
    """
    watch_path = Path(watch_dir)
    seen: set = set()

    if not process_existing:
        # Mark all pre-existing files as seen so we only act on new arrivals
        seen = {f for f in watch_path.glob("Digitizer_*.csv")}
        print(f"  Skipping {len(seen)} pre-existing file(s). Watching for new ones...")

    print(f"Watching {watch_dir}  (poll every {poll_interval}s)  —  log: {log_path}\n")

    try:
        while True:
            for f in sorted(watch_path.glob("Digitizer_*.csv")):
                if f not in seen:
                    seen.add(f)
                    process_file(str(f), detector, log_path, file_alert_threshold)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monitor a directory for anomalous Digitizer files."
    )
    parser.add_argument("--watch-dir", required=True, help="Directory to watch for new CSVs")
    parser.add_argument("--models-dir", default="models", help="Directory containing saved models")
    parser.add_argument("--log-file", default="logs/anomalies.csv", help="Output log file")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Seconds between directory scans (default: 5)",
    )
    parser.add_argument(
        "--process-existing",
        action="store_true",
        help="Also process files already present in watch-dir at startup",
    )
    parser.add_argument(
        "--file-alert-threshold",
        type=float,
        default=0.20,
        help="Fraction of anomalous channels required to print [ALERT] (default: 0.20). "
             "Channels are always logged individually regardless of this setting.",
    )
    args = parser.parse_args()

    models_dir = Path(args.models_dir)
    ref_path = models_dir / "reference.npz"
    det_path = models_dir / "detector.pkl"

    if not ref_path.exists() or not det_path.exists():
        print(
            f"ERROR: Models not found in {args.models_dir}.\n"
            "Run  python -m src.train --good-dir <good-data-dir>  first.",
            file=sys.stderr,
        )
        sys.exit(1)

    Path(args.log_file).parent.mkdir(parents=True, exist_ok=True)

    print("Loading models...")
    ref = ReferenceModel.load(str(ref_path))
    detector = AnomalyDetector.load(str(det_path), ref)
    print(f"  Reference: {len(ref.known_channels())} channels known")
    print(f"  Z-threshold: {detector.z_threshold}σ")
    print()

    watch_directory(
        args.watch_dir,
        detector,
        args.log_file,
        poll_interval=args.poll_interval,
        process_existing=args.process_existing,
        file_alert_threshold=args.file_alert_threshold,
    )


if __name__ == "__main__":
    main()
