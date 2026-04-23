"""
Build or update the reference model and Isolation Forest from good data.

Default: good-list = ../data/good_run_list_EOS.txt

Usage — quick test (50 random files):
    python -m src.train --test

Usage — custom sample size:
    python -m src.train --test 100

Usage — full training (all files):
    python -m src.train

Usage — full training on the complete slab dataset from EOS:
    python -m src.train --train-goodRunList

Usage — override quality or fraction for a single run:
    python -m src.train --train-goodRunList --train-goodRunList-quality Tight
    python -m src.train --train-goodRunList --train-goodRunList-fraction 0.2

Usage — incremental update after collecting more good runs:
    python -m src.train --update
    (adds only files not yet seen; the Isolation Forest is always fully retrained)

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
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from .run_list import resolve_run_list, resolve_full_sample
from .reference import ReferenceModel, build_reference
from .detector import AnomalyDetector
from .args import (preparse_config, add_config, add_features,
                   add_model_thresholds, add_test_mode,
                   add_full_sample_args, validate_full_sample_args, add_plot_format)


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
    read_full_sample: bool = False,
    full_sample_json: str = "",
    full_sample_slab_dir: str = "",
    full_sample_quality: str = "",
    full_sample_fraction: float = 1.0,
    test_seed: int = 42,
    update: bool = False,
    config_path: str = "",
    training_metadata: "dict | None" = None,
    fmt: str = "png",
) -> bool:

    _step("STEP 1 — TRAIN")

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
            f"  Reading full sample catalogue from {full_sample_json} "
            f"[quality={full_sample_quality}, fraction={full_sample_fraction}] ..."
        )
        all_csv = resolve_full_sample(
            json_path  = full_sample_json,
            slab_dir   = full_sample_slab_dir,
            quality    = full_sample_quality,
            fraction   = full_sample_fraction,
            seed       = test_seed,
        )
    else:
        print(f"  Reading good run list from {good_list} ...")
        all_csv = resolve_run_list(good_list)

    if not all_csv:
        print("ERROR: good run list resolved to zero files. Check patterns in the list file.",
              file=sys.stderr)
        sys.exit(1)

    if not read_full_sample:
        # resolve_full_sample already prints its own count summary
        print(f"  {len(all_csv)} good file(s) found.")
    print(f"  Trigger features: {'enabled' if use_trigger else 'disabled'}")
    print(f"  LVDS features:    {'enabled' if use_lvds else 'disabled'}")

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
                ref.update(extract_features(str(f), use_trigger=ref._use_trigger, use_lvds=ref._use_lvds))
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
        )
        seen = {Path(f).name for f in all_csv}

    ref.save(str(ref_path))
    seen_path.write_text(json.dumps(sorted(seen), indent=2))
    print(f"  Reference saved → {ref_path}")

    # ---- Train Isolation Forest ----
    print("Training Isolation Forest...")
    detector = AnomalyDetector(ref, z_threshold=z_threshold, if_contamination=if_contamination)
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
        shutil.copy2(config_path, models_dir / "config.yaml")
        print(f"  Config snapshot saved → {models_dir}/config.yaml")
    if training_metadata is not None:
        meta_path = models_dir / "training_metadata.json"
        meta_path.write_text(json.dumps(training_metadata, indent=2))
        print(f"  Training metadata saved → {meta_path}")

    return True


def main() -> None:
    _, cfg = preparse_config()

    parser = argparse.ArgumentParser(
        description="Build reference model and train Isolation Forest from a run list."
    )
    add_config(parser)
    parser.add_argument("--good-list",  help="Path to a text file listing good Digitizer CSV files")
    parser.add_argument("--models-dir", help="Directory to save models")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Incremental mode: add new files to an existing reference without reprocessing old ones",
    )
    add_features(parser, cfg)
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
        models_dir = cfg["models_dir"],
    )

    args = parser.parse_args()
    validate_full_sample_args(parser, args)
    use_trigger = cfg["use_trigger"] and not args.no_trigger
    use_lvds    = cfg["use_lvds"]    and not args.no_trigger_lvds

    models_dir = Path(args.models_dir)

    from .config import print_banner, build_training_metadata

    if args.train_goodRunList:
        input_source = (
            f"{cfg['full_sample_json']} "
            f"[quality={args.train_goodRunList_quality}, "
            f"fraction={args.train_goodRunList_fraction}]"
        )
    else:
        input_source = args.good_list

    print_banner("train", args.config, [
        ("models dir",       str(models_dir)),
        ("input source",     input_source),
        ("train goodRunList", "yes" if args.train_goodRunList else "no"),
        ("trigger features", "yes" if use_trigger else "no"),
        ("LVDS features",    "yes" if use_lvds else "no"),
        ("ignore features",  str(list(cfg["ignore_features"])) if cfg["ignore_features"] else "none"),
        ("z threshold",      f"{args.z_threshold}σ"),
        ("IF contamination", str(args.if_contamination)),
        ("test mode",        f"{args.test} files" if args.test else "off (full run)"),
        ("test seed",        str(args.test_seed)),
        ("incremental",      "yes" if args.update else "no"),
    ])

    models_dir.mkdir(parents=True, exist_ok=True)

    effective = {
        "good_list":                  args.good_list,
        "models_dir":                 args.models_dir,
        "z_threshold":                args.z_threshold,
        "if_contamination":           args.if_contamination,
        "use_trigger":                use_trigger,
        "use_lvds":                   use_lvds,
        "ignore_features":            list(cfg["ignore_features"]),
        "train_goodRunList_quality":  args.train_goodRunList_quality,
        "train_goodRunList_fraction": args.train_goodRunList_fraction,
        "test_seed":                  args.test_seed,
    }
    metadata = build_training_metadata(cfg, effective, args.config, sys.argv)

    if not step_train(
        args.good_list, models_dir,
        args.z_threshold, args.if_contamination,
        args.test,
        use_trigger=use_trigger,
        use_lvds=use_lvds,
        ignore_features=tuple(cfg["ignore_features"]),
        read_full_sample     = args.train_goodRunList,
        full_sample_json     = cfg["full_sample_json"],
        full_sample_slab_dir = cfg["full_sample_slab_dir"],
        full_sample_quality  = args.train_goodRunList_quality,
        full_sample_fraction = args.train_goodRunList_fraction,
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
