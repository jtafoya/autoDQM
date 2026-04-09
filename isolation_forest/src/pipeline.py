"""
Run the full autoDQM pipeline in a single command:

  1. Train  — build reference model and Isolation Forest from a good run list
  2. Apply  — run the detector over an application run list, log results
  3. Report — classify runs into good / partial / bad
  4. Plots  — reference statistics, log summary, per-file diagnostics for ALERTs

Defaults: good-list = ../data/good_run_list_EOS.txt
          apply-list = ../data/all_run_list_EOS.txt

Usage — quick end-to-end test (50 files each, default):
    python3 -m src.pipeline --test-train --test-apply

Usage — full run (all files):
    python3 -m src.pipeline

Usage — custom sample size:
    python3 -m src.pipeline --test-train 100 --test-apply 50

Any step can be skipped with --skip-train / --skip-apply / --skip-report / --skip-plots.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import pandas as pd


# ── Step helpers ─────────────────────────────────────────────────────────────

def _step(name: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}\n")


def step_train(
    good_list: str,
    models_dir: Path,
    z_threshold: float,
    if_contamination: float,
    test_n: int,
    use_trigger: bool = True,
    use_lvds: bool = False,
) -> None:
    from .run_list import resolve_run_list
    from .reference import build_reference
    from .detector import AnomalyDetector

    _step("STEP 1 — TRAIN")

    all_csv = resolve_run_list(good_list)
    if not all_csv:
        print("ERROR: good run list resolved to zero files.", file=sys.stderr)
        sys.exit(1)
    print(f"  {len(all_csv)} good file(s) found.")
    print(f"  Trigger features: {'enabled' if use_trigger else 'disabled'}")
    print(f"  LVDS features:    {'enabled' if use_lvds else 'disabled'}")

    if test_n:
        n = min(test_n, len(all_csv))
        all_csv = random.sample(all_csv, n)
        print(f"  [TEST MODE] Using {n} randomly sampled file(s).")

    ref, features_cache = build_reference(all_csv, use_trigger=use_trigger, use_lvds=use_lvds)
    ref.save(str(models_dir / "reference.npz"))

    import json
    seen = {Path(f).name for f in all_csv}
    (models_dir / "seen_files.json").write_text(json.dumps(sorted(seen), indent=2))
    print(f"  Reference saved → {models_dir}/reference.npz")

    print("Training Isolation Forest...")
    detector = AnomalyDetector(ref, z_threshold=z_threshold, if_contamination=if_contamination)
    detector.train_isolation_forest(all_csv, features_cache=features_cache)
    detector.save(str(models_dir / "detector.pkl"))
    print(f"  Detector saved  → {models_dir}/detector.pkl")


def step_apply(
    apply_list: str,
    models_dir: Path,
    log_file: Path,
    file_alert_threshold: float,
    test_n: int,
) -> None:
    from .run_list import resolve_run_list
    from .reference import ReferenceModel
    from .detector import AnomalyDetector
    from .monitor import process_file

    _step("STEP 2 — APPLY")

    ref      = ReferenceModel.load(str(models_dir / "reference.npz"))
    detector = AnomalyDetector.load(str(models_dir / "detector.pkl"), ref)
    print(f"  Reference: {len(ref.known_channels())} channels  |  Z-threshold: {detector.z_threshold}σ")

    all_files = resolve_run_list(apply_list)
    if not all_files:
        print("ERROR: apply run list resolved to zero files.", file=sys.stderr)
        sys.exit(1)
    print(f"  {len(all_files)} file(s) found in apply list.")

    if test_n:
        n = min(test_n, len(all_files))
        all_files = random.sample(all_files, n)
        print(f"  [TEST MODE] Using {n} randomly sampled file(s).\n")

    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.unlink(missing_ok=True)   # fresh log for this run

    for i, f in enumerate(all_files, 1):
        process_file(str(f), detector, str(log_file),
                     file_alert_threshold=file_alert_threshold)
        if i % 100 == 0:
            print(f"  --- {i}/{len(all_files)} files processed ---")

    print(f"\n  Log written → {log_file}")


def step_report(log_file: Path, reports_dir: Path, file_alert_threshold: float) -> None:
    from .report import classify_runs, write_report

    _step("STEP 3 — REPORT")

    runs = classify_runs(str(log_file), file_alert_threshold)
    if not runs:
        print("  No runs found in log — skipping report.")
        return
    write_report(runs, reports_dir)


def step_plots(
    log_file: Path,
    models_dir: Path,
    plots_dir: Path,
    file_alert_threshold: float,
) -> None:
    from .reference import ReferenceModel
    from .detector import AnomalyDetector
    from .plot import plot_reference, plot_file, plot_log

    _step("STEP 4 — PLOTS")

    ref      = ReferenceModel.load(str(models_dir / "reference.npz"))
    detector = AnomalyDetector.load(str(models_dir / "detector.pkl"), ref)

    plots_dir.mkdir(parents=True, exist_ok=True)

    print("Reference plots...")
    plot_reference(ref, plots_dir)

    print("Log summary plots...")
    plot_log(str(log_file), plots_dir, file_alert_threshold=file_alert_threshold)

    print("Per-file plots for ALERT files...")
    df = pd.read_csv(str(log_file))
    per_file = (
        df.groupby("filename")
          .agg(total=("channel", "count"), n_bad=("anomalous", "sum"))
          .assign(frac=lambda x: x["n_bad"] / x["total"])
    )
    alert_names = per_file[per_file["frac"] >= file_alert_threshold].index.tolist()

    # Recover full paths from the log (filenames only) via the apply list lookup
    # We stored full paths in the log as base names; reconstruct from the log's
    # source column if available, otherwise skip files we can't locate.
    # The log only stores base filenames, so we search a path cache built from
    # the run list — but since we don't have the list here, we match against the
    # paths already known to the detector's reference (not ideal).
    # Simpler: use a path cache stored alongside the log.
    path_cache_file = log_file.parent / (log_file.stem + "_paths.txt")
    if path_cache_file.exists():
        path_map = {Path(p).name: p for p in path_cache_file.read_text().splitlines() if p.strip()}
    else:
        path_map = {}

    n_plotted = 0
    for name in alert_names:
        full_path = path_map.get(name)
        if full_path is None:
            print(f"    [SKIP] {name} — full path not in cache, re-run with --apply-list to rebuild")
            continue
        out = plots_dir / Path(full_path).stem
        out.mkdir(parents=True, exist_ok=True)
        print(f"  {name}")
        try:
            plot_file(full_path, detector, out)
            n_plotted += 1
        except Exception as exc:
            print(f"    [ERROR] {exc}", file=sys.stderr)

    print(f"\n  {n_plotted}/{len(alert_names)} ALERT file(s) plotted.")
    print(f"  All plots saved → {plots_dir}/")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full autoDQM pipeline: train → apply → report → plots."
    )

    # ── Input ──
    parser.add_argument("--good-list",  default="../data/good_run_list_EOS.txt",
                        help="Run list of good files for training "
                             "(default: ../data/good_run_list_EOS.txt)")
    parser.add_argument("--apply-list", default="../data/all_run_list_EOS.txt",
                        help="Run list of files to apply the trained model to "
                             "(default: ../data/all_run_list_EOS.txt)")

    # ── Test mode ──
    parser.add_argument("--test-train", type=int, nargs="?", const=50, default=None, metavar="N",
                        help="Test mode: sample N training files (default N=50 when flag is given)")
    parser.add_argument("--test-apply", type=int, nargs="?", const=50, default=None, metavar="N",
                        help="Test mode: sample N apply files (default N=50 when flag is given)")

    # ── Feature set ──
    parser.add_argument("--no-trigger", action="store_true",
                        help="Exclude TriggerBoard features (Digitizer-only mode)")
    parser.add_argument("--no-trigger-LVDS", action="store_true", dest="no_trigger_lvds",
                        help="Exclude LVDS pin count features from TriggerBoardSlab LVDSCounts CSV "
                             "(enabled by default; use this flag to disable)")

    # ── Thresholds ──
    parser.add_argument("--z-threshold",       type=float, default=5.0)
    parser.add_argument("--if-contamination",  type=float, default=0.05)
    parser.add_argument("--file-alert-threshold", type=float, default=0.20,
                        help="Fraction of anomalous channels to trigger a file-level ALERT")

    # ── Output paths ──
    parser.add_argument("--models-dir",  default="models",           help="Saved models directory")
    parser.add_argument("--log-file",    default="logs/anomalies.csv", help="Output anomaly log")
    parser.add_argument("--reports-dir", default="reports",           help="Run quality report output")
    parser.add_argument("--plots-dir",   default="plots",             help="Plot output directory")

    # ── Skip flags ──
    parser.add_argument("--skip-train",  action="store_true", help="Skip training step")
    parser.add_argument("--skip-apply",  action="store_true", help="Skip apply step")
    parser.add_argument("--skip-report", action="store_true", help="Skip report step")
    parser.add_argument("--skip-plots",  action="store_true", help="Skip plots step")

    args = parser.parse_args()

    models_dir  = Path(args.models_dir)
    log_file    = Path(args.log_file)
    reports_dir = Path(args.reports_dir)
    plots_dir   = Path(args.plots_dir)

    models_dir.mkdir(parents=True, exist_ok=True)

    use_trigger = not args.no_trigger
    use_lvds    = not args.no_trigger_lvds

    # ── Step 1: Train ──────────────────────────────────────────────────────
    if not args.skip_train:
        step_train(
            args.good_list, models_dir,
            args.z_threshold, args.if_contamination,
            args.test_train,
            use_trigger=use_trigger,
            use_lvds=use_lvds,
        )
    else:
        print("[SKIP] Training")
        if not (models_dir / "reference.npz").exists():
            print("ERROR: --skip-train set but no models found in "
                  f"{models_dir}. Run without --skip-train first.", file=sys.stderr)
            sys.exit(1)

    # ── Step 2: Apply ──────────────────────────────────────────────────────
    if not args.skip_apply:
        # Write a path cache alongside the log so step_plots can find full paths
        from .run_list import resolve_run_list
        all_apply = resolve_run_list(args.apply_list)
        if args.test_apply:
            all_apply = random.sample(all_apply, min(args.test_apply, len(all_apply)))

        path_cache = log_file.parent / (log_file.stem + "_paths.txt")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        path_cache.write_text("\n".join(all_apply))

        # Re-use the already-sampled list directly rather than re-sampling in step_apply
        from .reference import ReferenceModel
        from .detector import AnomalyDetector
        from .monitor import process_file

        _step("STEP 2 — APPLY")
        ref      = ReferenceModel.load(str(models_dir / "reference.npz"))
        detector = AnomalyDetector.load(str(models_dir / "detector.pkl"), ref)
        print(f"  Reference: {len(ref.known_channels())} channels  |  Z-threshold: {detector.z_threshold}σ")
        print(f"  {len(all_apply)} file(s) to process.")
        if args.test_apply:
            print(f"  [TEST MODE] {len(all_apply)} randomly sampled file(s).\n")

        log_file.unlink(missing_ok=True)
        for i, f in enumerate(all_apply, 1):
            process_file(str(f), detector, str(log_file),
                         file_alert_threshold=args.file_alert_threshold)
            if i % 100 == 0:
                print(f"  --- {i}/{len(all_apply)} files processed ---")
        print(f"\n  Log written → {log_file}")
    else:
        print("[SKIP] Apply")
        if not log_file.exists():
            print(f"ERROR: --skip-apply set but log not found: {log_file}", file=sys.stderr)
            sys.exit(1)

    # ── Step 3: Report ─────────────────────────────────────────────────────
    if not args.skip_report:
        step_report(log_file, reports_dir, args.file_alert_threshold)
    else:
        print("[SKIP] Report")

    # ── Step 4: Plots ──────────────────────────────────────────────────────
    if not args.skip_plots:
        step_plots(log_file, models_dir, plots_dir, args.file_alert_threshold)
    else:
        print("[SKIP] Plots")

    print(f"\n{'='*60}")
    print("  Pipeline complete.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
