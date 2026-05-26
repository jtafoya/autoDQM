"""
Central configuration loader for the autoDQM isolation-forest pipeline.

All scripts read config.yaml (or a path given via --config) at startup and use
those values as defaults; explicit CLI arguments always override them.

Keys and their roles
--------------------
data_path            Base directory for all input data (run list files).
good_list            Path/glob list of good Digitizer CSVs used for training.
apply_list           Path/glob list of all CSVs to score.
model_tag            Label that namespaces all outputs under models/, logs/, etc.
models_dir           Root directory for saved models.
logs_dir             Root directory for per-run anomaly logs.
reports_dir          Root directory for run-classification reports.
plots_dir            Root directory for diagnostic plots.
use_trigger          Include TriggerBoard rate features (bool).
use_lvds             Include LVDS pin-count features (bool).

Per-run configuration features (optional, controlled by includeConfigInfo_*)
-----------------------------------------------------------------------------
run_configs_dir         Directory containing Run{N}TriggerDefault.py and
                        Run{N}DAQDefault.py config files.
thresholds_json_path    Path to thresholds.json (per-channel trigger thresholds).
includeConfigInfo_Trigger  Use per-run trigger board config to transform
                        observable features before scoring.  No new features
                        are added — the feature space size is unchanged.
                        When True, the variables listed in
                        includeConfigVariables_Trigger drive three in-place
                        transformations applied to every file at extract time:
                          • triggerBoard.prescale  → prescale-normalise each
                            triggerRate_bit{N} to the physics rate before
                            prescaling; runs with different prescale settings
                            become directly comparable.
                          • triggerBoard.trigger   → NaN triggerRate_bit{N}
                            for disabled trigger types (expected-zero rate is
                            not anomalous).
                          • triggerBoard.trigger_mask → NaN all features for
                            channels whose LVDS pin is masked.  The 8-byte
                            mask is indexed by physical pin number; LVDS data
                            channels are numbered consecutively, skipping dead
                            physical pins 32–39 and 43.  LVDS channel l (the
                            l-th non-dead physical pin) covers digitizer
                            channels 2l and 2l+1.
                        When False, behaviour is identical to the pre-config
                        code path and "_ignoreTriggerConfig" is appended to
                        the model tag.
includeConfigVariables_Trigger  List of trigger variable names to parse.
                        Supported: triggerBoard.trigger, triggerBoard.prescale,
                        triggerBoard.trigger_mask, triggerBoard.dead_time,
                        triggerBoard.coincidence_time, triggerBoard.nLayerThreshold,
                        triggerBoard.nHitThreshold, triggerBoard.zero_bias.
includeConfigInfo_DAQ   Accepted for API and tag-suffix purposes; currently
                        applies no transformation (no analytical normalisation
                        is available for per-channel thresholds without the full
                        pulse-height spectrum).  When False, "_ignoreDAQConfig"
                        is appended to the model tag.
includeConfigVariables_DAQ  List of DAQ variable names.  Supported:
                        channel.triggerThreshold.
z_threshold          |z-score| above which a channel feature is flagged.
if_contamination     Expected anomaly fraction passed to IsolationForest.

Persistence-based alert — targets sustained, gradual degradation:
  file_alert_n_channels  Minimum number of *persistent* channels required for [ALERT].
                         Can be low (e.g. 2) because persistence already filters noise.
  alert_consecutive_n    A channel must be anomalous in this many consecutive files to
                         be counted as persistent (1 = disabled, every anomaly is
                         immediately ALERT-eligible).

Single-file severity alerts — fire immediately on one bad file, no history needed:
  single_file_alert_n_channels  Minimum anomalous channels in a single file for [ALERT].
                         Targets sudden widespread events (power glitch, noisy run).
                         Should be higher than file_alert_n_channels (e.g. 5) since
                         there is no persistence filter to suppress transient noise.
                         0 = disabled.
  single_file_alert_max_z  If any channel's max_z meets or exceeds this value, raise
                         [ALERT] immediately. Targets a single channel that is
                         catastrophically out of range (e.g. broken digitizer channel).
                         0.0 = disabled.

poll_interval        Seconds between directory scans in watch mode.
live_good_list       Path to the live good-run list file updated by the monitor.
                     When set (non-empty), every subrun that passes
                     _subrun_quality_verdict() is appended to this file in real
                     time.  The file format is the same plain-text format read
                     by the training step.  "" (default) = disabled.
test_seed            Random seed for reproducible test-mode sampling.
max_subrun_plots     Number of subrun plot sets to generate per category in the
                     pipeline plots step. Produces up to max_subrun_plots random
                     bad subruns (always including the worst/most anomalous) and
                     up to max_subrun_plots random good subruns (n_bad below
                     file_alert_n_channels). -1 = no limit (plots every file —
                     can be very slow and disk-heavy for large runs; a prominent
                     warning is printed).

Full-sample training (--train-goodRunList mode)
-----------------------------------------------
These keys control training on the complete slab dataset stored on EOS.

full_sample_slab_dir   Root directory of the slab dataset on EOS.  Files are
                       organised in sub-directories named by the floor-100 of the
                       run number (e.g. run 1214 → .../slab/1200/).
goodRunsList_json       Path to the JSON good-runs catalogue
                       (goodRunsListSlab.json).  The file must contain a top-level
                       "data" list whose rows follow the column order:
                       [run, file, goodRunLoose, goodRunMedium, goodRunTight,
                        goodSingleTrigger, tag].
train_goodRunList_quality  Default quality level for training when --train-goodRunList
                           is active.  Accepted values: Loose, Medium, Tight, All
                           (OR of the three quality columns).  Can be overridden at
                           runtime with --train-goodRunList-quality.
train_goodRunList_fraction Fraction of the quality-filtered catalogue to use for
                           training (0 < value ≤ 1).  A value < 1 draws a random
                           sub-sample; set to 1.0 to use all matching entries.
train_goodRunList_min_run  Lowest run number (inclusive) to include in training.
                           Catalogue entries with run < this value are excluded
                           before quality filtering and sub-sampling.  None (default)
                           means no lower bound.  Overridable at runtime with
                           --train-goodRunList-min-run.
train_goodRunList_max_run  Highest run number (inclusive) to include in training.
                           Catalogue entries with run > this value are excluded
                           before quality filtering and sub-sampling.  None (default)
                           means no upper bound.  Overridable at runtime with
                           --train-goodRunList-max-run.
full_sample_apply_quality  Default quality level for the apply step when
                           --read-full-sample-apply is active.  Same accepted values
                           as train_goodRunList_quality.  Can be overridden at runtime
                           with --full-sample-apply-quality.
full_sample_apply_fraction Fraction of the quality-filtered catalogue to use for the
                           apply step (0 < value ≤ 1).  Defaults to 1.0 (score all
                           matching files).

LLM anomaly categorization (optional, triggered on [ALERT] only)
----------------------------------------------------------------
llm_enabled          When True, query an LLM on every [ALERT] to categorize the
                     anomaly and suggest an action based on historical bad runs.
                     Default False — zero overhead when disabled.
llm_provider         LLM provider to use.  Currently supported: "anthropic".
                     To add a new provider, implement one elif branch in
                     src/llm.py:_call_api() and install its package.
llm_model            Model ID passed to the provider API.
                     Default: "claude-haiku-4-5-20251001" (fast, cheap).
                     Swap to e.g. "claude-sonnet-4-6" for better reasoning.
llm_knowledge_base   Path to the YAML file mapping bad run numbers to human
                     annotations (category, cause, action, recovery).  Anomaly
                     snapshots for referenced runs are injected automatically
                     from the anomaly log — do not write feature values here.
llm_historical_log   Path to an existing anomaly log CSV used to fetch historical
                     run snapshots.  Typically a combined batch apply log.
                     If empty ("") or omitted, defaults automatically to the
                     live log produced by the current apply/monitor run.
"""

import yaml
from pathlib import Path

# Hardcoded fallback defaults — used only when a key is absent from config.yaml.
# These are intentionally conservative relative paths so the code stays runnable
# without any config file; the real site-specific values live in config.yaml.
DEFAULTS: dict = {
    "data_path":            "../data",
    "good_list":            "../data/good_run_list_EOS.txt",
    "good_list_fraction":   0.1,
    #"good_list_fraction":   1.0,
    "apply_list":           "../data/all_run_list_EOS.txt",
    #
    ### Training tag
    "model_tag":            "default",
    #
    ### Outputs
    "models_dir":           "models",
    "logs_dir":             "logs",
    "reports_dir":          "reports",
    "plots_dir":            "plots",
    "max_subrun_plots":     10,
    "plot_format":          "png",
    #
    ### Inference training and anomaly identification
    "z_threshold":          5.0,
    "if_contamination":     0.05,
    "file_alert_n_channels": 2,
    "alert_consecutive_n":  1,
    "single_file_alert_n_channels": 0,
    "single_file_alert_max_z":      0.0,
    "use_trigger":          True,
    "use_lvds":             True,
    "ignore_features":      [],
    #
    ### Per-run configuration features
    "run_configs_dir":             "/eos/experiment/milliqan/run3/slab/configs",
    "thresholds_json_path":        "/eos/experiment/milliqan/run3/slab/configs/thresholds.json",
    "includeConfigInfo_Trigger":   True,
    "includeConfigVariables_Trigger": [
        "triggerBoard.trigger",
        "triggerBoard.prescale",
        "triggerBoard.trigger_mask",
    ],
    "includeConfigInfo_DAQ":       True,
    "includeConfigVariables_DAQ":  ["channel.triggerThreshold"],
    #
    #
    "poll_interval":        5.0,
    "live_good_list":       "",     # path to live good-run list; "" = disabled
    "test_seed":            42,
    #
    ### Full-sample training
    "full_sample_slab_dir":  "/eos/experiment/milliqan/run3_MilliMon/slab",
    "goodRunsList_json":      "../data/goodRunsListSlab.json",
    #"train_goodRunList_quality":   "Loose",
    "train_goodRunList_quality":   "Medium",
    #"train_goodRunList_quality":   "Tight",
    #"train_goodRunList_quality":   "All",
    "train_goodRunList_fraction":  0.01,
    #"train_goodRunList_fraction":  1.0,
    "train_goodRunList_min_run":   None,
    "train_goodRunList_max_run":   None,
    "full_sample_apply_quality":   "Medium",
    "full_sample_apply_fraction":  1.0,
    #
    ### LLM anomaly categorization
    "llm_enabled":          False,
    "llm_provider":         "anthropic",
    "llm_model":            "claude-haiku-4-5-20251001",
    "llm_knowledge_base":   "data/llm_knowledge_base.yaml",
    "llm_historical_log":   "",   # defaults to the current apply/monitor log when empty
}


def print_step_header(name: str) -> None:
    """Print a prominent section header for a pipeline step."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}\n")


def print_banner(script: str, config_path: str, fields: list[tuple[str, str]]) -> None:
    """
    Print a startup banner showing the config file and effective runtime values.

    Parameters
    ----------
    script      : short script name shown in the header, e.g. "pipeline"
    config_path : path to the YAML config file that was loaded
    fields      : list of (label, value) pairs to display
    """
    width = 60
    print("=" * width)
    print(f"  autoDQM  ·  {script}")
    print(f"  config   : {config_path}")
    for label, value in fields:
        print(f"  {label:<22} {value}")
    print("=" * width)
    print()


def load_config(path: str = "configs/config.yaml") -> dict:
    """
    Load configuration from a YAML file, merged on top of DEFAULTS.

    If the file does not exist, returns a copy of DEFAULTS unchanged.
    Unknown keys in the file are passed through (scripts ignore what they
    don't use, so adding new keys never breaks old scripts).

    If the YAML contains a 'base' key, that file is loaded first (resolved
    relative to the directory of the config file), then the remaining keys
    override it.  This lets sweep configs be minimal override files:

        base: config.yaml
        z_threshold: 5.0
        if_contamination: 0.005
        model_tag: sweep__ifContamination_0p005__zThreshold_5sigma
    """
    cfg = dict(DEFAULTS)
    p = Path(path)
    if p.exists():
        data = yaml.safe_load(p.read_text()) or {}
        if "base" in data:
            base_path = (p.parent / data.pop("base")).resolve()
            if base_path.exists():
                cfg.update(yaml.safe_load(base_path.read_text()) or {})
        cfg.update(data)
    return cfg


def build_training_metadata(
    cfg: dict,
    effective: dict,
    config_path: str,
    argv: list,
) -> dict:
    """
    Build a metadata dict capturing the complete state of a training run.

    Parameters
    ----------
    cfg         : full resolved config (DEFAULTS merged with YAML), before any
                  CLI overrides.  Provides the baseline for override detection.
    effective   : training parameters as actually used (after CLI overrides and
                  any derived computations such as use_trigger).  Keys must be
                  a subset of cfg keys.
    config_path : path to the YAML config file that was loaded (args.config).
    argv        : sys.argv at the time of the call.

    Returns a dict with:
      timestamp       — ISO-8601 wall-clock time of the training run.
      command         — full command line, showing exactly what was invoked.
      config_file     — config file path.
      effective_config — cfg updated with every value in effective, giving the
                        complete resolved configuration that governed training.
      cli_overrides   — keys where the effective value differs from the config
                        file value, explicitly flagging CLI-driven changes.
                        Format: {key: {config_value: …, cli_value: …}}.
    """
    from datetime import datetime

    cli_overrides = {
        k: {"config_value": cfg[k], "cli_value": v}
        for k, v in effective.items()
        if k in cfg and cfg[k] != v
    }

    return {
        "timestamp":        datetime.now().isoformat(timespec="seconds"),
        "command":          " ".join(argv),
        "config_file":      config_path,
        "effective_config": {**cfg, **effective},
        "cli_overrides":    cli_overrides,
    }
