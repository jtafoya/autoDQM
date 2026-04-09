"""
Monitor a directory for new Digitizer CSV files and log per-channel anomalies.

Uses polling (compatible with AFS and network filesystems where inotify is unreliable).
Each new Digitizer_*.csv file found is processed once; results are appended to a CSV log.

Usage:
    python -m src.monitor --watch-dir /eos/.../live --log-file logs/anomalies.csv

    # Auto-generate diagnostic plots for every alerted file:
    python -m src.monitor --watch-dir /eos/.../live --plot-alerts

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
    plot_alerts: bool = False,
    plots_dir: str = "plots",
) -> bool:
    """
    Analyze one file and append per-channel results to the log.

    Returns True if the file crossed the alert threshold, False otherwise.

    file_alert_threshold : fraction of channels that must be anomalous before
        the file is printed as [ALERT]. Individual channel anomalies are always
        logged, but low counts (likely spurious) are printed as [WARN] instead.
        Set to 0.0 to alert on any single anomalous channel.
    plot_alerts : if True and the file crosses the threshold, generate diagnostic
        plots saved to plots_dir/alerts/<stem>/.
    plots_dir : root directory for plot output.
    """
    filename = Path(filepath).name
    stem     = Path(filepath).stem
    timestamp = _utc_now()
    alerted = False

    try:
        results = detector.analyze_file(filepath)
    except Exception as exc:
        print(f"[ERROR] {filename}: {exc}", file=sys.stderr)
        return False

    if results.empty:
        print(f"[SKIP]  {timestamp}  {filename}  —  no events in file")
        return False

    anomalies = results[results["anomalous"]]
    n_total   = len(results)
    n_bad     = len(anomalies)
    frac_bad  = n_bad / n_total if n_total > 0 else 0.0

    if n_bad == 0:
        print(f"[OK]    {timestamp}  {filename}  —  {n_total} channels, all nominal")
    elif frac_bad >= file_alert_threshold:
        alerted = True
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
            f"{n_bad}/{n_total} ({frac_bad:.0%}) anomalous channels "
            f"(below alert threshold): {bad_channels}"
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

    # Auto-plot if alerted
    if alerted and plot_alerts:
        from .plot import plot_file as _plot_file
        out = Path(plots_dir) / "alerts" / stem
        out.mkdir(parents=True, exist_ok=True)
        print(f"         Generating plots → {out}/")
        try:
            _plot_file(filepath, detector, out)
        except Exception as exc:
            print(f"[ERROR] Plotting failed for {filename}: {exc}", file=sys.stderr)

    return alerted


def watch_directory(
    watch_dir: str,
    detector: AnomalyDetector,
    log_path: str,
    poll_interval: float = 5.0,
    process_existing: bool = False,
    file_alert_threshold: float = 0.20,
    plot_alerts: bool = False,
    plots_dir: str = "plots",
    refresh_log_plots_every: int = 0,
    test_n: int = 0,
) -> None:
    """
    Poll watch_dir for new Digitizer_*.csv files and process each one.

    Files already present when the monitor starts are skipped unless
    --process-existing is passed.

    test_n : if > 0, randomly sample this many files from watch_dir, process
        them, then exit immediately (no polling loop). Useful for quick checks
        that the pipeline is working end-to-end.

    refresh_log_plots_every : if > 0, regenerate log summary plots every N
        processed files. 0 disables automatic log plot refresh.
    """
    import random
    watch_path = Path(watch_dir)
    n_processed = 0

    # ── Test mode: sample N files and exit ───────────────────────────────────
    if test_n > 0:
        all_files = sorted(watch_path.glob("Digitizer_*.csv"))
        sample = random.sample(all_files, min(test_n, len(all_files)))
        print(f"[TEST MODE] Randomly selected {len(sample)} file(s) from {watch_dir}\n")
        for f in sample:
            process_file(
                str(f), detector, log_path,
                file_alert_threshold=file_alert_threshold,
                plot_alerts=plot_alerts,
                plots_dir=plots_dir,
            )
        print(f"\n[TEST MODE] Done. Processed {len(sample)} file(s).")
        return

    # ── Normal mode: poll for new files ──────────────────────────────────────
    seen: set = set()

    if not process_existing:
        seen = {f for f in watch_path.glob("Digitizer_*.csv")}
        print(f"  Skipping {len(seen)} pre-existing file(s). Watching for new ones...")

    print(f"Watching {watch_dir}  (poll every {poll_interval}s)  —  log: {log_path}")
    if plot_alerts:
        print(f"  Alert plots → {plots_dir}/alerts/<stem>/")
    if refresh_log_plots_every > 0:
        print(f"  Log summary plots refresh every {refresh_log_plots_every} file(s) → {plots_dir}/")
    print()

    try:
        while True:
            for f in sorted(watch_path.glob("Digitizer_*.csv")):
                if f not in seen:
                    seen.add(f)
                    process_file(
                        str(f), detector, log_path,
                        file_alert_threshold=file_alert_threshold,
                        plot_alerts=plot_alerts,
                        plots_dir=plots_dir,
                    )
                    n_processed += 1

                    if refresh_log_plots_every > 0 and n_processed % refresh_log_plots_every == 0:
                        if Path(log_path).exists():
                            from .plot import plot_log as _plot_log
                            print(f"  [log plots] Refreshing after {n_processed} files...")
                            try:
                                _plot_log(log_path, Path(plots_dir),
                                          file_alert_threshold=file_alert_threshold)
                            except Exception as exc:
                                print(f"[ERROR] Log plot refresh failed: {exc}", file=sys.stderr)

            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monitor a directory for anomalous Digitizer files."
    )
    parser.add_argument("--watch-dir", help="Directory to watch for new CSVs")
    parser.add_argument(
        "--run-list",
        help="Path to a run list file (glob patterns). When combined with --test N, "
             "randomly samples N files from the list and processes them, then exits. "
             "Alternative to --watch-dir for batch and test use.",
    )
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
    parser.add_argument(
        "--plot-alerts",
        action="store_true",
        help="Auto-generate diagnostic plots for every alerted file, "
             "saved to plots-dir/alerts/<stem>/",
    )
    parser.add_argument(
        "--plots-dir",
        default="plots",
        help="Root directory for plot output (default: plots/)",
    )
    parser.add_argument(
        "--refresh-log-plots-every",
        type=int,
        default=0,
        metavar="N",
        help="Regenerate log summary plots every N processed files (0 = disabled)",
    )
    parser.add_argument(
        "--test",
        type=int,
        default=0,
        metavar="N",
        help="Test mode: randomly sample N files from watch-dir, process them, then exit "
             "(no polling loop). Useful for quick end-to-end checks.",
    )
    args = parser.parse_args()

    if not args.watch_dir and not args.run_list:
        parser.error("one of --watch-dir or --run-list is required")
    if args.run_list and not args.test:
        parser.error("--run-list requires --test N (batch processing without a watch loop)")

    models_dir = Path(args.models_dir)
    ref_path   = models_dir / "reference.npz"
    det_path   = models_dir / "detector.pkl"

    if not ref_path.exists() or not det_path.exists():
        print(
            f"ERROR: Models not found in {args.models_dir}.\n"
            "Run  python -m src.train --good-list <run-list>  first.",
            file=sys.stderr,
        )
        sys.exit(1)

    Path(args.log_file).parent.mkdir(parents=True, exist_ok=True)

    print("Loading models...")
    ref      = ReferenceModel.load(str(ref_path))
    detector = AnomalyDetector.load(str(det_path), ref)
    print(f"  Reference: {len(ref.known_channels())} channels known")
    print(f"  Z-threshold: {detector.z_threshold}σ")
    print(f"  Trigger features: {'enabled' if detector._use_trigger else 'disabled'}")
    print()

    # ── Run-list test mode ────────────────────────────────────────────────────
    if args.run_list:
        import random
        from .run_list import resolve_run_list
        all_files = resolve_run_list(args.run_list)
        sample = random.sample(all_files, min(args.test, len(all_files)))
        print(f"[TEST MODE] {len(sample)} file(s) sampled from {args.run_list}\n")
        for f in sample:
            process_file(
                f, detector, args.log_file,
                file_alert_threshold=args.file_alert_threshold,
                plot_alerts=args.plot_alerts,
                plots_dir=args.plots_dir,
            )
        print(f"\n[TEST MODE] Done. Processed {len(sample)} file(s).")
        return

    # ── Directory watch mode ──────────────────────────────────────────────────
    watch_directory(
        args.watch_dir,
        detector,
        args.log_file,
        poll_interval=args.poll_interval,
        process_existing=args.process_existing,
        file_alert_threshold=args.file_alert_threshold,
        plot_alerts=args.plot_alerts,
        plots_dir=args.plots_dir,
        refresh_log_plots_every=args.refresh_log_plots_every,
        test_n=args.test,
    )


if __name__ == "__main__":
    main()
