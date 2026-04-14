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

Any step can be skipped with --skip-train / --skip-apply / --skip-report / --skip-all-plots.
Use --skip-subrun-plots to skip only the per-ALERT subrun plots while still producing
the reference_* and log_* summary plots.
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
from pathlib import Path

import pandas as pd

from .config import load_config


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
    ignore_features: tuple = (),
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

    if ignore_features:
        print(f"  Ignored features: {list(ignore_features)}")
    ref, features_cache = build_reference(all_csv, use_trigger=use_trigger, use_lvds=use_lvds,
                                          ignore_features=ignore_features)
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

    from .plot import plot_mean_table
    print("Saving mean feature table...")
    plot_mean_table(ref, models_dir)
    print(f"  Mean table saved → {models_dir}/reference_mean_table.png")


def step_apply(
    apply_list: str,
    models_dir: Path,
    log_file: Path,
    file_alert_n_channels: int,
    alert_consecutive_n: int,
    test_n: int,
    single_file_alert_n_channels: int = 0,
    single_file_alert_max_z: float = 0.0,
) -> None:
    from .run_list import resolve_run_list
    from .reference import ReferenceModel
    from .detector import AnomalyDetector
    from .monitor import process_file, _sort_key, _run_number

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

    # Sort by run/subrun so channel history accumulates in chronological order
    all_files = sorted(all_files, key=_sort_key)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.unlink(missing_ok=True)   # fresh log for this run

    channel_history: dict      = {}
    current_run:     "int | None" = None
    run_file_index:  int          = 0
    for i, f in enumerate(all_files, 1):
        run = _run_number(f)
        if run != current_run:
            if current_run is not None:
                print(f"  [run {run}] New run — channel history reset")
            current_run     = run
            run_file_index  = 0
            channel_history = {}
        process_file(str(f), detector, str(log_file),
                     file_alert_n_channels=file_alert_n_channels,
                     alert_consecutive_n=alert_consecutive_n,
                     channel_history=channel_history,
                     single_file_alert_n_channels=single_file_alert_n_channels,
                     single_file_alert_max_z=single_file_alert_max_z,
                     run_file_index=run_file_index)
        run_file_index += 1
        if i % 100 == 0:
            print(f"  --- {i}/{len(all_files)} files processed ---")

    print(f"\n  Log written → {log_file}")


def step_report(log_file: Path, reports_dir: Path, file_alert_n_channels: int) -> None:
    from .report import classify_runs, write_report

    _step("STEP 3 — REPORT")

    runs = classify_runs(str(log_file), file_alert_n_channels)
    if not runs:
        print("  No runs found in log — skipping report.")
        return
    write_report(runs, reports_dir)


def step_plots(
    log_file: Path,
    models_dir: Path,
    plots_dir: Path,
    file_alert_n_channels: int,
    alert_consecutive_n: int,
    single_file_alert_n_channels: int = 0,
    single_file_alert_max_z: float = 0.0,
    skip_subrun_plots: bool = False,
    max_subrun_plots: int = 10,
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
    plot_log(str(log_file), plots_dir,
             file_alert_n_channels=file_alert_n_channels,
             alert_consecutive_n=alert_consecutive_n,
             single_file_alert_n_channels=single_file_alert_n_channels,
             single_file_alert_max_z=single_file_alert_max_z)

    if skip_subrun_plots:
        print("[SKIP] Per-file subrun plots (--skip-subrun-plots)")
        print(f"  Plots saved → {plots_dir}/")
        return

    print("Per-file plots for ALERT files...")
    df = pd.read_csv(str(log_file))
    per_file = (
        df.groupby("filename")
          .agg(total=("channel", "count"), n_bad=("anomalous", "sum"))
    )
    alert_names = per_file[per_file["n_bad"] >= file_alert_n_channels].index.tolist()

    n_alert = len(alert_names)
    if max_subrun_plots == -1:
        print()
        print("!" * 60)
        print("  WARNING: max_subrun_plots = -1")
        print(f"  This will generate plots for ALL {n_alert} ALERT file(s).")
        print("  For large runs this can be very slow and use significant")
        print("  disk space.  Set  \"max_subrun_plots\": N  in config.json")
        print("  (or pass --max-subrun-plots N) to cap the output.")
        print("!" * 60)
        print()
        plot_names = alert_names
    else:
        plot_names = alert_names[:max_subrun_plots]
        if n_alert > max_subrun_plots:
            print(f"  Capped at {max_subrun_plots} of {n_alert} ALERT file(s)"
                  f" (set max_subrun_plots = -1 to plot all).")

    # Recover full paths from the log (filenames only) via a path cache stored
    # alongside the log by the apply step.
    path_cache_file = log_file.parent / (log_file.stem + "_paths.txt")
    if path_cache_file.exists():
        path_map = {Path(p).name: p for p in path_cache_file.read_text().splitlines() if p.strip()}
    else:
        path_map = {}

    n_plotted = 0
    for name in plot_names:
        full_path = path_map.get(name)
        if full_path is None:
            print(f"    [SKIP] {name} — full path not in cache, re-run with --apply-list to rebuild")
            continue
        out = plots_dir / Path(full_path).stem
        out.mkdir(parents=True, exist_ok=True)
        print(f"  {name}")
        try:
            plot_file(full_path, detector, out,
                      single_file_alert_n_channels=single_file_alert_n_channels,
                      single_file_alert_max_z=single_file_alert_max_z)
            n_plotted += 1
        except Exception as exc:
            print(f"    [ERROR] {exc}", file=sys.stderr)

    print(f"\n  {n_plotted}/{n_alert} ALERT file(s) plotted.")
    print(f"  All plots saved → {plots_dir}/")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # ── Pre-parse to locate the config file, then load it ────────────────────
    _pre = argparse.ArgumentParser(add_help=False)
    _pre.add_argument("--config", default="config.json")
    cfg = load_config(_pre.parse_known_args()[0].config)

    parser = argparse.ArgumentParser(
        description="Run the full autoDQM pipeline: train → apply → report → plots."
    )

    # ── Config ──
    parser.add_argument("--config", default="config.json",
                        help="Path to JSON configuration file (default: config.json)")

    # ── Input ──
    parser.add_argument("--good-list",  help="Run list of good files for training")
    parser.add_argument("--apply-list", help="Run list of files to apply the trained model to")

    # ── Output tag and directories ──
    parser.add_argument(
        "--model-tag",
        help="Tag used to name all outputs: models/<tag>/, logs/<tag>.csv, etc.",
    )
    parser.add_argument("--models-dir",  help="Base directory for saved models")
    parser.add_argument("--logs-dir",    help="Base directory for anomaly logs")
    parser.add_argument("--reports-dir", help="Base directory for run-classification reports")
    parser.add_argument("--plots-dir",   help="Base directory for diagnostic plots")

    # ── Feature set ──
    parser.add_argument("--no-trigger", action="store_true",
                        help="Exclude TriggerBoard features (Digitizer-only mode)")
    parser.add_argument("--no-trigger-LVDS", action="store_true", dest="no_trigger_lvds",
                        help="Exclude LVDS pin count features")

    # ── Thresholds ──
    parser.add_argument("--z-threshold",          type=float)
    parser.add_argument("--if-contamination",     type=float)
    parser.add_argument("--file-alert-n-channels", type=int,
                        help="Number of persistent anomalous channels to trigger a file-level ALERT")
    parser.add_argument(
        "--alert-consecutive-n",
        type=int,
        metavar="N",
        help="A channel must be anomalous in this many consecutive files to count as "
             "persistent (and contribute to ALERT). Set to 1 to disable (original behaviour).",
    )
    parser.add_argument(
        "--single-file-alert-n-channels",
        type=int,
        metavar="N",
        help="Raise [ALERT] immediately if this many channels are anomalous in a single "
             "file, regardless of persistence. 0 = disabled.",
    )
    parser.add_argument(
        "--single-file-alert-max-z",
        type=float,
        metavar="Z",
        help="Raise [ALERT] immediately if any channel's max_z reaches this value in a "
             "single file, regardless of persistence. 0 = disabled.",
    )

    # ── Test mode ──
    parser.add_argument("--test-train", type=int, nargs="?", const=50, default=None, metavar="N",
                        help="Test mode: sample N training files (default N=50 when flag is given)")
    parser.add_argument("--test-apply", type=int, nargs="?", const=50, default=None, metavar="N",
                        help="Test mode: sample N apply files (default N=50 when flag is given)")
    parser.add_argument("--test-seed", type=int)

    # ── Skip flags ──
    parser.add_argument("--skip-train",  action="store_true", help="Skip training step")
    parser.add_argument("--skip-apply",  action="store_true", help="Skip apply step")
    parser.add_argument("--skip-report", action="store_true", help="Skip report step")
    parser.add_argument("--skip-all-plots",    action="store_true",
                        help="Skip the entire plots step (no reference_*, log_*, or per-file plots)")
    parser.add_argument("--skip-subrun-plots", action="store_true",
                        help="Skip per-ALERT-file subrun plots; still generates reference_* and log_* summary plots")
    parser.add_argument(
        "--max-subrun-plots",
        type=int,
        metavar="N",
        help="Maximum number of per-ALERT subrun plot sets to generate, in run/subrun order. "
             "-1 = no limit (plots all ALERT files — prints a loud warning).",
    )

    # Apply config as defaults (CLI args override)
    parser.set_defaults(
        good_list            = cfg["good_list"],
        apply_list           = cfg["apply_list"],
        model_tag            = cfg["model_tag"],
        models_dir           = cfg["models_dir"],
        logs_dir             = cfg["logs_dir"],
        reports_dir          = cfg["reports_dir"],
        plots_dir            = cfg["plots_dir"],
        z_threshold           = cfg["z_threshold"],
        if_contamination      = cfg["if_contamination"],
        file_alert_n_channels         = cfg["file_alert_n_channels"],
        alert_consecutive_n           = cfg["alert_consecutive_n"],
        single_file_alert_n_channels  = cfg["single_file_alert_n_channels"],
        single_file_alert_max_z       = cfg["single_file_alert_max_z"],
        test_seed                     = cfg["test_seed"],
        max_subrun_plots              = cfg["max_subrun_plots"],
    )

    args = parser.parse_args()

    random.seed(args.test_seed)

    # use_trigger/use_lvds: config sets the baseline, --no-* flags override
    use_trigger = cfg["use_trigger"] and not args.no_trigger
    use_lvds    = cfg["use_lvds"]    and not args.no_trigger_lvds

    # Auto-append feature-set suffix to the tag so outputs are self-documenting
    tag = args.model_tag
    if not use_trigger:
        tag += "_noTrigger"
    if not use_lvds:
        tag += "_noLVDS"

    models_dir  = Path(args.models_dir)  / tag
    log_file    = Path(args.logs_dir)    / f"{tag}.csv"
    reports_dir = Path(args.reports_dir) / tag
    plots_dir   = Path(args.plots_dir)   / tag

    from .config import print_banner
    print_banner("pipeline", args.config, [
        ("model tag",            tag),
        ("good list",            args.good_list),
        ("apply list",           args.apply_list),
        ("models dir",           str(models_dir)),
        ("log file",             str(log_file)),
        ("reports dir",          str(reports_dir)),
        ("plots dir",            str(plots_dir)),
        ("trigger features",     "yes" if use_trigger else "no"),
        ("LVDS features",        "yes" if use_lvds else "no"),
        ("ignore features",      str(list(cfg["ignore_features"])) if cfg["ignore_features"] else "none"),
        ("z threshold",          f"{args.z_threshold}σ"),
        ("IF contamination",     str(args.if_contamination)),
        ("alert threshold",          f"{args.file_alert_n_channels} channels"),
        ("alert window",             f"{args.alert_consecutive_n} consecutive file(s)"),
        ("single-file bulk alert",   f"{args.single_file_alert_n_channels} ch"
                                     if args.single_file_alert_n_channels else "disabled"),
        ("single-file extreme alert",f"z≥{args.single_file_alert_max_z}"
                                     if args.single_file_alert_max_z else "disabled"),
        ("max subrun plots",         "ALL (WARNING)" if args.max_subrun_plots == -1
                                     else str(args.max_subrun_plots)),
        ("test seed",                str(args.test_seed)),
    ])

    models_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Train ──────────────────────────────────────────────────────
    if not args.skip_train:
        step_train(
            args.good_list, models_dir,
            args.z_threshold, args.if_contamination,
            args.test_train,
            use_trigger=use_trigger,
            use_lvds=use_lvds,
            ignore_features=tuple(cfg["ignore_features"]),
        )
        # Save a snapshot of the config used for this training run
        config_snapshot = models_dir / "config.json"
        shutil.copy2(args.config, config_snapshot)
        print(f"  Config snapshot saved to {config_snapshot}")
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
        from .monitor import process_file, _sort_key, _run_number

        _step("STEP 2 — APPLY")
        ref      = ReferenceModel.load(str(models_dir / "reference.npz"))
        detector = AnomalyDetector.load(str(models_dir / "detector.pkl"), ref)
        print(f"  Reference: {len(ref.known_channels())} channels  |  Z-threshold: {detector.z_threshold}σ")
        print(f"  {len(all_apply)} file(s) to process.")
        if args.test_apply:
            print(f"  [TEST MODE] {len(all_apply)} randomly sampled file(s).\n")

        # Sort by run/subrun so channel history accumulates in chronological order
        all_apply = sorted(all_apply, key=_sort_key)

        log_file.unlink(missing_ok=True)
        channel_history: dict      = {}
        current_run:     "int | None" = None
        run_file_index:  int          = 0
        for i, f in enumerate(all_apply, 1):
            run = _run_number(f)
            if run != current_run:
                if current_run is not None:
                    print(f"  [run {run}] New run — channel history reset")
                current_run     = run
                run_file_index  = 0
                channel_history = {}
            process_file(str(f), detector, str(log_file),
                         file_alert_n_channels=args.file_alert_n_channels,
                         alert_consecutive_n=args.alert_consecutive_n,
                         channel_history=channel_history,
                         single_file_alert_n_channels=args.single_file_alert_n_channels,
                         single_file_alert_max_z=args.single_file_alert_max_z,
                         run_file_index=run_file_index)
            run_file_index += 1
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
        step_report(log_file, reports_dir, args.file_alert_n_channels)
    else:
        print("[SKIP] Report")

    # ── Step 4: Plots ──────────────────────────────────────────────────────
    if not args.skip_all_plots:
        step_plots(log_file, models_dir, plots_dir,
                   args.file_alert_n_channels, args.alert_consecutive_n,
                   single_file_alert_n_channels=args.single_file_alert_n_channels,
                   single_file_alert_max_z=args.single_file_alert_max_z,
                   skip_subrun_plots=args.skip_subrun_plots,
                   max_subrun_plots=args.max_subrun_plots)
    else:
        print("[SKIP] Plots")

    print(f"\n{'='*60}")
    print("  Pipeline complete.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
