"""
Build or update the reference model and Isolation Forest from good data.

Default: good-list = ../data/good_run_list_EOS.txt

Usage — quick test (50 random files):
    python -m src.train --test

Usage — custom sample size:
    python -m src.train --test 100

Usage — full training (all files):
    python -m src.train

Usage — incremental update after collecting more good runs:
    python -m src.train --update
    (adds only files not yet seen; the Isolation Forest is always fully retrained)

Models are saved to --models-dir (default: models/).
"""

import argparse
import json
import sys
from pathlib import Path

from .run_list import resolve_run_list
from .reference import ReferenceModel, build_reference
from .detector import AnomalyDetector


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build reference model and train Isolation Forest from a run list."
    )
    parser.add_argument(
        "--good-list",
        default="../data/good_run_list_EOS.txt",
        help="Path to a text file listing good Digitizer CSV files "
             "(default: ../data/good_run_list_EOS.txt)",
    )
    parser.add_argument("--models-dir", default="models", help="Directory to save models")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Incremental mode: add new files to an existing reference without reprocessing old ones",
    )
    parser.add_argument(
        "--no-trigger",
        action="store_true",
        help="Exclude TriggerBoard features (use Digitizer-only features)",
    )
    parser.add_argument(
        "--no-trigger-LVDS",
        action="store_true",
        dest="no_trigger_lvds",
        help="Exclude LVDS pin count features from TriggerBoardSlab_run<N>_LVDSCounts.csv "
             "(enabled by default; use this flag to disable)",
    )
    parser.add_argument("--z-threshold", type=float, default=5.0, help="Z-score alert threshold")
    parser.add_argument(
        "--if-contamination",
        type=float,
        default=0.05,
        help="Expected fraction of anomalies in training data (Isolation Forest)",
    )
    parser.add_argument(
        "--test",
        type=int,
        nargs="?",
        const=50,
        default=None,
        metavar="N",
        help="Test mode: randomly sample N files (default N=50 when flag is given, omit for full run)",
    )
    args = parser.parse_args()
    use_trigger = not args.no_trigger
    use_lvds    = not args.no_trigger_lvds

    models_dir = Path(args.models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    ref_path = models_dir / "reference.npz"
    det_path = models_dir / "detector.pkl"
    seen_path = models_dir / "seen_files.json"

    # ---- Resolve file list ----
    print(f"Reading good run list from {args.good_list} ...")
    all_csv = resolve_run_list(args.good_list)
    if not all_csv:
        print("ERROR: Run list resolved to zero files. Check patterns in the list file.",
              file=sys.stderr)
        sys.exit(1)
    print(f"  {len(all_csv)} file(s) found.")

    # ---- Test mode: subsample ----
    if args.test:
        import random
        n = min(args.test, len(all_csv))
        all_csv = random.sample(all_csv, n)
        print(f"  [TEST MODE] Randomly selected {n} file(s) for training.")

    # ---- Build or update reference ----
    if args.update and ref_path.exists():
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
        ref, features_cache = build_reference(all_csv, use_trigger=use_trigger, use_lvds=use_lvds)
        seen = {Path(f).name for f in all_csv}

    ref.save(str(ref_path))
    seen_path.write_text(json.dumps(sorted(seen), indent=2))
    print(f"  Reference saved to {ref_path}")

    # ---- Train Isolation Forest ----
    print("Training Isolation Forest...")
    detector = AnomalyDetector(
        ref,
        z_threshold=args.z_threshold,
        if_contamination=args.if_contamination,
    )
    # Pass the cached features to avoid re-reading every file from disk.
    # In incremental mode there is no cache, so fall back to re-reading.
    cache = features_cache if not (args.update and ref_path.exists()) else None
    detector.train_isolation_forest(all_csv, features_cache=cache)
    detector.save(str(det_path))
    print(f"  Detector saved to {det_path}")

    print("\nDone. Next step: run  python -m src.monitor --watch-dir <live-dir>")


if __name__ == "__main__":
    main()
