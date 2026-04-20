"""
Shared argparse helpers for the autoDQM isolation-forest pipeline.

Each add_*() function appends a logical group of arguments to an existing
ArgumentParser and wires in defaults from a loaded config dict.  Multiple
add_* calls each invoke parser.set_defaults() for their own keys; argparse
merges them, so order does not matter.

Typical usage in every script::

    import argparse
    from .args import (preparse_config, add_config, add_features,
                       add_model_thresholds, add_alert_thresholds,
                       add_test_mode, add_full_sample_args,
                       validate_full_sample_args)
    from .config import print_banner

    _, cfg = preparse_config()
    parser = argparse.ArgumentParser(description="...")
    add_config(parser)
    add_features(parser, cfg)
    add_model_thresholds(parser, cfg)
    add_alert_thresholds(parser, cfg)
    add_test_mode(parser, cfg)
    add_full_sample_args(parser, cfg)   # defaults from config; no required CLI args
    # ... script-specific arguments ...
    args = parser.parse_args()
    validate_full_sample_args(parser, args)  # range-checks fractions; validates --share-full-sample-lists
"""

import argparse

from .config import load_config
from .run_list import QUALITY_ALL_CHOICES


def preparse_config(argv=None) -> tuple:
    """
    Parse --config early (before the full parser is built) and load it.

    Returns (config_path: str, cfg: dict).  Call this before constructing
    the main ArgumentParser so that config-derived defaults are available
    when wiring the full argument set.
    """
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default="config.yaml")
    config_path = pre.parse_known_args(argv)[0].config
    return config_path, load_config(config_path)


# ── Individual argument groups ────────────────────────────────────────────────

def add_config(parser: argparse.ArgumentParser) -> None:
    """Add --config to the full parser (mirrors the pre-parse default)."""
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml)",
    )


def add_features(parser: argparse.ArgumentParser, cfg: dict) -> None:
    """
    Add feature-set toggle flags: --no-trigger and --no-trigger-LVDS.

    These control which feature groups are included in training and scoring.
    The config supplies the baseline (use_trigger / use_lvds); the flags
    can only disable a group, not enable one the config has turned off.
    """
    parser.add_argument(
        "--no-trigger", action="store_true",
        help="Exclude TriggerBoard rate features (Digitizer-only mode)",
    )
    parser.add_argument(
        "--no-trigger-LVDS", action="store_true", dest="no_trigger_lvds",
        help="Exclude LVDS pin-count features",
    )


def add_model_thresholds(parser: argparse.ArgumentParser, cfg: dict) -> None:
    """
    Add model-building thresholds: --z-threshold and --if-contamination.

    Used by train and pipeline.
    """
    parser.add_argument(
        "--z-threshold", type=float,
        help="Z-score alert threshold: |z| above this flags a feature as anomalous",
    )
    parser.add_argument(
        "--if-contamination", type=float,
        help="Expected fraction of anomalies in training data (Isolation Forest contamination)",
    )
    parser.set_defaults(
        z_threshold      = cfg["z_threshold"],
        if_contamination = cfg["if_contamination"],
    )


def add_alert_thresholds(parser: argparse.ArgumentParser, cfg: dict) -> None:
    """
    Add alert-decision thresholds.

    Covers the persistence-based alert (file_alert_n_channels,
    alert_consecutive_n) and the two single-file severity alerts
    (single_file_alert_n_channels, single_file_alert_max_z).

    Used by monitor and pipeline.
    """
    parser.add_argument(
        "--file-alert-n-channels", type=int,
        help="Minimum number of *persistent* anomalous channels required to raise [ALERT]",
    )
    parser.add_argument(
        "--alert-consecutive-n", type=int, metavar="N",
        help="A channel must be anomalous in this many consecutive files to count as "
             "persistent (and contribute to ALERT). Set to 1 to disable.",
    )
    parser.add_argument(
        "--single-file-alert-n-channels", type=int, metavar="N",
        help="Raise [ALERT] immediately if this many channels are anomalous in a "
             "single file, regardless of persistence. 0 = disabled.",
    )
    parser.add_argument(
        "--single-file-alert-max-z", type=float, metavar="Z",
        help="Raise [ALERT] immediately if any channel's max_z reaches this value in a "
             "single file, regardless of persistence. 0 = disabled.",
    )
    parser.set_defaults(
        file_alert_n_channels        = cfg["file_alert_n_channels"],
        alert_consecutive_n          = cfg["alert_consecutive_n"],
        single_file_alert_n_channels = cfg["single_file_alert_n_channels"],
        single_file_alert_max_z      = cfg["single_file_alert_max_z"],
    )


def add_test_mode(parser: argparse.ArgumentParser, cfg: dict) -> None:
    """
    Add --test-seed (shared across all scripts).

    Each script adds its own --test / --test-train / --test-apply argument
    independently since the nargs and metavar differ per script.
    """
    parser.add_argument(
        "--test-seed", type=int,
        help="Random seed for reproducible test-mode file sampling",
    )
    parser.set_defaults(test_seed=cfg["test_seed"])


def add_full_sample_args(parser: argparse.ArgumentParser, cfg: dict) -> None:
    """
    Add arguments for full-sample training and apply modes.

    Training (--read-full-sample)
        Reads the complete slab catalogue instead of the default text run list.
        Defaults for quality and fraction come from config.yaml
        (full_sample_train_quality / full_sample_train_fraction).

    Apply (--read-full-sample-apply)
        Mirrors the training mode for the apply step: scores all catalogue files
        that pass the chosen quality filter instead of the default apply list.
        Defaults come from config.yaml
        (full_sample_apply_quality / full_sample_apply_fraction).

    All options default to config values; none are required at the command line.
    Per-run overrides are available via --full-sample-train-quality,
    --full-sample-train-fraction, --full-sample-apply-quality,
    --full-sample-apply-fraction, and --share-full-sample-lists.
    """
    # ── Training ──────────────────────────────────────────────────────────────
    trn = parser.add_argument_group(
        "full-sample training",
        "Use the complete slab dataset on EOS for training instead of the default "
        "good run list.  Defaults for quality and fraction come from config.yaml.",
    )
    trn.add_argument(
        "--read-full-sample",
        action="store_true",
        help="Enable full-sample training: resolve files from the slab catalogue "
             "on EOS instead of the default good run list.",
    )
    trn.add_argument(
        "--full-sample-train-quality",
        choices=QUALITY_ALL_CHOICES,
        metavar="{" + ",".join(QUALITY_ALL_CHOICES) + "}",
        help="Quality filter for training. "
             "'All' selects entries passing at least one criterion (OR). "
             "(default: %(default)s)",
    )
    trn.add_argument(
        "--full-sample-train-fraction",
        type=float,
        metavar="F",
        help="Fraction of the quality-filtered catalogue to use for training "
             "(0 < F ≤ 1).  A random sub-sample is drawn when F < 1. "
             "(default: %(default)s)",
    )

    # ── Apply ─────────────────────────────────────────────────────────────────
    apl = parser.add_argument_group(
        "full-sample apply",
        "Use the complete slab dataset on EOS for the apply step instead of the "
        "default apply list.  Defaults for quality and fraction come from config.yaml.",
    )
    apl.add_argument(
        "--read-full-sample-apply",
        action="store_true",
        help="Enable full-sample apply: score files resolved from the slab "
             "catalogue on EOS instead of the default apply list.",
    )
    apl.add_argument(
        "--full-sample-apply-quality",
        choices=QUALITY_ALL_CHOICES,
        metavar="{" + ",".join(QUALITY_ALL_CHOICES) + "}",
        help="Quality filter for the apply step. "
             "'All' selects entries passing at least one criterion (OR). "
             "(default: %(default)s)",
    )
    apl.add_argument(
        "--full-sample-apply-fraction",
        type=float,
        metavar="F",
        help="Fraction of the quality-filtered catalogue to score "
             "(0 < F ≤ 1).  A random sub-sample is drawn when F < 1. "
             "(default: %(default)s)",
    )
    apl.add_argument(
        "--share-full-sample-lists",
        action="store_true",
        help="Apply the model to exactly the same files used for training "
             "(same quality filter, fraction, and seed).  Requires "
             "--read-full-sample.  Overrides --read-full-sample-apply, "
             "--full-sample-apply-quality, and --full-sample-apply-fraction.",
    )

    parser.set_defaults(
        read_full_sample             = False,
        full_sample_train_quality    = cfg["full_sample_train_quality"],
        full_sample_train_fraction   = cfg["full_sample_train_fraction"],
        read_full_sample_apply       = False,
        full_sample_apply_quality    = cfg["full_sample_apply_quality"],
        full_sample_apply_fraction   = cfg["full_sample_apply_fraction"],
        share_full_sample_lists      = False,
    )


def validate_full_sample_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> None:
    """
    Validate full-sample arguments after parser.parse_args().

    Checks:
    - fraction values are in (0, 1] when the corresponding mode is active
    - --share-full-sample-lists requires --read-full-sample

    Call this immediately after parser.parse_args() in every script that uses
    add_full_sample_args().
    """
    if args.read_full_sample:
        if not (0 < args.full_sample_train_fraction <= 1.0):
            parser.error(
                f"--full-sample-train-fraction must be in (0, 1]; "
                f"got {args.full_sample_train_fraction}"
            )
    if getattr(args, "share_full_sample_lists", False):
        if not args.read_full_sample:
            parser.error("--share-full-sample-lists requires --read-full-sample")
    if getattr(args, "read_full_sample_apply", False):
        if not (0 < args.full_sample_apply_fraction <= 1.0):
            parser.error(
                f"--full-sample-apply-fraction must be in (0, 1]; "
                f"got {args.full_sample_apply_fraction}"
            )
