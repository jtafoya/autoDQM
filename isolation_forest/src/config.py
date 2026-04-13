"""
Central configuration loader for the autoDQM isolation-forest pipeline.

All scripts read config.json (or a path given via --config) at startup and use
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
file_alert_threshold Fraction of anomalous channels that triggers a file ALERT.
poll_interval        Seconds between directory scans in watch mode.
test_seed            Random seed for reproducible test-mode sampling.
"""

import json
from pathlib import Path

# Hardcoded fallback defaults — used only when a key is absent from config.json.
# These are intentionally conservative relative paths so the code stays runnable
# without any config file; the real site-specific values live in config.json.
DEFAULTS: dict = {
    "data_path":            "../data",
    "good_list":            "../data/good_run_list_EOS.txt",
    "apply_list":           "../data/all_run_list_EOS.txt",
    "model_tag":            "default",
    "models_dir":           "models",
    "logs_dir":             "logs",
    "reports_dir":          "reports",
    "plots_dir":            "plots",
    "use_trigger":          True,
    "use_lvds":             True,
    "z_threshold":          5.0,
    "if_contamination":     0.05,
    "file_alert_threshold": 0.001,
    "poll_interval":        5.0,
    "test_seed":            42,
    "ignore_features":      [],
}


def print_banner(script: str, config_path: str, fields: list[tuple[str, str]]) -> None:
    """
    Print a startup banner showing the config file and effective runtime values.

    Parameters
    ----------
    script      : short script name shown in the header, e.g. "pipeline"
    config_path : path to the JSON config file that was loaded
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


def load_config(path: str = "config.json") -> dict:
    """
    Load configuration from a JSON file, merged on top of DEFAULTS.

    If the file does not exist, returns a copy of DEFAULTS unchanged.
    Unknown keys in the file are passed through (scripts ignore what they
    don't use, so adding new keys never breaks old scripts).
    """
    cfg = dict(DEFAULTS)
    p = Path(path)
    if p.exists():
        with open(p) as fh:
            cfg.update(json.load(fh))
    return cfg
