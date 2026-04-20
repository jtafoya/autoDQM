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
test_seed            Random seed for reproducible test-mode sampling.
max_subrun_plots     Number of subrun plot sets to generate per category in the
                     pipeline plots step. Produces up to max_subrun_plots random
                     bad subruns (always including the worst/most anomalous) and
                     up to max_subrun_plots random good subruns (n_bad below
                     file_alert_n_channels). -1 = no limit (plots every file —
                     can be very slow and disk-heavy for large runs; a prominent
                     warning is printed).

Full-sample training (--read-full-sample mode)
----------------------------------------------
These keys control training on the complete slab dataset stored on EOS.

full_sample_slab_dir  Root directory of the slab dataset on EOS.  Files are
                      organised in sub-directories named by the floor-100 of the
                      run number (e.g. run 1214 → .../slab/1200/).
full_sample_json      Path to the JSON good-runs catalogue
                      (goodRunsListSlab.json).  The file must contain a top-level
                      "data" list whose rows follow the column order:
                      [run, file, goodRunLoose, goodRunMedium, goodRunTight,
                       goodSingleTrigger, tag].
full_sample_train_quality  Default quality level for training when --read-full-sample
                           is active.  Accepted values: Loose, Medium, Tight, All
                           (OR of the three quality columns).  Can be overridden at
                           runtime with --full-sample-train-quality.
full_sample_train_fraction Fraction of the quality-filtered catalogue to use for
                           training (0 < value ≤ 1).  A value < 1 draws a random
                           sub-sample; set to 1.0 to use all matching entries.
full_sample_apply_quality  Default quality level for the apply step when
                           --read-full-sample-apply is active.  Same accepted values
                           as full_sample_train_quality.  Can be overridden at runtime
                           with --full-sample-apply-quality.
full_sample_apply_fraction Fraction of the quality-filtered catalogue to use for the
                           apply step (0 < value ≤ 1).  Defaults to 1.0 (score all
                           matching files).
"""

import yaml
from pathlib import Path

# Hardcoded fallback defaults — used only when a key is absent from config.yaml.
# These are intentionally conservative relative paths so the code stays runnable
# without any config file; the real site-specific values live in config.yaml.
DEFAULTS: dict = {
    "data_path":            "../data",
    "good_list":            "../data/good_run_list_EOS.txt",
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
    #
    "poll_interval":        5.0,
    "test_seed":            42,
    #
    ### Full-sample training
    "full_sample_slab_dir":  "/eos/experiment/milliqan/run3_MilliMon/slab",
    "full_sample_json":      "../data/goodRunsListSlab.json",
    #"full_sample_train_quality":   "Loose",
    "full_sample_train_quality":   "Medium",
    #"full_sample_train_quality":   "Tight",
    #"full_sample_train_quality":   "All",
    "full_sample_train_fraction":  0.01,
    #"full_sample_train_fraction":  1.0,
    "full_sample_apply_quality":   "Medium",
    "full_sample_apply_fraction":  1.0,
}


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


def load_config(path: str = "config.yaml") -> dict:
    """
    Load configuration from a YAML file, merged on top of DEFAULTS.

    If the file does not exist, returns a copy of DEFAULTS unchanged.
    Unknown keys in the file are passed through (scripts ignore what they
    don't use, so adding new keys never breaks old scripts).
    """
    cfg = dict(DEFAULTS)
    p = Path(path)
    if p.exists():
        with open(p) as fh:
            cfg.update(yaml.safe_load(fh))
    return cfg
