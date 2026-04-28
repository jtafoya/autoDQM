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
                       add_specific_run_args, add_plot_format,
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
    add_specific_run_args(parser)       # per-run apply and combine modes
    add_plot_format(parser, cfg)        # --plot-format png/pdf/svg (default from config)
    # ... script-specific arguments ...
    args = parser.parse_args()
    validate_full_sample_args(parser, args)  # range-checks fractions; validates --apply-to-training-list

Post-parse helpers
------------------
Three helpers operate on the parsed Namespace and are intended to be called
immediately after validate_full_sample_args() in any script that trains a model:

  resolve_feature_flags(args, cfg) → (use_trigger, use_lvds)
      Applies --no-trigger / --no-trigger-LVDS overrides to the config baseline.

  resolve_run_config_flags(args, cfg) → (include_trigger_config, trigger_config_vars,
                                         include_daq_config, daq_config_vars)
      Applies --no-trigger-config / --no-daq-config overrides to the config baseline.

  build_train_effective(args, cfg, use_trigger, use_lvds,
                        include_trigger_config, trigger_config_vars,
                        include_daq_config, daq_config_vars) → dict
      Returns the canonical 'effective config' dict consumed by
      config.build_training_metadata().  Centralised here so that train.py and
      pipeline.py do not duplicate the construction.  Includes the resolved config
      variable lists for bookkeeping in training_metadata.json.
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

    Training (--train-goodRunList)
        Reads the complete slab catalogue instead of the default text run list.
        Defaults for quality and fraction come from config.yaml
        (train_goodRunList_quality / train_goodRunList_fraction).

    Apply (--read-full-sample-apply)
        Mirrors the training mode for the apply step: scores all catalogue files
        that pass the chosen quality filter instead of the default apply list.
        Defaults come from config.yaml
        (full_sample_apply_quality / full_sample_apply_fraction).

    All options default to config values; none are required at the command line.
    Per-run overrides are available via --train-goodRunList-quality,
    --train-goodRunList-fraction, --full-sample-apply-quality,
    --full-sample-apply-fraction, and --apply-to-training-list.
    """
    # ── Training ──────────────────────────────────────────────────────────────
    trn = parser.add_argument_group(
        "goodRunList training",
        "Use the complete slab dataset on EOS for training instead of the default "
        "good run list.  Defaults for quality and fraction come from config.yaml.",
    )
    trn.add_argument(
        "--train-goodRunList",
        action="store_true",
        help="Enable goodRunList training: resolve files from the slab catalogue "
             "on EOS instead of the default good run list.",
    )
    trn.add_argument(
        "--train-goodRunList-quality",
        choices=QUALITY_ALL_CHOICES,
        metavar="{" + ",".join(QUALITY_ALL_CHOICES) + "}",
        help="Quality filter for training. "
             "'All' selects entries passing at least one criterion (OR). "
             "(default: %(default)s)",
    )
    trn.add_argument(
        "--train-goodRunList-fraction",
        type=float,
        metavar="F",
        help="Fraction of the quality-filtered catalogue to use for training "
             "(0 < F ≤ 1).  A random sub-sample is drawn when F < 1. "
             "(default: %(default)s)",
    )
    trn.add_argument(
        "--train-goodRunList-min-run",
        type=int,
        metavar="RUN",
        help="Lowest run number (inclusive) to include in goodRunList training. "
             "Catalogue entries with run < RUN are excluded. "
             "(default: no lower bound)",
    )
    trn.add_argument(
        "--train-goodRunList-max-run",
        type=int,
        metavar="RUN",
        help="Highest run number (inclusive) to include in goodRunList training. "
             "Catalogue entries with run > RUN are excluded. "
             "(default: no upper bound)",
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
        "--apply-to-training-list",
        action="store_true",
        help="Apply the model to exactly the same files used for training "
             "(same quality filter, fraction, and seed).  Requires "
             "--train-goodRunList.  Overrides --read-full-sample-apply, "
             "--full-sample-apply-quality, and --full-sample-apply-fraction.",
    )

    parser.set_defaults(
        train_goodRunList            = False,
        train_goodRunList_quality    = cfg["train_goodRunList_quality"],
        train_goodRunList_fraction   = cfg["train_goodRunList_fraction"],
        train_goodRunList_min_run    = cfg["train_goodRunList_min_run"],
        train_goodRunList_max_run    = cfg["train_goodRunList_max_run"],
        read_full_sample_apply       = False,
        full_sample_apply_quality    = cfg["full_sample_apply_quality"],
        full_sample_apply_fraction   = cfg["full_sample_apply_fraction"],
        apply_to_training_list       = False,
    )


def add_specific_run_args(parser: argparse.ArgumentParser) -> None:
    """
    Add arguments for per-run apply mode and the combine step.

    --apply-specific-run RUN
        Requires --train-goodRunList.  Scans the slab directory on disk for
        every subrun of run RUN (catalogue-independent — any run can be
        targeted regardless of quality).  The fraction of files to score is
        controlled by --apply-specific-run-fraction (default 1.0), which is
        fully decoupled from --train-goodRunList-fraction.  Output is written
        to logs/<tag>_run<RUN>.csv; no report or plots are produced.  The
        text-based apply list is ignored entirely in per-run mode.  Cannot be
        combined with --apply-to-training-list.  Designed for Condor array jobs.

    --apply-specific-run-fraction F
        Fraction of the run's files to score (0 < F ≤ 1).  Applies only when
        --apply-specific-run is set.  Default: 1.0 (all files of the run).

    --combine-specific-run-outputs PATTERN
        Combine per-run CSVs matching logs/<tag>_run<PATTERN>.csv into the
        main logs/<tag>.csv.  PATTERN accepts shell wildcards (e.g. '*' for
        all runs, '100?' for runs 1000–1009).  Files not present on disk are
        silently skipped.  This is a standalone operation: it exits after
        combining.
    """
    grp = parser.add_argument_group(
        "specific-run apply / combine",
        "Per-run apply mode for Condor array jobs, and the corresponding combine step.",
    )
    grp.add_argument(
        "--apply-specific-run",
        type=int,
        metavar="RUN",
        default=None,
        help="Apply model to all subruns of RUN found on disk in the slab directory "
             "(catalogue-independent; any run can be targeted; requires --train-goodRunList). "
             "Output saved to logs/<tag>_run<RUN>.csv; no report or plots produced.",
    )
    grp.add_argument(
        "--apply-specific-run-fraction",
        type=float,
        metavar="F",
        default=1.0,
        help="Fraction of the run's files to score when --apply-specific-run is set "
             "(0 < F ≤ 1).  Decoupled from --train-goodRunList-fraction. "
             "(default: 1.0 — apply to all files of the run)",
    )
    grp.add_argument(
        "--combine-specific-run-outputs",
        metavar="PATTERN",
        default=None,
        help="Combine per-run CSVs matching logs/<tag>_run<PATTERN>.csv into "
             "logs/<tag>.csv. Accepts shell wildcards (e.g. '*', '100?'). "
             "Exits after combining.",
    )


def add_plot_format(parser: argparse.ArgumentParser, cfg: dict) -> None:
    """Add --plot-format (png / pdf / svg) with default from config."""
    parser.add_argument(
        "--plot-format",
        choices=["png", "pdf", "svg"],
        help="Output format for all figures (default: %(default)s)",
    )
    parser.set_defaults(plot_format=cfg.get("plot_format", "png"))


def add_run_config_flags(parser: argparse.ArgumentParser, cfg: dict) -> None:
    """
    Add --no-trigger-config and --no-daq-config flags.

    When set, these disable the corresponding per-run configuration feature
    groups and append a suffix to the model tag so outputs are self-documenting.
    The config supplies the baseline (includeConfigInfo_Trigger /
    includeConfigInfo_DAQ); the flags can only disable a group.
    """
    parser.add_argument(
        "--no-trigger-config",
        action="store_true",
        help="Exclude trigger board config features (active bits, prescales, mask, timing). "
             "Appends _ignoreTriggerConfig to the model tag.",
    )
    parser.add_argument(
        "--no-daq-config",
        action="store_true",
        help="Exclude DAQ config features (per-channel trigger thresholds). "
             "Appends _ignoreDAQConfig to the model tag.",
    )


def resolve_feature_flags(args: argparse.Namespace, cfg: dict) -> "tuple[bool, bool]":
    """
    Resolve use_trigger and use_lvds from config baseline and --no-* CLI overrides.

    The config sets the baseline; the flags can only disable a group, not enable
    one the config has turned off.  Returns (use_trigger, use_lvds).

    Used by train.py and pipeline.py — defined here to avoid duplicating the
    two-line pattern in every CLI entry point that exposes --no-trigger.
    """
    return (
        cfg["use_trigger"] and not args.no_trigger,
        cfg["use_lvds"]    and not args.no_trigger_lvds,
    )


def resolve_run_config_flags(
    args: argparse.Namespace,
    cfg: dict,
) -> "tuple[bool, tuple, bool, tuple]":
    """
    Resolve include_trigger_config / include_daq_config from config and --no-* overrides.

    Returns (include_trigger_config, trigger_config_vars, include_daq_config, daq_config_vars).
    """
    include_trigger_config = (
        cfg["includeConfigInfo_Trigger"] and not getattr(args, "no_trigger_config", False)
    )
    include_daq_config = (
        cfg["includeConfigInfo_DAQ"] and not getattr(args, "no_daq_config", False)
    )
    return (
        include_trigger_config,
        tuple(cfg["includeConfigVariables_Trigger"]),
        include_daq_config,
        tuple(cfg["includeConfigVariables_DAQ"]),
    )


def build_train_effective(
    args: argparse.Namespace,
    cfg: dict,
    use_trigger: bool,
    use_lvds: bool,
    include_trigger_config: bool = False,
    trigger_config_vars: tuple = (),
    include_daq_config: bool = False,
    daq_config_vars: tuple = (),
) -> dict:
    """
    Build the 'effective config' dict passed to build_training_metadata.

    Records the resolved training parameters so that training_metadata.json
    captures the exact values used (config defaults + any CLI overrides).
    Defined here alongside the argument helpers that set these values.
    """
    return {
        "good_list":                       args.good_list,
        "models_dir":                      args.models_dir,
        "z_threshold":                     args.z_threshold,
        "if_contamination":                args.if_contamination,
        "use_trigger":                     use_trigger,
        "use_lvds":                        use_lvds,
        "ignore_features":                 list(cfg["ignore_features"]),
        "train_goodRunList_quality":       args.train_goodRunList_quality,
        "train_goodRunList_fraction":      args.train_goodRunList_fraction,
        "train_goodRunList_min_run":       args.train_goodRunList_min_run,
        "train_goodRunList_max_run":       args.train_goodRunList_max_run,
        "test_seed":                       args.test_seed,
        "include_trigger_config":          include_trigger_config,
        "trigger_config_vars":             list(trigger_config_vars),
        "include_daq_config":              include_daq_config,
        "daq_config_vars":                 list(daq_config_vars),
        "run_configs_dir":                 cfg["run_configs_dir"],
        "thresholds_json_path":            cfg["thresholds_json_path"],
    }


def validate_full_sample_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> None:
    """
    Validate full-sample arguments after parser.parse_args().

    Checks:
    - fraction values are in (0, 1] when the corresponding mode is active
    - --apply-to-training-list requires --train-goodRunList
    - --apply-to-training-list and --apply-specific-run are mutually exclusive

    Call this immediately after parser.parse_args() in every script that uses
    add_full_sample_args().
    """
    if args.train_goodRunList:
        if not (0 < args.train_goodRunList_fraction <= 1.0):
            parser.error(
                f"--train-goodRunList-fraction must be in (0, 1]; "
                f"got {args.train_goodRunList_fraction}"
            )
    if getattr(args, "apply_to_training_list", False):
        if not args.train_goodRunList:
            parser.error("--apply-to-training-list requires --train-goodRunList")
        if getattr(args, "apply_specific_run", None) is not None:
            parser.error(
                "--apply-to-training-list and --apply-specific-run cannot be combined. "
                "Use --read-full-sample-apply so the apply catalogue is resolved "
                "independently of the training sub-sample."
            )
    if getattr(args, "read_full_sample_apply", False):
        if not (0 < args.full_sample_apply_fraction <= 1.0):
            parser.error(
                f"--full-sample-apply-fraction must be in (0, 1]; "
                f"got {args.full_sample_apply_fraction}"
            )
    if getattr(args, "apply_specific_run_fraction", 1.0) != 1.0:
        if not (0 < args.apply_specific_run_fraction <= 1.0):
            parser.error(
                f"--apply-specific-run-fraction must be in (0, 1]; "
                f"got {args.apply_specific_run_fraction}"
            )
