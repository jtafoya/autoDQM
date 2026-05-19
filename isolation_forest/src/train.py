"""
Build or update the reference model and Isolation Forest from good data.

Default: good-list = ../data/good_run_list_EOS.txt

Usage — quick test (50 random files):
    python -m src.train --test

Usage — custom sample size (absolute N):
    python -m src.train --test 100

Usage — train on a random 10% fraction of the good run list:
    python -m src.train --fraction 0.1

Usage — full training (all files in good_list):
    python -m src.train

Usage — full training on the complete slab dataset from EOS:
    python -m src.train --train-goodRunList

Usage — override quality or fraction for a single run:
    python -m src.train --train-goodRunList --train-goodRunList-quality Tight
    python -m src.train --train-goodRunList --train-goodRunList-fraction 0.2

Usage — incremental update after collecting more good runs:
    python -m src.train --update
    (adds only files not yet seen; the Isolation Forest is always fully retrained)

Usage — disable per-run config integration (appends tag suffixes):
    python -m src.train --no-trigger-config   # → tag gets _ignoreTriggerConfig
    python -m src.train --no-daq-config       # → tag gets _ignoreDAQConfig

Config integration is enabled by default when includeConfigInfo_Trigger /
includeConfigInfo_DAQ are true in config.yaml.  When active, trigger rates
are prescale-normalised, disabled trigger types and LVDS-masked channels are
NaN'd out before building the reference — the model learns physics rates and
never sees masked channels, so config changes between runs never produce false
alerts.  See src/detector.py for full details on the three transformations.

Models are saved to --models-dir (default: models/).
The mean feature table figure format is set by --plot-format (png/pdf/svg,
default png; also configurable via ``plot_format`` in config.yaml).

Overwrite protection
--------------------
If models already exist in the target directory, the script stops with an
error.  Use --update to extend the reference incrementally, or delete the
directory to retrain from scratch.

Training metadata
-----------------
Each run saves <models-dir>/training_metadata.json containing the full
resolved configuration, the exact command, a timestamp, and an explicit
record of any values overridden on the command line relative to the config
file.  A copy of the config file is also saved as <models-dir>/config.yaml.

The effective-config dict fed to training_metadata.json is built by
args.build_train_effective(), shared with pipeline.py to avoid duplicating
the construction across CLI entry points.  Feature flags are resolved via
args.resolve_feature_flags() for the same reason.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

from .run_list import resolve_run_list, resolve_full_sample
from .reference import ReferenceModel, build_reference
from .detector import AnomalyDetector
from .config import print_step_header, print_banner, build_training_metadata, load_config
from .args import (preparse_config, add_config, add_features,
                   add_model_thresholds, add_test_mode,
                   add_full_sample_args, validate_full_sample_args, add_plot_format,
                   add_run_config_flags, resolve_feature_flags, resolve_run_config_flags,
                   build_train_effective)


def step_train(
    good_list: str,
    models_dir: Path,
    z_threshold: float,
    if_contamination: float,
    if_n_estimators: int,
    if_max_samples: int,
    if_max_features: float,
    test_n: int,
    use_trigger: bool = True,
    use_lvds: bool = False,
    ignore_features: tuple = (),
    include_trigger_config: bool = False,
    trigger_config_vars: tuple = (),
    include_daq_config: bool = False,
    daq_config_vars: tuple = (),
    run_configs_dir: str = "",
    thresholds_json_path: str = "",
    read_full_sample: bool = False,
    goodRunsList_json: str = "",
    full_sample_slab_dir: str = "",
    full_sample_quality: str = "",
    full_sample_fraction: float = 1.0,
    full_sample_min_run: "int | None" = None,
    full_sample_max_run: "int | None" = None,
    good_list_fraction: float = 1.0,
    test_seed: int = 42,
    update: bool = False,
    config_path: str = "",
    training_metadata: "dict | None" = None,
    fmt: str = "png",
) -> bool:
    """
    Build the ReferenceModel and train the IsolationForest from a set of good runs.

    Auto-skips if models already exist in *models_dir* and *update* is False.
    Returns True if training ran, False if skipped.
    """
    print_step_header("STEP 1 — TRAIN")

    if (models_dir / "detector.pkl").exists() and not update:
        print(f"[AUTO-SKIP] Training — models already exist in {models_dir}/")
        meta_path = models_dir / "training_metadata.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            ec   = meta.get("effective_config", {})
            ovr  = meta.get("cli_overrides", {})
            ovr_str = (", ".join(
                f"{k}: {v['config_value']} → {v['cli_value']}"
                for k, v in ovr.items()
            )) if ovr else "none"
            print(f"  trained      : {meta.get('timestamp', 'unknown')}")
            print(f"  z_threshold  : {ec.get('z_threshold', '?')}")
            print(f"  contamination: {ec.get('if_contamination', '?')}")
            print(f"  trigger      : {ec.get('use_trigger', '?')}  |  lvds: {ec.get('use_lvds', '?')}")
            print(f"  CLI overrides: {ovr_str}")
        print(f"  Pass --update to extend the reference incrementally,")
        print(f"  or delete {models_dir}/ to retrain from scratch.")
        return False

    # ---- Resolve file list ----
    if read_full_sample:
        print(
            f"  Reading full sample catalogue from {goodRunsList_json} "
            f"[quality={full_sample_quality}, fraction={full_sample_fraction}] ..."
        )
        all_csv = resolve_full_sample(
            json_path  = goodRunsList_json,
            slab_dir   = full_sample_slab_dir,
            quality    = full_sample_quality,
            fraction   = full_sample_fraction,
            seed       = test_seed,
            min_run    = full_sample_min_run,
            max_run    = full_sample_max_run,
        )
    else:
        print(f"  Reading good run list from {good_list} ...")
        all_csv = resolve_run_list(good_list)
        if good_list_fraction < 1.0:
            import random
            random.seed(test_seed)
            n = max(1, int(round(len(all_csv) * good_list_fraction)))
            all_csv = random.sample(all_csv, n)
            print(f"  Fraction {good_list_fraction}: using {n} randomly sampled file(s).")

    if not all_csv:
        print("ERROR: good run list resolved to zero files. Check patterns in the list file.",
              file=sys.stderr)
        sys.exit(1)

    if not read_full_sample:
        # resolve_full_sample already prints its own count summary
        print(f"  {len(all_csv)} good file(s) found.")
    print(f"  Trigger features:        {'enabled' if use_trigger else 'disabled'}")
    print(f"  LVDS features:           {'enabled' if use_lvds else 'disabled'}")
    print(f"  Trigger config features: {'enabled' if include_trigger_config else 'disabled'}"
          + (f"  {list(trigger_config_vars)}" if include_trigger_config else ""))
    print(f"  DAQ config features:     {'enabled' if include_daq_config else 'disabled'}"
          + (f"  {list(daq_config_vars)}" if include_daq_config else ""))

    # ---- Test mode: subsample ----
    if test_n:
        import random
        random.seed(test_seed)
        n = min(test_n, len(all_csv))
        all_csv = random.sample(all_csv, n)
        print(f"  [TEST MODE] Using {n} randomly sampled file(s).")

    if ignore_features:
        print(f"  Ignored features: {list(ignore_features)}")

    # ---- Build or update reference ----
    ref_path  = models_dir / "reference.npz"
    seen_path = models_dir / "seen_files.json"
    features_cache = None

    if update and ref_path.exists():
        print("Loading existing reference (incremental update)...")
        ref = ReferenceModel.load(str(ref_path))
        seen = set(json.loads(seen_path.read_text())) if seen_path.exists() else set()

        new_files = [f for f in all_csv if Path(f).name not in seen]
        if not new_files:
            print("  No new files to add.")
        else:
            from .features import extract_features
            for f in new_files:
                print(f"  [{Path(f).name}] adding to reference...")
                ref.update(extract_features(
                    str(f),
                    use_trigger=ref._use_trigger,
                    use_lvds=ref._use_lvds,
                    ignore_features=ref._ignore_features,
                    include_trigger_config=ref._include_trigger_config,
                    trigger_config_vars=ref._trigger_config_vars,
                    include_daq_config=ref._include_daq_config,
                    daq_config_vars=ref._daq_config_vars,
                    run_configs_dir=ref._run_configs_dir,
                    thresholds_json_path=ref._thresholds_json_path,
                ))
                seen.add(Path(f).name)
            print(f"  Added {len(new_files)} file(s). "
                  f"Reference now covers {len(ref.known_channels())} channels.")
    else:
        print("Building reference from scratch...")
        ref, features_cache = build_reference(
            all_csv,
            use_trigger=use_trigger,
            use_lvds=use_lvds,
            ignore_features=ignore_features,
            include_trigger_config=include_trigger_config,
            trigger_config_vars=trigger_config_vars,
            include_daq_config=include_daq_config,
            daq_config_vars=daq_config_vars,
            run_configs_dir=run_configs_dir,
            thresholds_json_path=thresholds_json_path,
        )
        seen = {Path(f).name for f in all_csv}

    ref.save(str(ref_path))
    seen_path.write_text(json.dumps(sorted(seen), indent=2))
    print(f"  Reference saved → {ref_path}")

    # ---- Train Isolation Forest ----
    print("Training Isolation Forest...")
    detector = AnomalyDetector(
        ref,
        z_threshold     = z_threshold,
        if_contamination = if_contamination,
        if_n_estimators = if_n_estimators,
        if_max_samples  = if_max_samples,
        if_max_features = if_max_features,
    )
    # In incremental mode features_cache is None; re-read all files from disk.
    detector.train_isolation_forest(all_csv, features_cache=features_cache)
    detector.save(str(models_dir / "detector.pkl"))
    print(f"  Detector saved  → {models_dir}/detector.pkl")

    # ---- Mean feature table ----
    from .plot import plot_mean_table
    print("Saving mean feature table...")
    plot_mean_table(ref, models_dir, fmt=fmt)
    print(f"  Mean table saved → {models_dir}/reference_mean_table.{fmt}")

    # ---- Config snapshot and training metadata ----
    if config_path:
        resolved = load_config(config_path)
        (models_dir / "config.yaml").write_text(
            yaml.dump(resolved, default_flow_style=False, sort_keys=False)
        )
        print(f"  Config snapshot saved → {models_dir}/config.yaml")
    if training_metadata is not None:
        meta_path = models_dir / "training_metadata.json"
        meta_path.write_text(json.dumps(training_metadata, indent=2))
        print(f"  Training metadata saved → {meta_path}")

    return True


def main() -> None:
    """CLI entry point: ``python3 -m src.train``."""
    _, cfg = preparse_config()

    parser = argparse.ArgumentParser(
        description="Build reference model and train Isolation Forest from a run list."
    )
    add_config(parser)
    parser.add_argument("--good-list",  help="Path to a text file listing good Digitizer CSV files")
    parser.add_argument(
        "--fraction",
        type=float,
        metavar="F",
        help="Fraction of the good run list to use for training (0 < F ≤ 1). "
             "Ignored when --train-goodRunList is set (use --train-goodRunList-fraction instead).",
    )
    parser.add_argument("--models-dir", help="Directory to save models")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Incremental mode: add new files to an existing reference without reprocessing old ones",
    )
    add_features(parser, cfg)
    add_run_config_flags(parser, cfg)
    add_model_thresholds(parser, cfg)
    parser.add_argument(
        "--test",
        type=int,
        nargs="?",
        const=50,
        default=None,
        metavar="N",
        help="Test mode: randomly sample N files (default N=50 when flag is given, omit for full run)",
    )
    add_test_mode(parser, cfg)
    add_full_sample_args(parser, cfg)
    add_plot_format(parser, cfg)

    parser.set_defaults(
        good_list  = cfg["good_list"],
        fraction   = cfg.get("good_list_fraction", 1.0),
        models_dir = cfg["models_dir"],
    )

    args = parser.parse_args()
    validate_full_sample_args(parser, args)
    use_trigger, use_lvds = resolve_feature_flags(args, cfg)
    include_trigger_config, trigger_config_vars, include_daq_config, daq_config_vars = \
        resolve_run_config_flags(args, cfg)

    models_dir = Path(args.models_dir)

    if args.train_goodRunList:
        input_source = (
            f"{cfg['goodRunsList_json']} "
            f"[quality={args.train_goodRunList_quality}, "
            f"fraction={args.train_goodRunList_fraction}]"
        )
        _lo = str(args.train_goodRunList_min_run) if args.train_goodRunList_min_run is not None else "—"
        _hi = str(args.train_goodRunList_max_run) if args.train_goodRunList_max_run is not None else "—"
        run_range = f"{_lo} … {_hi}"
    else:
        frac_str = f"{args.fraction}" if args.fraction < 1.0 else "1.0 (full)"
        input_source = f"{args.good_list}  [fraction={frac_str}]"
        run_range = "n/a"

    print_banner("train", args.config, [
        ("models dir",        str(models_dir)),
        ("input source",      input_source),
        ("train goodRunList", "yes" if args.train_goodRunList else "no"),
        ("run range",         run_range),
        ("trigger features",  "yes" if use_trigger else "no"),
        ("LVDS features",     "yes" if use_lvds else "no"),
        ("trigger config",    "yes" if include_trigger_config else "no"),
        ("  vars",            str(list(trigger_config_vars)) if include_trigger_config else "—"),
        ("DAQ config",        "yes" if include_daq_config else "no"),
        ("  vars",            str(list(daq_config_vars)) if include_daq_config else "—"),
        ("ignore features",   str(list(cfg["ignore_features"])) if cfg["ignore_features"] else "none"),
        ("z threshold",       f"{args.z_threshold}σ"),
        ("IF contamination",  str(args.if_contamination)),
        ("IF n_estimators",   str(args.if_n_estimators)),
        ("IF max_samples",    str(args.if_max_samples)),
        ("IF max_features",   str(args.if_max_features)),
        ("test mode",         f"{args.test} files" if args.test else "off (full run)"),
        ("test seed",         str(args.test_seed)),
        ("incremental",       "yes" if args.update else "no"),
    ])

    models_dir.mkdir(parents=True, exist_ok=True)

    metadata = build_training_metadata(
        cfg,
        build_train_effective(args, cfg, use_trigger, use_lvds,
                              include_trigger_config, trigger_config_vars,
                              include_daq_config, daq_config_vars),
        args.config, sys.argv,
    )

    if not step_train(
        args.good_list, models_dir,
        args.z_threshold, args.if_contamination,
        args.if_n_estimators, args.if_max_samples, args.if_max_features,
        args.test,
        use_trigger=use_trigger,
        use_lvds=use_lvds,
        ignore_features=tuple(cfg["ignore_features"]),
        include_trigger_config=include_trigger_config,
        trigger_config_vars=trigger_config_vars,
        include_daq_config=include_daq_config,
        daq_config_vars=daq_config_vars,
        run_configs_dir=cfg["run_configs_dir"],
        thresholds_json_path=cfg["thresholds_json_path"],
        read_full_sample     = args.train_goodRunList,
        goodRunsList_json     = cfg["goodRunsList_json"],
        full_sample_slab_dir = cfg["full_sample_slab_dir"],
        full_sample_quality  = args.train_goodRunList_quality,
        full_sample_fraction = args.train_goodRunList_fraction,
        full_sample_min_run  = args.train_goodRunList_min_run,
        full_sample_max_run  = args.train_goodRunList_max_run,
        good_list_fraction   = args.fraction,
        test_seed            = args.test_seed,
        update               = args.update,
        config_path          = args.config,
        training_metadata    = metadata,
        fmt                  = args.plot_format,
    ):
        sys.exit(1)

    print("\nDone. Next step: run  python -m src.monitor --watch-dir <live-dir>")


if __name__ == "__main__":
    main()
