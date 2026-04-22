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

Usage — full training on the complete slab dataset from EOS:
    python3 -m src.pipeline --read-full-sample --full-sample-train-quality Tight

Usage — apply the same files used for training:
    python3 -m src.pipeline --read-full-sample --share-full-sample-lists

Resuming an interrupted run
----------------------------
Steps whose outputs already exist are skipped automatically — the pipeline
resumes from the first incomplete step.  To force a step to re-run, delete
its output:
  - Training : delete  models/<tag>/
  - Apply    : delete  logs/<tag>.csv
  - Report   : delete  reports/<tag>/
  - Plots    : delete  plots/<tag>/

Any step can also be skipped manually with --skip-train / --skip-apply /
--skip-report / --skip-all-plots.  Use --skip-subrun-plots to skip only the
per-file plots while still producing the reference_* and log_* summaries.

Training metadata
-----------------
Each training run saves models/<tag>/training_metadata.json containing the
full resolved configuration, the exact command used, a timestamp, and an
explicit record of any values that were overridden on the command line
relative to the config file.  A copy of the config file itself is saved as
models/<tag>/config.yaml.

Deleting a model tag
--------------------
To remove all outputs for a given tag at once:
    python3 -m src.pipeline --delete-model-tag <tag>

This deletes models/<tag>/, logs/<tag>.csv, logs/<tag>_paths.txt,
reports/<tag>/, and plots/<tag>/.  A confirmation prompt requires typing YES
before anything is removed.  Cannot be combined with any other argument.
"""

import argparse
import random
import sys
from pathlib import Path

from .args import (preparse_config, add_config, add_features,
                   add_model_thresholds, add_alert_thresholds, add_test_mode,
                   add_full_sample_args, validate_full_sample_args)
from .train import step_train
from .monitor import step_apply


# ── Step helpers ─────────────────────────────────────────────────────────────

def _step(name: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}\n")


def step_report(log_file: Path, reports_dir: Path, file_alert_n_channels: int) -> bool:
    _step("STEP 3 — REPORT")

    if (reports_dir / "run_summary.csv").exists():
        print(f"[AUTO-SKIP] Report — {reports_dir}/run_summary.csv already exists.")
        print(f"            Delete {reports_dir}/ to regenerate.")
        return False

    from .report import classify_runs, write_report

    runs = classify_runs(str(log_file), file_alert_n_channels)
    if not runs:
        print("  No runs found in log — skipping report.")
        return True
    write_report(runs, reports_dir)
    return True


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
) -> bool:
    _step("STEP 4 — PLOTS")

    if (plots_dir / "reference_means.png").exists():
        print(f"[AUTO-SKIP] Plots — {plots_dir}/reference_means.png already exists.")
        print(f"            Delete {plots_dir}/ to regenerate.")
        return False

    import pandas as pd
    from .reference import ReferenceModel
    from .detector import AnomalyDetector
    from .plot import plot_reference, plot_file, plot_log

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
    return True


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    _, cfg = preparse_config()

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
    add_full_sample_args(parser, cfg)

    # ── Destructive operations ──
    parser.add_argument(
        "--delete-model-tag",
        metavar="NAME",
        default=None,
        help="Delete ALL outputs (models, log, reports, plots) for the exact tag NAME and exit. "
             "Cannot be combined with any other argument.",
    )

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

    # ── --delete-model-tag: must be the only operation ────────────────────
    if args.delete_model_tag is not None:
        allowed_flags = {"--delete-model-tag", "--config"}
        extra_flags = [
            a for a in sys.argv[1:]
            if a.startswith("--") and a.split("=")[0] not in allowed_flags
        ]
        if extra_flags:
            print(
                f"ERROR: --delete-model-tag cannot be combined with other arguments.\n"
                f"  Unexpected: {', '.join(extra_flags)}",
                file=sys.stderr,
            )
            sys.exit(1)

        tag = args.delete_model_tag
        candidates = [
            Path(args.models_dir)  / tag,
            Path(args.logs_dir)    / f"{tag}.csv",
            Path(args.logs_dir)    / f"{tag}_paths.txt",
            Path(args.reports_dir) / tag,
            Path(args.plots_dir)   / tag,
        ]
        to_delete = [p for p in candidates if p.exists()]

        if not to_delete:
            print(f"Nothing found for tag '{tag}' — no outputs to delete.")
            sys.exit(0)

        print(f"\nWARNING: The following will be permanently deleted for tag '{tag}':\n")
        for p in to_delete:
            label = "dir " if p.is_dir() else "file"
            print(f"  [{label}]  {p}")

        print("\nType YES and press Enter to confirm, or anything else to abort: ", end="", flush=True)
        if input().strip() != "YES":
            print("Aborted — nothing was deleted.")
            sys.exit(0)

        import shutil
        for p in to_delete:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            print(f"  Deleted: {p}")
        print(f"\nAll outputs for tag '{tag}' removed.")
        sys.exit(0)

    validate_full_sample_args(parser, args)

    random.seed(args.test_seed)

    # use_trigger/use_lvds: config sets the baseline, --no-* flags override
    use_trigger = cfg["use_trigger"] and not args.no_trigger
    use_lvds    = cfg["use_lvds"]    and not args.no_trigger_lvds

    # Auto-append feature-set suffix to the tag so outputs are self-documenting
    tag = args.model_tag
    if args.read_full_sample:
        tag += f"_{args.full_sample_train_quality}"
    if not use_trigger:
        tag += "_noTrigger"
    if not use_lvds:
        tag += "_noLVDS"

    models_dir  = Path(args.models_dir)  / tag
    log_file    = Path(args.logs_dir)    / f"{tag}.csv"
    reports_dir = Path(args.reports_dir) / tag
    plots_dir   = Path(args.plots_dir)   / tag

    from .config import print_banner

    if args.read_full_sample:
        train_source = (
            f"{cfg['full_sample_json']} "
            f"[quality={args.full_sample_train_quality}, "
            f"fraction={args.full_sample_train_fraction}]"
        )
    else:
        train_source = args.good_list

    if args.share_full_sample_lists:
        apply_source = (
            f"{cfg['full_sample_json']} "
            f"[quality={args.full_sample_train_quality}, "
            f"fraction={args.full_sample_train_fraction}] "
            f"[shared with training]"
        )
    elif args.read_full_sample_apply:
        apply_source = (
            f"{cfg['full_sample_json']} "
            f"[quality={args.full_sample_apply_quality}, "
            f"fraction={args.full_sample_apply_fraction}]"
        )
    else:
        apply_source = args.apply_list

    print_banner("pipeline", args.config, [
        ("model tag",            tag),
        ("train source",         train_source),
        ("full sample train",    "yes" if args.read_full_sample else "no"),
        ("apply source",         apply_source),
        ("full sample apply",    "yes" if args.read_full_sample_apply else "no"),
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
        from .config import build_training_metadata
        effective = {
            "good_list":                  args.good_list,
            "models_dir":                 args.models_dir,
            "z_threshold":                args.z_threshold,
            "if_contamination":           args.if_contamination,
            "use_trigger":                use_trigger,
            "use_lvds":                   use_lvds,
            "ignore_features":            list(cfg["ignore_features"]),
            "full_sample_train_quality":  args.full_sample_train_quality,
            "full_sample_train_fraction": args.full_sample_train_fraction,
            "test_seed":                  args.test_seed,
        }
        metadata = build_training_metadata(cfg, effective, args.config, sys.argv)
        step_train(
            args.good_list, models_dir,
            args.z_threshold, args.if_contamination,
            args.test_train,
            use_trigger=use_trigger,
            use_lvds=use_lvds,
            ignore_features=tuple(cfg["ignore_features"]),
            read_full_sample     = args.read_full_sample,
            full_sample_json     = cfg["full_sample_json"],
            full_sample_slab_dir = cfg["full_sample_slab_dir"],
            full_sample_quality  = args.full_sample_train_quality,
            full_sample_fraction = args.full_sample_train_fraction,
            test_seed            = args.test_seed,
            config_path          = args.config,
            training_metadata    = metadata,
        )
    else:
        print("[SKIP] Training")
        if not (models_dir / "reference.npz").exists():
            print("ERROR: --skip-train set but no models found in "
                  f"{models_dir}. Run without --skip-train first.", file=sys.stderr)
            sys.exit(1)

    # ── Step 2: Apply ──────────────────────────────────────────────────────
    if not args.skip_apply:
        from .run_list import resolve_run_list, resolve_full_sample
        if args.share_full_sample_lists:
            print(
                f"  [--share-full-sample-lists] Resolving apply list from same "
                f"catalogue params as training "
                f"[quality={args.full_sample_train_quality}, "
                f"fraction={args.full_sample_train_fraction}] ..."
            )
            all_apply = resolve_full_sample(
                json_path  = cfg["full_sample_json"],
                slab_dir   = cfg["full_sample_slab_dir"],
                quality    = args.full_sample_train_quality,
                fraction   = args.full_sample_train_fraction,
                seed       = args.test_seed,
            )
        elif args.read_full_sample_apply:
            print(
                f"  Reading full sample catalogue from {cfg['full_sample_json']} "
                f"[quality={args.full_sample_apply_quality}, "
                f"fraction={args.full_sample_apply_fraction}] ..."
            )
            all_apply = resolve_full_sample(
                json_path  = cfg["full_sample_json"],
                slab_dir   = cfg["full_sample_slab_dir"],
                quality    = args.full_sample_apply_quality,
                fraction   = args.full_sample_apply_fraction,
                seed       = args.test_seed,
            )
        else:
            all_apply = resolve_run_list(args.apply_list)
        if args.test_apply:
            print(f"  [TEST MODE] {len(all_apply)} file(s) to sample for apply.\n")
            all_apply = random.sample(all_apply, min(args.test_apply, len(all_apply)))
        step_apply(
            all_apply, models_dir, log_file,
            file_alert_n_channels=args.file_alert_n_channels,
            alert_consecutive_n=args.alert_consecutive_n,
            single_file_alert_n_channels=args.single_file_alert_n_channels,
            single_file_alert_max_z=args.single_file_alert_max_z,
        )
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
