"""
Run the full autoDQM pipeline in a single command:

  1. Train  — build reference model and Isolation Forest from a good run list
  2. Apply  — run the detector over an application run list, log results
  3. Report — classify runs into good / partial / bad
  4. Plots  — reference statistics, log summary, per-file diagnostics for a sample of good and bad subruns

Defaults: good-list = ../data/good_run_list_EOS.txt
          apply-list = ../data/all_run_list_EOS.txt

Usage — quick end-to-end test (50 files each, default):
    python3 -m src.pipeline --test-train --test-apply

Usage — full run (all files):
    python3 -m src.pipeline

Usage — custom sample size:
    python3 -m src.pipeline --test-train 100 --test-apply 50

Any step can be skipped with --skip-train / --skip-apply / --skip-report / --skip-all-plots.
Use --skip-subrun-plots to skip only the per-subrun plots while still producing
the reference_* and log_* summary plots.
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
from pathlib import Path

from .args import (preparse_config, add_config, add_features,
                   add_model_thresholds, add_alert_thresholds, add_test_mode)


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
    import pandas as pd
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

    print("Per-file plots (sample of good and bad subruns)...")
    df = pd.read_csv(str(log_file))
    per_file = (
        df.groupby("filename")
          .agg(total=("channel", "count"), n_bad=("anomalous", "sum"))
    )
    # Split into bad (alert) and good (below threshold), bad sorted worst-first
    bad_df   = per_file[per_file["n_bad"] >= file_alert_n_channels].sort_values("n_bad", ascending=False)
    good_df  = per_file[per_file["n_bad"] <  file_alert_n_channels]

    bad_names  = bad_df.index.tolist()
    good_names = good_df.index.tolist()

    n_bad  = len(bad_names)
    n_good = len(good_names)

    if max_subrun_plots == -1:
        print()
        print("!" * 60)
        print("  WARNING: max_subrun_plots = -1")
        print(f"  This will generate plots for ALL {n_bad} bad and ALL {n_good} good file(s).")
        print("  For large runs this can be very slow and use significant")
        print("  disk space.  Set  \"max_subrun_plots\": N  in config.yaml")
        print("  (or pass --max-subrun-plots N) to cap the output.")
        print("!" * 60)
        print()
        plot_bad  = bad_names
        plot_good = good_names
    else:
        # Bad: always include the worst subrun, then randomly sample from the rest
        if bad_names:
            worst     = bad_names[:1]
            remaining = bad_names[1:]
            n_extra   = min(max_subrun_plots - 1, len(remaining))
            plot_bad  = worst + random.sample(remaining, n_extra)
        else:
            plot_bad = []

        # Good: random sample up to max_subrun_plots
        plot_good = random.sample(good_names, min(max_subrun_plots, len(good_names)))

        print(f"  Plotting {len(plot_bad)}/{n_bad} bad file(s) "
              f"(worst + {len(plot_bad)-1 if plot_bad else 0} random) "
              f"and {len(plot_good)}/{n_good} good file(s) (random).")

    plot_names = plot_bad + plot_good

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

    print(f"\n  {n_plotted}/{len(plot_names)} file(s) plotted ({len(plot_bad)} bad, {len(plot_good)} good).")
    print(f"  All plots saved → {plots_dir}/")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    config_path, cfg = preparse_config()

    parser = argparse.ArgumentParser(
        description="Run the full autoDQM pipeline: train → apply → report → plots."
    )

    # ── Config ──
    add_config(parser)

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
    add_features(parser, cfg)

    # ── Thresholds ──
    add_model_thresholds(parser, cfg)
    add_alert_thresholds(parser, cfg)

    # ── Test mode ──
    parser.add_argument("--test-train", type=int, nargs="?", const=50, default=None, metavar="N",
                        help="Test mode: sample N training files (default N=50 when flag is given)")
    parser.add_argument("--test-apply", type=int, nargs="?", const=50, default=None, metavar="N",
                        help="Test mode: sample N apply files (default N=50 when flag is given)")
    add_test_mode(parser, cfg)

    # ── Skip flags ──
    parser.add_argument("--skip-train",  action="store_true", help="Skip training step")
    parser.add_argument("--skip-apply",  action="store_true", help="Skip apply step")
    parser.add_argument("--skip-report", action="store_true", help="Skip report step")
    parser.add_argument("--skip-all-plots",    action="store_true",
                        help="Skip the entire plots step (no reference_*, log_*, or per-file plots)")
    parser.add_argument("--skip-subrun-plots", action="store_true",
                        help="Skip per-subrun plots; still generates reference_* and log_* summary plots")
    parser.add_argument(
        "--max-subrun-plots",
        type=int,
        metavar="N",
        help="Per category: up to N random bad subruns (always including the worst) and up to N random "
             "good subruns. -1 = no limit (plots every file — prints a loud warning).",
    )

    # Apply config as defaults (CLI args override)
    parser.set_defaults(
        good_list   = cfg["good_list"],
        apply_list  = cfg["apply_list"],
        model_tag   = cfg["model_tag"],
        models_dir  = cfg["models_dir"],
        logs_dir    = cfg["logs_dir"],
        reports_dir = cfg["reports_dir"],
        plots_dir   = cfg["plots_dir"],
        max_subrun_plots = cfg["max_subrun_plots"],
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
        config_snapshot = models_dir / "config.yaml"
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
