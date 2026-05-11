# isolation_forest

Automated per-channel anomaly detection for MilliQan slab Digitizer data.  
Part of the [autoDQM](https://arxiv.org/pdf/2501.13789) framework.

---

## Overview

Each Digitizer CSV file contains ~1000 events in long format (one row per event × channel).  
This system processes each file as it arrives, compares per-channel statistics against a
reference built from known-good runs, and logs any channels that deviate from nominal behaviour.

Detection uses two complementary layers:

| Layer | Method | Catches |
|---|---|---|
| 1 | Statistical z-score | Individual feature drift > 5σ from reference (noisy/dead channels, gain shifts, timing jumps) |
| 2 | Isolation Forest | Multivariate anomalies: combinations of features that break nominal correlation structure, including novel failure modes not seen in training |

A channel is flagged if **either** layer triggers.

To suppress single-file fluctuations, the pipeline distinguishes two levels of anomaly:

| Level | Condition | Status |
|---|---|---|
| **Persistent** | channel anomalous in the current file **and** every one of the `alert_consecutive_n − 1` preceding files **within the same run** | counts toward ALERT |
| **Transient** | channel anomalous now but streak incomplete | counts toward WARN only |

**Channel history is reset at every run boundary.** A helper `_run_number()` extracts the run number from the filename; when it changes, the streak counters are cleared. Clean files always print `[OK]` immediately — there is no probationary hold for nominal subruns. A subrun with only transient anomalies (streak not established) also prints `[OK]`; `[WARN]` fires only when at least one channel has a confirmed sub-threshold persistent anomaly. In the plots, subruns in runs that are too short for persistence to ever be verified (fewer than `alert_consecutive_n` subruns total) are labelled `PEND` retrospectively.

Three independent conditions can raise `[ALERT]`:

| Condition | Config key | Rationale |
|---|---|---|
| **Persistent** | `file_alert_n_channels` | ≥ N channels each anomalous in `alert_consecutive_n` consecutive files. Can be low (e.g. 2) because persistence already suppresses transient noise. |
| **Bulk** | `single_file_alert_n_channels` | ≥ K anomalous channels in a single file. Targets sudden widespread events (power glitch, noisy run). No history required; set higher than `file_alert_n_channels` (e.g. 5) since there is no persistence filter. 0 = disabled. |
| **Extreme** | `single_file_alert_max_z` | Any single channel's `max_z` ≥ this value. Targets a catastrophically out-of-range channel (e.g. broken hardware). 0.0 = disabled. |

Setting `alert_consecutive_n = 1` disables the persistence check and restores single-file behaviour (every anomalous channel is immediately persistent).

---

## Directory structure

```
isolation_forest/
  src/
    config.py        — central config loader (load_config, DEFAULTS)
    args.py          — shared argparse helpers (preparse_config, add_* argument groups)
    features.py      — per-channel feature extraction; applies config-driven normalisations
                        (prescale normalisation, channel masking) before training/scoring
    run_config.py    — per-run MilliDAQ config parser (Run{N}TriggerDefault.py,
                        Run{N}DAQDefault.py, thresholds.json); regex-based, no import needed
    reference.py     — Welford online reference model (incremental, scalable)
    detector.py      — two-layer anomaly detector (z-score + Isolation Forest)
    run_list.py      — run list file parser and filename utilities (glob expansion, extract_run_number)
    train.py         — CLI: build/update reference and train Isolation Forest
    monitor.py       — CLI: watch a directory for new files and log anomalies
    combine.py       — combine per-run apply outputs into a single log (--combine-specific-run-outputs)
    report.py        — CLI: classify runs from the anomaly log (good / partial / bad)
    plot.py          — CLI: generate diagnostic plots for training and detection output
    evaluate.py      — CLI: evaluate TP/FP/TN/FN against goodRunsListSlab.json; writes framework_good_runs.json
    pipeline.py      — CLI: run the full pipeline (train → apply → evaluate → report → plots) in one command
  condor/
    submit.sub       — HTCondor job description (4 feature-variant jobs)
    run_pipeline.sh  — worker-node entry point (calls pipeline.py)
    logs/            — per-job stdout/stderr and shared job event log
  models/            — saved reference stats and trained Isolation Forest (created by train.py); each tag subdirectory also contains a config.yaml snapshot of the settings used for that training run
  logs/              — anomaly log CSV files (created by monitor.py / pipeline.py)
  reports/           — run quality lists and summary table (created by report.py / pipeline.py)
  plots/             — diagnostic figures (created by plot.py / pipeline.py)
  config.yaml        — central pipeline configuration (paths, thresholds, feature flags)
  setup.sh           — install Python dependencies
  diagram.md         — Mermaid architecture diagram of the full framework
  ../data/
    good_run_list_EOS.txt    — known-good files used for training (default --good-list)
    bad_run_list_EOS.txt     — known-bad files (for reference and validation)
    all_run_list_EOS.txt     — all classified runs combined (good + bad); default --apply-list
    goodRunsListSlab.json    — full good-runs catalogue for the slab dataset on EOS
                               (used by --train-goodRunList; path set by goodRunsList_json in config)
  requirements.txt   — Python dependencies
```

---

## Setup

### 1. Configure

`config.yaml` is the single source of truth for all pipeline settings. Edit it
before running anything else:

```yaml
data_path:  /afs/.../data
good_list:  /afs/.../data/good_run_list_EOS.txt
apply_list: /afs/.../data/all_run_list_EOS.txt
models_dir: /afs/.../isolation_forest/models
# ...
```

All paths must be **absolute** so the pipeline works from Condor worker nodes, cron jobs,
or any working directory. CLI arguments always override config.yaml values.

### 2. Install Python dependencies

```bash
bash setup.sh
```

This installs `pandas`, `scikit-learn`, `numpy`, `scipy`, `watchdog`, and `pyyaml` into your user
site-packages (`--user`, no root needed). Works on lxplus/AFS.

Verify:
```bash
python3 -c "import pandas, sklearn, numpy, scipy, watchdog, yaml; print('OK')"
```

---

## Workflow

All commands must be run from the **`isolation_forest/`** directory:

```bash
cd autoDQM/isolation_forest/
```

### 0. Full pipeline (recommended)

Run all steps — train, apply, report, and plots — with a single command.
Both `--good-list` and `--apply-list` default to the EOS run lists, so the
minimal invocations are:

```bash
# Quick end-to-end test (50 random training files, 50 random apply files)
python3 -m src.pipeline --test-train --test-apply

# Custom sample size
python3 -m src.pipeline --test-train 100 --test-apply 50

# Full production run (all files)
python3 -m src.pipeline

# Digitizer-only mode (exclude TriggerBoard features)
python3 -m src.pipeline --test-train --test-apply --no-trigger
```

See [Pipeline](#pipeline) for the full options table. The steps below describe how to run
each stage individually when finer control is needed.

### 1. Edit the run lists

Three run list files live in `../data/`:

| File | Purpose |
|---|---|
| `good_run_list_EOS.txt` | Known-good files used to build the reference model and train the IF |
| `bad_run_list_EOS.txt` | Known-bad files (validation only — never used in training) |
| `all_run_list_EOS.txt` | Good + bad combined; used as the apply list for end-to-end validation |

Each non-empty, non-comment line is a **glob pattern** resolved from the `isolation_forest/` directory:

```
# ../data/good_run_list_EOS.txt
/eos/user/t/tafoyava/autoDQM/data/Digitizer_run1637_subrun[1-9].csv
/eos/user/t/tafoyava/autoDQM/data/Digitizer_run1644_subrun*.csv
../data/noisy_channel__AfterFix/Digitizer_run2082_subrun*.csv
```

Lines starting with `#` and blank lines are ignored.

### 2. Train

Build the reference model and train the Isolation Forest.
`--good-list` defaults to `../data/good_run_list_EOS.txt`:

```bash
# Quick test (50 random files)
python3 -m src.train --test

# Custom sample size
python3 -m src.train --test 100

# Full training (all files from the default good run list)
python3 -m src.train

# Digitizer-only mode (no TriggerBoard features)
python3 -m src.train --no-trigger

# Disable LVDS pin count features
python3 -m src.train --no-trigger-LVDS
```

#### Full-sample training (complete slab dataset on EOS)

Use `--train-goodRunList` to train on the complete slab dataset instead of the
default text run list.  The good-run catalogue `goodRunsListSlab.json` is read
automatically (path set by `goodRunsList_json` in `config.yaml`).

The quality level and fraction are read from `config.yaml` (`train_goodRunList_quality`
and `train_goodRunList_fraction`) — no extra flags are required at the command line.
Both can be overridden per-run with `--train-goodRunList-quality` and
`--train-goodRunList-fraction`:

```bash
# Train using the quality and fraction defined in config.yaml (default: Medium, 1.0)
python3 -m src.train --train-goodRunList

# Override quality for this run only
python3 -m src.train --train-goodRunList --train-goodRunList-quality Loose
python3 -m src.train --train-goodRunList --train-goodRunList-quality Tight
python3 -m src.train --train-goodRunList --train-goodRunList-quality All

# Use only a random 20 % of the catalogue (reproducible via --test-seed)
python3 -m src.train --train-goodRunList --train-goodRunList-fraction 0.2

# Restrict to a run-number window (applied after quality filtering, before fraction sub-sampling)
python3 -m src.train --train-goodRunList --train-goodRunList-min-run 1600
python3 -m src.train --train-goodRunList --train-goodRunList-min-run 1600 --train-goodRunList-max-run 1800
```

Statistics about the catalogue (total entries, unique runs, per-quality counts,
post-filter counts, and post-sampling counts) are printed at startup.

This creates:
- `models/reference.npz` — per-channel Welford statistics (mean, variance, count)
- `models/detector.pkl` — trained Isolation Forest
- `models/seen_files.json` — list of files already incorporated into the reference
- `models/config.yaml` — snapshot of the config file used for this training run (overwritten on every retrain)

The `use_trigger` and `use_lvds` settings are saved into `reference.npz` so all subsequent
steps (apply, plots) automatically use the same feature set.

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--config` | `config.yaml` | Path to YAML configuration file |
| `--good-list` | from config.yaml | Path to the good run list file |
| `--models-dir` | from config.yaml | Where to save the trained models |
| `--z-threshold` | from config.yaml | σ threshold for the statistical layer |
| `--if-contamination` | from config.yaml | Expected anomaly fraction for Isolation Forest |
| `--if-n-estimators` | from config.yaml (200) | Number of trees in the Isolation Forest ensemble. More trees → more stable scores, slower training |
| `--if-max-samples` | from config.yaml (`auto`) | Samples drawn per tree (`auto` = `min(256, n_samples)`). Higher values increase score stability but raise memory usage |
| `--if-max-features` | from config.yaml (1.0) | Fraction of features considered at each split (sklearn `max_features`). `1.0` = all features |
| `--no-trigger` | off | Exclude TriggerBoard features (overrides `use_trigger` in config.yaml) |
| `--no-trigger-LVDS` | off | Exclude LVDS features: drops `LVDSpin` and the `"trigger_lvds_total"` pseudo-channel (overrides `use_lvds`) |
| `--no-trigger-config` | off | Disable per-run trigger config integration (prescale normalisation, channel masking). Overrides `includeConfigInfo_Trigger`. Appends `_ignoreTriggerConfig` to the model tag |
| `--no-daq-config` | off | Disable DAQ config integration. Overrides `includeConfigInfo_DAQ`. Appends `_ignoreDAQConfig` to the model tag |
| `--update` | off | Incremental mode: add new good files without reprocessing old ones |
| `--test [N]` | off | Test mode: randomly sample N files (default N=50 when flag is given) |
| `--test-seed` | from config.yaml | Random seed for reproducible test-mode sampling |
| `--train-goodRunList` | off | Train on the complete slab dataset on EOS instead of the default good run list |
| `--train-goodRunList-quality` | from config.yaml | Quality filter: `Loose`, `Medium`, `Tight`, or `All` (OR of all three). Override the config default for a single run |
| `--train-goodRunList-fraction` | from config.yaml | Fraction of the quality-filtered catalogue to use (0 < F ≤ 1). `1.0` = use all entries |
| `--train-goodRunList-min-run` | none (no lower bound) | Lowest run number (inclusive) to include when training from the catalogue. Applied after quality filtering and before fraction sub-sampling |
| `--train-goodRunList-max-run` | none (no upper bound) | Highest run number (inclusive) to include when training from the catalogue. Applied after quality filtering and before fraction sub-sampling |
| `--plot-format` | from config.yaml (`png`) | Output format for the mean feature table figure: `png`, `pdf`, or `svg`. Use `pdf` for vector output |

### 3. Monitor

Watch a directory for new `Digitizer_*.csv` files and log anomalies.
The feature set (with or without trigger info) is read from the saved model automatically:

```bash
python3 -m src.monitor --watch-dir /eos/experiment/milliqan/run3/slab/live/
```

To also auto-generate diagnostic plots for every alerted file and refresh log summary plots periodically:

```bash
python3 -m src.monitor \
  --watch-dir /eos/experiment/milliqan/run3/slab/live/ \
  --plot-alerts \
  --refresh-log-plots-every 50
```

To accumulate confirmed good subruns into a live good-run list for incremental training:

```bash
python3 -m src.monitor \
  --watch-dir /eos/experiment/milliqan/run3/slab/live/ \
  --live-good-list data/live_good_runs.txt
```

Subruns that do not trigger an alert are written to `live_good_runs.txt` in the same
plain-text format as `good_run_list_EOS.txt`, ready for incremental training
(see [Scaling](#scaling-to--106-files)).

**Probationary period** (live-good-list only): subruns with transient anomalies (`n_bad > 0` but no alert) are held in a per-run queue rather than written immediately. They are flushed (written retroactively) only when the first non-probationary passing subrun arrives — i.e. the first subrun for which the persistence window is complete and no alert fires. An alert during probation clears the queue; those subruns are discarded. **Clean subruns (`n_bad = 0`) and purely-transient subruns (streak not established) are written immediately** — no hold applies. When `alert_consecutive_n = 1` there is no probationary period.

To apply the model to a run list instead of a live directory (test mode only):

```bash
python3 -m src.monitor \
  --run-list ../data/all_run_list_EOS.txt \
  --test 20
```

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--config` | `config.yaml` | Path to YAML configuration file |
| `--watch-dir` | (one of these required) | Directory to watch for new CSV files |
| `--run-list` | (one of these required) | Run list file; requires `--test N`; processes N random files then exits |
| `--models-dir` | from config.yaml | Directory with saved models |
| `--log-file` | from config.yaml | Output log path |
| `--poll-interval` | from config.yaml | Seconds between directory scans |
| `--file-alert-n-channels` | from config.yaml | Number of *persistent* anomalous channels needed to print `[ALERT]` (persistence condition) |
| `--alert-consecutive-n` | from config.yaml | A channel must be anomalous in this many consecutive files to count as persistent. Set to `1` to disable (any anomaly → ALERT-eligible) |
| `--single-file-alert-n-channels` | from config.yaml | Minimum anomalous channels in a single file to trigger `[ALERT]` (bulk condition). Should be higher than `--file-alert-n-channels`. `0` = disabled |
| `--single-file-alert-max-z` | from config.yaml | If any channel's `max_z` meets or exceeds this value, trigger `[ALERT]` immediately (extreme condition). `0.0` = disabled |
| `--process-existing` | off | Also process files already in the directory at startup |
| `--plot-alerts` | off | Auto-generate 4 diagnostic plots for every alerted file, saved to `plots-dir/alerts/<stem>/` |
| `--plots-dir` | from config.yaml | Root directory for all plot output |
| `--refresh-log-plots-every` | `0` | Regenerate log summary plots every N processed files (0 = disabled) |
| `--live-good-list` | off | Path to a live good-run list file. Subruns that do not trigger an alert are written here (same plain-text format as `--good-list`). Probationary subruns (first `alert_consecutive_n − 1` of each run) are held and flushed retroactively when the persistence window is confirmed; an alert during probation discards them. To change what counts as "good", edit `_subrun_quality_verdict()` in `monitor.py` |
| `--test [N]` | off | Test mode: randomly sample N files from the source (watch-dir or run-list), process them, then exit |
| `--test-seed` | from config.yaml | Random seed for reproducible test-mode sampling |
| `--plot-format` | from config.yaml (`png`) | Output format for `--plot-alerts` diagnostic plots and log-summary refreshes: `png`, `pdf`, or `svg` |

Terminal output (with `alert_consecutive_n = 3`, `single_file_alert_n_channels = 5`, `single_file_alert_max_z = 15.0`):
```
[run 2090] New run — channel history reset
[OK]    2026-04-08T17:00:00Z  Digitizer_run2090_subrun1.csv  —  96 channels, all nominal
[OK]    2026-04-08T17:00:05Z  Digitizer_run2090_subrun2.csv  —  96 channels, all nominal
[OK]    2026-04-08T17:00:10Z  Digitizer_run2090_subrun3.csv  —  96 channels, all nominal
[OK]    2026-04-08T17:00:15Z  Digitizer_run2090_subrun4.csv  —  2 transient anomalous channel(s), streak not established  [window: 3 files]
                  ch1  method=statistical+IF        max_z=8.2    if_score=-0.59   features=[nPulses_std;occupancy]  [1/3 files]
                  ch3  method=statistical           max_z=6.4    if_score=-0.41   features=[sideband_mean_median]   [1/3 files]
[WARN]  2026-04-08T17:00:20Z  Digitizer_run2090_subrun5.csv  —  2 persistent anomalous channel(s)  [window: 3 files, need 2 persistent for ALERT]
                  ch1  method=statistical+IF        max_z=8.2    if_score=-0.59   features=[nPulses_std;occupancy]  [2/3 files]
                  ch3  method=statistical           max_z=6.4    if_score=-0.65   features=[sideband_mean_median]   [2/3 files]
[ALERT] 2026-04-08T17:00:25Z  Digitizer_run2090_subrun6.csv  —  2 persistent + 1 transient anomalous channel(s)  (window: 3 files)  |  bulk: 6 channels ≥ 5 threshold
                  ch1  method=statistical+IF        max_z=8.2    if_score=-0.59   features=[nPulses_std;occupancy]  [3/3 files]
                  ch3  method=statistical           max_z=6.4    if_score=-0.65   features=[sideband_mean_median]   [3/3 files]
                 ch57  method=isolation_forest      max_z=4.1    if_score=-0.71   features=[]                       [1/3 files]
```

`[OK]` is immediate for clean subruns and for subruns whose only anomalies are transient (streak not established). `[WARN]` fires when at least one channel has a confirmed sub-threshold persistent anomaly. With `alert_consecutive_n = 1` (persistence check disabled) the `[k/N files]` annotations are omitted and the output matches the original single-file format.

### 4. Classify runs

After processing files with the monitor, summarise run quality from the anomaly log:

```bash
python3 -m src.report
```

Reads the log for the active `model_tag` (from `config.yaml`) and writes into the corresponding reports directory:

| File | Description |
|---|---|
| `good_runs.txt` | Runs where every subrun is nominal |
| `partial_good_runs.txt` | Runs that start nominal then transition to anomalous, with the last good and first bad subrun noted |
| `persistent_fault_runs.txt` | Runs with one or more channels anomalous in every subrun (systematic fault below the per-file threshold) |
| `run_summary.csv` | Full per-run breakdown (all categories), including a `persistent_channels` column |

Runs are classified as:

| Classification | Meaning |
|---|---|
| `good` | All subruns below the alert threshold, no persistent channel faults |
| `partial` | At least one good subrun followed by at least one bad subrun (clean transition) |
| `bad` | All subruns above the alert threshold |
| `mixed` | Good and bad subruns interleaved with no clean transition |
| `persistent_fault` | All subruns appear nominal by the per-file threshold, but one or more channels are anomalous in every subrun — e.g. a dead or missing channel that never triggers enough to reach the alert count on its own |

> **`persistent_fault` guard:** requires at least **2 subruns** in the log for the run.
> A run with only 1 subrun trivially satisfies "anomalous in every subrun" (1/1),
> which would produce false positives when sampling a sparse test set.

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--config` | `config.yaml` | Path to YAML configuration file |
| `--log-file` | from config.yaml (`<logs_dir>/<tag>.csv`) | Anomaly log to read |
| `--out-dir` | from config.yaml (`<reports_dir>/<tag>`) | Directory to write output files |
| `--file-alert-n-channels` | from config.yaml | Number of anomalous channels that marks a subrun as bad (must match the value used in monitor.py) |

### 5. Evaluate (TP/FP/TN/FN against ground truth)

Compare the detector's per-subrun predictions against the goodRunsListSlab.json catalogue
to measure false positive and detection rates.  In the pipeline, the evaluate step runs
automatically after apply when `--train-goodRunList` is set, using `--train-goodRunList-quality`
as the ground truth level (Loose/Medium/Tight).  It is silently skipped when
`--train-goodRunList` is not active.

The standalone CLI accepts an explicit quality flag:

```bash
python3 -m src.evaluate \
    --log-file logs/myrun_Tight.csv \
    --json-path /path/to/goodRunsListSlab.json \
    --out-dir reports/myrun_Tight/ \
    --plots-dir plots/myrun_Tight/ \
    --gt-quality Tight
```

Each subrun in the log is looked up in the catalogue and assigned a ground-truth category:

| Category | Meaning |
|---|---|
| `known_good` | In catalogue with at least one quality flag set at the chosen level |
| `not_certified` | In catalogue but all quality flags = 0 (not certified good or bad) |
| `unknown` | Not found in catalogue at all |

Predicted status comes from replaying the full alert logic (persistence + bulk + extreme)
on the log. Combining ground truth and prediction yields:

| | predicted ok | predicted warn | predicted pend | predicted alert |
|---|---|---|---|---|
| known good | TN ✓ | mild anomaly | unconfirmed | FP ✗ |
| not certified | possible FN | mild | unconfirmed | possible TP |
| unknown | (shown separately) | | | |

Outputs written to `<out_dir>/` and `<plots_dir>/`:

| File | Description |
|---|---|
| `eval_summary.txt` | Printed table of counts and rates per ground-truth category |
| `eval_confusion.<fmt>` | Stacked bar chart: predicted status (ok/warn/pend/alert) per ground-truth category. Format set by `--plot-format` (default `png`) |
| `framework_good_runs.json` | JSON in `goodRunsListSlab` column order — every subrun in the log with framework quality flags: Tight=ok only, Medium=ok+warn, Loose=ok+warn+pend, 0/0/0=alert |

The `framework_good_runs.json` can be loaded directly by the same `resolve_full_sample` function
used for training, treating the framework's prediction as an alternative quality catalogue.

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--log-file` | from config.yaml | Anomaly log to read |
| `--json-path` | from config.yaml (`goodRunsList_json`) | Path to goodRunsListSlab.json |
| `--out-dir` | from config.yaml | Directory for `eval_summary.txt` and `framework_good_runs.json` |
| `--plots-dir` | from config.yaml | Directory for `eval_confusion.png` |
| `--gt-quality` | `Tight` | Quality level used to define "known good" ground truth |
| `--file-alert-n-channels` | from config.yaml | Persistent alert threshold |
| `--alert-consecutive-n` | from config.yaml | Persistence window |
| `--single-file-alert-n-channels` | from config.yaml | Bulk alert threshold |
| `--single-file-alert-max-z` | from config.yaml | Extreme alert threshold |
| `--plot-format` | from config.yaml (`png`) | Output format for `eval_confusion.<fmt>`: `png`, `pdf`, or `svg` |

### 6. Plot

Generate diagnostic figures after training or after processing files:

```bash
# Reference model statistics
python3 -m src.plot reference

# Anomaly analysis of a single file
python3 -m src.plot file <path/to/Digitizer_runXXXX_subrunY.csv>

# Summary of the anomaly log
python3 -m src.plot log
```

Defaults for `--out-dir`, `--models-dir`, and `--log-file` are all derived from `config.yaml` (using `<base_dir>/<model_tag>`). Pass `--config` to switch configs, or override individual paths explicitly — both flags must appear **before** the subcommand:

```bash
python3 -m src.plot --config config_bad.yaml reference
python3 -m src.plot --out-dir /tmp/myplots --models-dir models/myrun reference

# Save all figures as PDF for lossless zooming
python3 -m src.plot --plot-format pdf reference
python3 -m src.plot --plot-format pdf log
```

`--plot-format` accepts `png` (default), `pdf`, or `svg` and applies to every figure produced by the subcommand. The default can be set permanently in `config.yaml` under `plot_format`.

See the [Plots](#plots) section for descriptions of each figure.

---

## Log format

`logs/anomalies.csv` is append-only. One row per channel per file:

| Column | Description |
|---|---|
| `timestamp` | UTC time the file was processed (ISO-8601) |
| `filename` | Base name of the Digitizer CSV |
| `channel` | Integer channel ID for digitizer channels, or `"trigger_rate"` / `"trigger_lvds_total"` for pseudo-channels |
| `anomalous` | `True` / `False` |
| `method` | `statistical`, `isolation_forest`, `statistical+IF`, `new_channel`, `missing_channel`, or `""` |
| `triggered_features` | Semicolon-separated feature names with \|z\| > threshold |
| `max_z` | Largest absolute z-score across all features for this channel |
| `if_score` | Isolation Forest anomaly score (more negative = more anomalous) |

---

## Plots

Figures are generated by `src/plot.py`. Default output directory, models directory, and log file are all read from `config.yaml`. All subcommands accept `--config`, `--models-dir`, and `--out-dir` to override defaults.

File names below are shown with the `.png` default extension. Pass `--plot-format pdf` (or `svg`) to any script or set `plot_format: pdf` in `config.yaml` to produce vector output instead — all file suffixes are substituted automatically.

When running the monitor with `--plot-alerts`, diagnostic plots for alerted files are saved
automatically into subdirectories, one per file:

```
plots/
  alerts/
    Digitizer_run2068_subrun1/     ← one directory per alerted file
      zscore_heatmap.png
      max_zscore.png
      if_scores.png
      geometry.png
    Digitizer_run2071_subrun3/
      ...
  log_anomaly_rate.png             ← log summary (refreshed with --refresh-log-plots-every N)
  log_channel_frequency.png
  log_feature_frequency.png
  log_run_summary.png
  log_persistence_subrun_grid.png  ← persistence-aware subrun heatmap
  log_persistence_run_summary.png  ← persistence-aware run quality bar chart
```

Good files and files below the alert threshold generate no plots, keeping storage proportional
to the number of anomalies rather than the total number of files processed.

### Reference plots

```bash
python3 -m src.plot reference
```

| File | Description |
|---|---|
| `reference_means.png` | Heatmap of per-channel reference means, column-normalised to z-scores so all features share a common colour scale. Shows the nominal state of each channel across all features, including trigger rates at the bottom (when trigger features are enabled). |
| `reference_stds.png` | Heatmap of reference uncertainties (log-normalised σ). Bright cells indicate features with high run-to-run variability; these contribute less to anomaly detection. |
| `reference_coverage.png` | Bar chart of how many training files each channel appeared in. Channels with low coverage have less reliable reference statistics. |
| `reference_mean_table.png` | Full channels × features table of raw mean values. Colour is per-column min→max so each feature's variation across channels is visible regardless of scale. Cell text shows the actual mean value. Pseudo-channels (`trigger_rate`, `trigger_lvds_total`) appear at the bottom separated by a dashed line; cells that are not applicable to a row (e.g. trigger columns for digitiser channels) are shown in grey. **Generated automatically after every training run** and saved alongside the model files in `models/<tag>/`. |

### Single-file analysis plots

```bash
python3 -m src.plot file <path/to/Digitizer_runXXXX_subrunY.csv>
```

| File | Description |
|---|---|
| `<stem>_zscore_heatmap.png` | Full channels × features z-score matrix, clamped at 50σ. Same layout as `reference_mean_table.png`: digitiser channels (`ch0`–`ch95`) ordered numerically top to bottom, pseudo-channels (`trigger_rate`, `trigger_lvds_total`) below a dashed separator, cell text showing the actual \|z\| value, grey cells for features not applicable to that row (including masked channels when config integration is active). Red shading highlights flagged channels. |
| `<stem>_max_zscore.png` | Bar chart of the maximum absolute z-score per channel (log scale), channels ordered numerically with pseudo-channels at the right. The dashed line marks the alert threshold. Red bars are flagged channels, blue are nominal. |
| `<stem>_if_scores.png` | Isolation Forest anomaly score per channel, same channel ordering. More negative = more anomalous. Complements the z-score plot by capturing multivariate anomalies not visible in any single feature. |
| `<stem>_geometry.png` | Detector layout plot: one panel per layer (all 4 layers in a single row), channels placed at their (row, column) position and coloured by max \|z\|. Each channel also gets a status ring: 🟢 green = OK (nominal), 🟡 yellow = WARN (anomalous but no alert condition fired), 🔴 red = ALERT (bulk or extreme condition triggered). Useful for spotting spatially localised problems (e.g. a dead row or noisy column). |

The following three figures are generated automatically when `includeConfigInfo_Trigger: true`:

| File | Description |
|---|---|
| `<stem>_config_trigger.png` | Side-by-side bars for trigger types 1–13: **blue** = raw rate from TriggerBoard CSV, **orange** = prescale-normalised rate (what the model sees), **grey** = disabled by `triggerBoard.trigger`. The ÷N prescale factor is annotated above each active trigger. Directly shows the effect of prescale normalisation for this subrun. |
| `<stem>_config_zscore_comparison.png` | Two |z|-score heatmaps side by side for all channels × features. **Left panel**: raw (un-normalised) features scored against the reference — shows what would happen without config integration (potential false positives highlighted). **Right panel**: config-normalised features (what the model actually used). Grey cells in the right panel are masked channels or disabled triggers correctly excluded from scoring. Large |z| values that appear only in the left panel are false positives that config normalisation suppresses. |
| `<stem>_config_mask.png` | Detector geometry per layer showing channel mask state. **Grey ×** = channel silenced by `triggerBoard.trigger_mask` (all features NaN'd, excluded from reference and scoring). **Blue/red dots** = active nominal/anomalous channels. Only generated when at least one channel is actually masked in this subrun. |

### Log summary plots

```bash
python3 -m src.plot log
```

Files are ordered by **run number then subrun number** in all log plots.

| File | Description |
|---|---|
| `log_anomaly_rate.png` | Anomalous channel count per file, sorted by run/subrun. Red bars = ALERT (any of the three alert conditions fired), orange = WARN (sub-threshold persistent anomaly), light-blue = PEND (anomalous, but run too short to verify persistence), steel-blue = OK (clean or purely transient). A second dashed threshold line marks the bulk single-file threshold. Each x-axis label is coloured to match its bar, so zero-count files remain visible. |
| `log_channel_frequency.png` | Bar chart of the 40 most frequently flagged channels across all processed files. Persistent entries point to channels with chronic issues rather than transient noise. |
| `log_feature_frequency.png` | Bar chart of the 20 most frequently triggered features. Identifies which metrics are driving alerts — useful for diagnosing systematic hardware problems (e.g. TDC drift, occupancy loss, trigger rate shifts). |
| `log_run_summary.png` | Bar chart with one bar per run showing what fraction of its subruns are non-ALERT (0–100%), based on raw per-file anomaly counts. Blue = all good, orange = partial, red = all bad. Each bar is annotated with the raw count. |
| `log_persistence_subrun_grid.png` | Heatmap of every (run, subrun) cell coloured by its persistence-aware status: blue = OK (clean, or transient anomaly in a long-enough run), light-blue = PEND (anomalous channel(s) in a run too short to verify persistence), orange = WARN (sub-threshold persistent anomaly), red = ALERT (any alert condition fired — persistent, bulk, or extreme). Grey = no data. |
| `log_persistence_run_summary.png` | Same as `log_run_summary.png` but subrun badness is determined by the full alert logic (persistent + bulk + extreme conditions): a subrun is counted as bad only if it reaches ALERT level. Runs with only transient spikes appear fully good here while showing anomalies in `log_run_summary.png`. |

Options for the `log` subcommand:

| Flag | Default | Meaning |
|---|---|---|
| `--log-file` | from config.yaml (`<logs_dir>/<tag>.csv`) | Anomaly log to read |
| `--file-alert-n-channels` | from config.yaml | Number of persistent anomalous channels that marks a file as ALERT — persistence condition (must match the value used in monitor.py) |
| `--alert-consecutive-n` | from config.yaml | Consecutive files a channel must be anomalous in to count as persistent (must match the value used in monitor.py) |
| `--single-file-alert-n-channels` | from config.yaml | Bulk alert threshold for replayed log colouring (must match the value used in monitor.py). `0` = disabled |
| `--single-file-alert-max-z` | from config.yaml | Extreme alert threshold for replayed log colouring (must match the value used in monitor.py). `0.0` = disabled |

---

## How it works in detail

### Feature extraction (`src/features.py`)

Each file is compressed from ~8000 rows to **one row per channel** by computing,
for each of the 11 numeric metrics, three aggregations across all events:

```
{metric}_{mean | std | median}   →  33 features
occupancy                        →  fraction of events where this channel fired
frac_dead                        →  fraction of appearances with nPulses == 0
                                    ─────────────────────────────────────────
                                     35 Digitizer features per channel per file
```

By default, **LVDS pin counts** from the matching LVDSCounts CSV are added as a per-channel feature (disable with `--no-trigger-LVDS`):

```
LVDSpin                          →  1 feature,  LVDS count for the pin corresponding
                                                 to this channel  (pin = channel // 2)
                                    ─────────────────────────────────────────
                                     ch 0 & 1 share pin 0, ch 2 & 3 share pin 1, etc.
```

Trigger and run-level quantities are independent of individual digitizer channels and
are therefore represented as **pseudo-channel rows** appended to the feature DataFrame,
rather than being broadcast across every channel row.

**`"trigger_rate"` pseudo-channel** (added when `use_trigger=True`):

```
triggerRate_bit{1–13}            →  13 features, per-bit trigger rate in Hz
triggerRate_tot                  →  1 feature,  total trigger rate in Hz
triggerCounts_tot                →  1 feature,  total trigger count for the subrun
                                    ─────────────────────────────────────────
                                     15 TriggerBoard features; all other columns NaN
```

**`"trigger_lvds_total"` pseudo-channel** (added when `use_lvds=True`):

```
LVDStotal                        →  1 feature,  sum of all LVDS pin counts for the subrun
                                    ─────────────────────────────────────────
                                     1 feature; all other columns NaN
```

All rows (real channels and pseudo-channels) share the same column space. Columns that
are not applicable to a given row are `NaN`. The reference model and Isolation Forest
treat pseudo-channels exactly like real channels — each gets its own Welford statistics
and IF anomaly score.

**Total columns in the shared feature space (before `ignore_features`):**

| Mode | Columns |
|---|---|
| Default (trigger on, LVDS on) | 35 + 1 (LVDSpin) + 15 (trigger) + 1 (LVDStotal) = **52** |
| `--no-trigger-LVDS` | 35 + 15 = **50** |
| `--no-trigger` | 35 + 1 (LVDSpin) + 1 (LVDStotal) = **37** |
| `--no-trigger --no-trigger-LVDS` | **35** |

**`ignore_features`** (set in `config.yaml`) accepts a list of glob patterns that are
removed from the feature set at training time and automatically excluded at inference:

```yaml
ignore_features:
  - "TDCRollovers_*"
  - "triggerRate_bit1*"
```

Patterns use standard `fnmatch` syntax (`*` matches anything within a name). The
excluded columns are stored inside `reference.npz` so a loaded model always uses the
same feature set it was trained with — no need to repeat the patterns at apply time.
The `reference_mean_table.png` reflects only the active (non-ignored) features.

All TriggerBoard and LVDS files are located automatically from the Digitizer filename
in the same directory.

If a companion file is absent or the subrun entry is missing (e.g. the last few subruns
of a run are sometimes not recorded), the corresponding pseudo-channel row has all-`NaN`
values for that file. The reference model handles this gracefully — NaN entries are
skipped in the Welford update so they do not corrupt the running mean or variance.

Feature flags are saved in `models/reference.npz` and applied automatically by all
subsequent steps (apply, plots) — no flags needed at inference time.

### Per-run config integration (`src/run_config.py`, `src/features.py`)

Enabled by `includeConfigInfo_Trigger: true` in `config.yaml`.  Config files
(`Run{N}TriggerDefault.py`, `Run{N}DAQDefault.py`) are parsed once per subrun using
regex extraction — they cannot be imported since they reference custom MilliDAQ classes.

Config information is used **exclusively to transform observable features in-place**.
No new features are added; the feature space size is unchanged (52 columns by default).
This means the model never alerts because a configuration parameter changed between runs —
it alerts only when observables are inconsistent with the run's own configuration.

Three transformations are applied when the corresponding variable is listed in
`includeConfigVariables_Trigger`:

| Variable | Transformation |
|---|---|
| `triggerBoard.prescale` | `triggerRate_bit{N}` → `raw_rate / prescale[N-1]` (physics rate before prescaling). Runs with different prescale settings become directly comparable. |
| `triggerBoard.trigger` | `triggerRate_bit{N}` → NaN for disabled trigger types. A zero rate from an inactive trigger is expected, not anomalous. |
| `triggerBoard.trigger_mask` | All features for digitizer channels `2l` and `2l+1` → NaN when LVDS channel `l` is masked. The 8-byte mask is indexed by **physical pin number** (bit k of byte b → physical pin b·8+k). LVDS data channels are numbered **consecutively**, skipping dead physical pins 32–39 and 43 (the physical routing already omits them). LVDS channel `l` is therefore the l-th non-dead physical pin, **not** physical pin `l` itself. Example: physical pins 32–39 are dead → physical pin 40 (active in the default mask) becomes LVDS channel 32 → signal channels 64–65, not 80–81. The default mask `[0xff, 0xff, 0xff, 0xff, 0x00, 0xf7, 0xff, 0xc1]` has zero bits only for dead physical pins, so all 96 signal channels are active. |

When either config flag is False, behaviour is identical to the pre-config code path and
`_ignoreTriggerConfig` / `_ignoreDAQConfig` is appended to the model tag.

Config flags and variable lists are stored in `reference.npz` and `training_metadata.json`
so any loaded model is always self-describing.

```yaml
# config.yaml — enable all three trigger transformations
includeConfigInfo_Trigger: true
includeConfigVariables_Trigger:
  - "triggerBoard.trigger"
  - "triggerBoard.prescale"
  - "triggerBoard.trigger_mask"
includeConfigInfo_DAQ: true
includeConfigVariables_DAQ:
  - "channel.triggerThreshold"
run_configs_dir:       /eos/experiment/milliqan/run3/slab/configs
thresholds_json_path:  /eos/experiment/milliqan/run3/slab/configs/thresholds.json
```

Disable for a single run (tag suffix appended automatically):

```bash
python3 -m src.pipeline --no-trigger-config   # tag gets _ignoreTriggerConfig
python3 -m src.pipeline --no-daq-config       # tag gets _ignoreDAQConfig
```

### Reference model (`src/reference.py`)

Built from good-data files using **Welford's online algorithm**. For each
(channel, feature) pair it maintains three numbers — `count`, `mean`, `M2` — from
which the mean and standard deviation can be derived at any time. Adding a new file
costs O(channels × features) and never touches previously processed files.
NaN feature values (e.g. missing TriggerBoard entry) are masked out during the update
so a single file with missing data cannot corrupt the statistics for all subsequent files.

### Anomaly detector (`src/detector.py`)

**Two detection layers** run per channel for every file analyzed:

- **Statistical z-score**: flags channels where any feature deviates more than `z_threshold` σ from the reference mean
- **Isolation Forest**: flags multivariate anomalies that break the nominal correlation structure even without a large individual z-score

Channels are also flagged for two structural conditions:

- **`new_channel`**: channel appears in the file but was never seen in training — inherently suspicious
- **`missing_channel`**: channel is in the reference (fired reliably in training) but produces zero hits in this file — indicates a dead or disconnected channel

The IF is trained on **z-scored** feature vectors from good data, not raw values.
Z-scoring first makes the IF scale-invariant (channels at different detector positions
have different baseline values but similar nominal z-score distributions), and means
the IF learns *patterns of deviation* rather than memorising absolute scales.

**How the Isolation Forest works**: the algorithm builds an ensemble of random trees
that recursively split the feature space on randomly chosen features and split values.
Anomalous points — those that are sparse or far from the training distribution — are
isolated in fewer splits and receive a lower (more negative) `if_score`.  The score
ranges roughly from −0.5 (very anomalous) to 0 (deep inside the training distribution).
The decision boundary is set by `if_contamination`: the IF will always flag the top
`if_contamination` fraction of any scored dataset as anomalous, regardless of absolute
score values.  Lowering `if_contamination` is therefore the most direct lever for
reducing IF-driven false positives (see [Performance tuning](#performance-tuning)).
The number of trees (`if_n_estimators`, default 200), the per-tree sample count
(`if_max_samples`, default `"auto"` = `min(256, n_samples)`), and the feature fraction
per split (`if_max_features`, default 1.0) are all configurable via `config.yaml` or
the corresponding CLI flags.

Training data is capped at 50 000 channel-file vectors; beyond that,
a random subsample is drawn. This keeps training fast regardless of corpus size.

---

## Scaling to > 10^6 files

When the corpus of good runs grows, add the new patterns to `../data/good_run_list_EOS.txt`
and run training in incremental mode:

```bash
python3 -m src.train --update
```

`--update` reads `models/seen_files.json`, skips files already in the reference,
and folds in only the new ones. The Isolation Forest is always fully retrained
(it cannot be updated incrementally), but this is fast since training data is capped.

**Live deployment**: when the monitor is running with `--live-good-list`, the output file
accumulates confirmed good subruns automatically (probationary subruns are held and flushed
retroactively once the persistence window is confirmed — see `--live-good-list` above).
Pass it directly to `--good-list` for the next incremental training cycle:

```bash
python3 -m src.train --good-list data/live_good_runs.txt --update
```

As the reference improves with more files, per-channel mean and std estimates become
tighter and the Isolation Forest has a larger, more representative training set — the
false positive rate drops automatically. See [Performance tuning](#performance-tuning)
for guidance on threshold selection.

There is no hard limit on the number of files the reference can absorb — memory usage
is fixed at O(channels × features) regardless of how many files have been processed.

---

## Pipeline

`src/pipeline.py` runs all five steps — train, apply, evaluate, report, plots — in sequence with a single command.
Both `--good-list` and `--apply-list` default to the standard EOS run lists.

```bash
# Quick end-to-end test (50 random files each, default)
python3 -m src.pipeline --test-train --test-apply

# Custom sample sizes
python3 -m src.pipeline --test-train 100 --test-apply 50

# Full production run (all files)
python3 -m src.pipeline

# Digitizer-only mode
python3 -m src.pipeline --test-train --test-apply --no-trigger

# Disable LVDS pin count features
python3 -m src.pipeline --test-train --test-apply --no-trigger-LVDS

# Train on full slab dataset (quality and fraction from config.yaml), apply to default apply list
python3 -m src.pipeline --train-goodRunList --test-apply

# Override quality or fraction for a single run
python3 -m src.pipeline --train-goodRunList --train-goodRunList-quality Tight --test-apply
python3 -m src.pipeline --train-goodRunList --train-goodRunList-fraction 0.1 --test-apply

# Train and apply on the full slab dataset (independent quality/fraction per step)
python3 -m src.pipeline --train-goodRunList --read-full-sample-apply

# Train and apply on exactly the same files (guaranteed identical list)
python3 -m src.pipeline --train-goodRunList --apply-to-training-list
```

### Per-run apply mode (Condor array jobs over the full sample)

When the full-sample catalogue is too large to apply in a single job, each run can be
processed independently and the outputs combined afterwards.

`--apply-specific-run` combined with `--train-goodRunList` scans the slab directory on
disk for **every subrun** of the requested run (catalogue-independent — any run can be
targeted regardless of quality).  Use `--apply-specific-run-fraction` to score a random
fraction of that run's files (default 1.0 = all files); this is decoupled from
`--train-goodRunList-fraction`.  No `--read-full-sample-apply` flag is needed.

**Step 1 — train** (one job, as usual):
```bash
python3 -m src.pipeline \
  --train-goodRunList \
  --train-goodRunList-quality Tight \
  --train-goodRunList-fraction 0.001 \
  --skip-apply --skip-evaluate --skip-report --skip-all-plots
```

**Step 2 — apply per run** (one Condor job per run number, e.g. via a job array):
```bash
python3 -m src.pipeline \
  --train-goodRunList \
  --train-goodRunList-quality Tight \
  --train-goodRunList-fraction 0.001 \
  --skip-train --apply-specific-run $RUN_NUMBER
```
Each job scans the slab directory for all subruns of `$RUN_NUMBER` on disk and writes
`logs/<tag>_run<N>.csv` and `logs/<tag>_run<N>_paths.txt`.  No report or plots are produced.

**Step 3 — combine** (once all per-run jobs are done):
```bash
# Combine every per-run output
python3 -m src.pipeline --train-goodRunList --combine-specific-run-outputs '*'

# Or combine a subset (wildcards apply to the run number; missing files are skipped)
python3 -m src.pipeline --train-goodRunList --combine-specific-run-outputs '100?'
```
Writes `logs/<tag>.csv` and merges the companion `_paths.txt` caches.
The combined log's modification time is used as a watermark: any per-run file
newer than it is treated as uncombined.

**Step 4 — global evaluate, report, and plots** (after combining):
```bash
python3 -m src.pipeline --train-goodRunList --skip-train --skip-apply
```
If uncombined per-run files exist when this runs, the pipeline refuses to continue
and prints a message asking for the combine step to be run first.

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--config` | `config.yaml` | Path to YAML configuration file |
| `--good-list` | from config.yaml | Run list of good files for training |
| `--apply-list` | from config.yaml | Run list of files to apply the trained model to |
| `--model-tag` | from config.yaml | Base tag for all outputs. `_<Quality>` is appended when `--train-goodRunList` is active; `_noTrigger` and/or `_noLVDS` are appended when the corresponding flags are active, e.g. `myrun_Tight_noLVDS` |
| `--models-dir` | from config.yaml | Base directory for saved models |
| `--logs-dir` | from config.yaml | Base directory for anomaly logs |
| `--reports-dir` | from config.yaml | Base directory for reports |
| `--plots-dir` | from config.yaml | Base directory for plots |
| `--test-train [N]` | off | Sample N training files (default N=50 when flag is given) |
| `--test-apply [N]` | off | Sample N apply files (default N=50 when flag is given) |
| `--test-seed` | from config.yaml | Random seed for reproducible test-mode sampling |
| `--no-trigger` | off | Exclude TriggerBoard features (overrides `use_trigger` in config.yaml) |
| `--no-trigger-LVDS` | off | Exclude LVDS pin count features (overrides `use_lvds` in config.yaml) |
| `--no-trigger-config` | off | Disable trigger config integration (prescale normalisation, channel masking). Appends `_ignoreTriggerConfig` |
| `--no-daq-config` | off | Disable DAQ config integration. Appends `_ignoreDAQConfig` |
| `--z-threshold` | from config.yaml | σ threshold for the statistical layer |
| `--if-contamination` | from config.yaml | Expected anomaly fraction for Isolation Forest |
| `--if-n-estimators` | from config.yaml (200) | Number of trees in the Isolation Forest ensemble. More trees → more stable scores, slower training |
| `--if-max-samples` | from config.yaml (`auto`) | Samples drawn per tree (`auto` = `min(256, n_samples)`). Higher values increase score stability but raise memory usage |
| `--if-max-features` | from config.yaml (1.0) | Fraction of features considered at each split (sklearn `max_features`). `1.0` = all features |
| `--file-alert-n-channels` | from config.yaml | Number of *persistent* anomalous channels to trigger a file-level ALERT (persistence condition) |
| `--alert-consecutive-n` | from config.yaml | Consecutive files a channel must be anomalous in to count as persistent. Set to `1` to disable |
| `--single-file-alert-n-channels` | from config.yaml | Bulk alert: minimum anomalous channels in a single file for `[ALERT]`. `0` = disabled |
| `--single-file-alert-max-z` | from config.yaml | Extreme alert: `[ALERT]` when any channel's `max_z` meets or exceeds this value. `0.0` = disabled |
| `--train-goodRunList` | off | Train on the complete slab dataset on EOS instead of the default good run list. Appends `_<Quality>` to the model tag |
| `--train-goodRunList-quality` | from config.yaml | Quality filter for training: `Loose`, `Medium`, `Tight`, or `All` (OR of all three) |
| `--train-goodRunList-fraction` | from config.yaml | Fraction of the quality-filtered catalogue to use for training (0 < F ≤ 1) |
| `--train-goodRunList-min-run` | none (no lower bound) | Lowest run number (inclusive) to include when training from the catalogue. Applied after quality filtering and before fraction sub-sampling |
| `--train-goodRunList-max-run` | none (no upper bound) | Highest run number (inclusive) to include when training from the catalogue. Applied after quality filtering and before fraction sub-sampling |
| `--read-full-sample-apply` | off | Score files from the slab catalogue instead of the default apply list |
| `--full-sample-apply-quality` | from config.yaml | Quality filter for the apply step: `Loose`, `Medium`, `Tight`, or `All` |
| `--full-sample-apply-fraction` | from config.yaml | Fraction of the quality-filtered catalogue to score (0 < F ≤ 1) |
| `--apply-to-training-list` | off | Apply on exactly the same files used for training (same quality, fraction, seed). Requires `--train-goodRunList`. Overrides apply-side quality/fraction flags |
| `--apply-specific-run RUN` | off | Scan the slab directory on disk for all subruns of run RUN (catalogue-independent — any run can be targeted; requires `--train-goodRunList`). Writes output to `logs/<tag>_run<RUN>.csv`. No report or plots produced. Cannot be combined with `--apply-to-training-list` |
| `--apply-specific-run-fraction F` | `1.0` | Fraction of the run's files to score when `--apply-specific-run` is set (0 < F ≤ 1). Decoupled from `--train-goodRunList-fraction` |
| `--combine-specific-run-outputs PATTERN` | off | Combine per-run CSVs matching `logs/<tag>_run<PATTERN>.csv` into `logs/<tag>.csv`. Accepts shell wildcards (e.g. `'*'` for all, `'100?'` for runs 1000–1009). Exits after combining |
| `--delete-model-tag TAG` | off | Delete all outputs for the given model tag (models, log, reports, plots) after a confirmation prompt, then exit. Cannot be combined with other flags except `--config` |
| `--override-outputs` | off | Delete all existing outputs for the resolved model tag (models, log, reports, plots) with a confirmation prompt, then re-run the pipeline immediately. Unlike `--delete-model-tag`, does not exit after deletion |
| `--skip-train` | off | Skip training (requires existing models) |
| `--skip-apply` | off | Skip application (requires existing log) |
| `--skip-evaluate` | off | Skip the evaluate step (TP/FP/TN/FN against goodRunsListSlab.json). Evaluate is automatically skipped unless `--train-goodRunList` is set, since the training quality level is used as the ground truth |
| `--skip-report` | off | Skip report generation |
| `--skip-all-plots` | off | Skip the entire plots step — no `reference_*`, `log_*`, or per-file plots |
| `--skip-subrun-plots` | off | Skip per-subrun plots only; `reference_*` and `log_*` summary plots are still generated |
| `--max-subrun-plots` | from config.yaml | Per category: up to this many random bad subruns (always including the worst) and up to this many random good subruns. `-1` = no limit (plots every file — a loud warning is printed) |
| `--plot-format` | from config.yaml (`png`) | Output format for all figures (reference, log, per-file, and confusion matrix): `png`, `pdf`, or `svg`. Use `pdf` for vector output suitable for publication or lossless zooming. Also settable in `config.yaml` under `plot_format` |

The pipeline also writes a path cache (`<tag>_paths.txt`) alongside the log so that the plots step can locate the full file paths needed for per-file plots.

---

## HTCondor

The full pipeline can be submitted to the CERN HTCondor batch system to run all four
feature variants in parallel. Each job runs the complete
train → apply → evaluate → report → plots sequence for one variant.

### Prerequisites

1. `config.yaml` has correct absolute paths for `good_list`, `apply_list`, and the output directories (see [Setup](#setup))
2. Dependencies are installed: `bash setup.sh`

### Submit

```bash
# From isolation_forest/
condor_submit condor/submit.sub
```

This submits 4 jobs, one per feature variant:

Feature counts are before `ignore_features` is applied (see `config.yaml`).

| Job | Variant | Flags | Model tag | Features |
|---|---|---|---|---|
| `.0` | `trigger_lvds` | *(none)* | `condor` | 52 |
| `.1` | `trigger_nolvds` | `--no-trigger-LVDS` | `condor_noLVDS` | 50 |
| `.2` | `notrigger_lvds` | `--no-trigger` | `condor_noTrigger` | 37 |
| `.3` | `notrigger_nolvds` | `--no-trigger --no-trigger-LVDS` | `condor_noTrigger_noLVDS` | 35 |

Each job requests 4 CPUs, 4 GB RAM, and the `workday` flavour (8-hour wall time).
AFS and EOS are mounted on lxplus Condor nodes — no file transfer is needed.
You will receive an email at `j.tafoya.vargas@cern.ch` when all jobs complete.

### Monitor

```bash
condor_q <cluster_id>
condor_history <cluster_id>   # after jobs finish
```

### Output

Each variant writes to its own subdirectory under the base tag `condor`, with suffixes appended automatically by `pipeline.py` based on the active feature flags:

```
models/condor/                    logs/condor.csv
models/condor_noLVDS/             logs/condor_noLVDS.csv
models/condor_noTrigger/          logs/condor_noTrigger.csv
models/condor_noTrigger_noLVDS/   logs/condor_noTrigger_noLVDS.csv
reports/condor*/
plots/condor*/
```

Condor stdout/stderr are written to `condor/logs/<cluster>.<process>.<variant>.{out,err}` so reruns never overwrite previous output. The shared job event log is `condor/logs/condor.log`.

---

## Performance tuning

If known-good data keeps raising warnings or alerts, the cause is usually one of the
following. The log plots (`python3 -m src.plot log`) are the primary diagnostic tool.

### Diagnosing false positives

Run the pipeline against a known-good list and inspect the three frequency plots:

| Plot | What to look for |
|---|---|
| `log_channel_frequency.png` | Same channels flagged repeatedly → systematic issue with those channels or their reference stats. Random channels each time → threshold or IF noise. |
| `log_feature_frequency.png` | One or two features dominate → those features have high run-to-run variance; add them to `ignore_features` or raise `z_threshold`. |
| `log_anomaly_rate.png` | Every file just barely above the alert threshold → threshold is the problem. Some files much worse than others → those runs are genuinely different. |

### Common causes and fixes

**Isolation Forest contamination too high (`if_contamination`)**

The IF uses `if_contamination` to set its internal score threshold: it will always flag
the top `if_contamination` fraction of points in any new data. At `0.05`, 5% of good
data will be flagged by the IF regardless of how representative the training set is.
Lower this first:

```yaml
if_contamination: 0.01
```

**Alert thresholds**

`file_alert_n_channels` is the minimum number of *persistent* anomalous channels required to raise an ALERT via the persistence condition. Any anomalous channel below this count prints WARN unless a single-file condition also fires. The default is 2. Raise it if the detector routinely has one or two noisy channels that are not operationally significant:

```yaml
file_alert_n_channels: 5
```

Two additional single-file conditions can raise ALERT independently, without waiting for persistence:

- **`single_file_alert_n_channels`**: fires when ≥ K channels are anomalous in a single file. Targets sudden widespread events (power glitch, noisy run). Set higher than `file_alert_n_channels` (e.g. 5–10) because there is no persistence filter to suppress transient noise. `0` = disabled.
- **`single_file_alert_max_z`**: fires when any single channel's `max_z` meets or exceeds this value. Targets a catastrophically out-of-range channel (e.g. broken digitizer hardware). `0.0` = disabled.

```yaml
single_file_alert_n_channels: 5
single_file_alert_max_z:      15.0
```

**Persistence window (`alert_consecutive_n`)**

This is the primary lever for suppressing single-file fluctuations without raising the
channel count threshold. A channel must be anomalous in this many consecutive files
(including the current one) to be counted as persistent and contribute to ALERT. The
default is 3 — a transient spike in any single subrun prints WARN; sustained anomalies
over 3 consecutive subruns escalate to ALERT.

- **Larger N**: reduces false alerts from single-file noise; delays detection of new faults by N − 1 files
- **`N = 1`**: disables persistence entirely — every anomaly is immediately ALERT-eligible (original behaviour)
- **N = 2**: one confirmation file required (fastest escalation with any protection)

```yaml
alert_consecutive_n: 2
```

Note that `alert_consecutive_n` acts at the *console/alert* level only. The anomaly log
(`logs/<tag>.csv`) records every anomalous channel in every file regardless of persistence,
so the full history is always available for offline analysis via `report.py` and `plot.py`.

> **Caveats**
>
> - **Run boundaries**: channel history is **reset at every run boundary**. When a new run
>   number is detected, the streak counters and `channel_history` dict are cleared.
>   Clean subruns always print `[OK]` immediately. Subruns with only transient anomalies
>   (streak not yet established) also print `[OK]`. `[WARN]` fires only when at least one
>   channel has a confirmed sub-threshold persistent anomaly. In the plots, subruns belonging
>   to runs with fewer than `alert_consecutive_n` files total are labelled PEND
>   retrospectively, since persistence can never be verified for those runs.
>
> - **Test mode / random sampling**: in test mode files are randomly sampled then
>   processed in run/subrun order. If the sample skips subruns (e.g. picks subruns 1, 5,
>   10 but not 2–9), the persistence window spans the *sampled* files rather than truly
>   consecutive subruns. A channel anomalous in subruns 1 and 10 accumulates as `[2/3
>   files]` even if subruns 2–9 were nominal. The persistent/transient verdict is therefore
>   approximate in test mode and should not be used as a production-quality persistence
>   judgement.

**Noisy reference statistics from a small training set**

The per-channel mean and std are estimated from the training files. With a small set,
the std can be underestimated — making the z-score denominator too tight and inflating
z-scores for perfectly normal variation. Train on more files; the false positive rate
drops as the reference statistics converge.

**Run-to-run variation not captured in training**

Some features (occupancy, trigger rates) shift legitimately between runs depending on
beam conditions or run length. If those conditions are not well-represented in the
training set, new good runs in a slightly different regime will appear anomalous. Fix
by broadening the training set, or by adding the unstable features to `ignore_features`.

### Suggested starting point for a detector of this size

```yaml
z_threshold:                  6.0
if_contamination:             0.01
file_alert_n_channels:        2
alert_consecutive_n:          3
single_file_alert_n_channels: 5
single_file_alert_max_z:      15.0
```

Retrain and reapply to the known-good list after each change, using the frequency plots
to verify the false positive rate is dropping rather than just masking real anomalies.

---

---

## Per-run apply workflow (goodRunList → per-run jobs → combine → report)

The standard workflow for processing the complete slab dataset via Condor array jobs.

```bash
# ── Step 1: train once ──────────────────────────────────────────────────────
python3 -m src.pipeline \
  --model-tag my_tag \
  --train-goodRunList \
  --train-goodRunList-quality Tight \
  --train-goodRunList-fraction 0.001 \
  --skip-apply --skip-evaluate --skip-report --skip-all-plots

# ── Step 2: apply per run (one job per RUN_NUMBER) ───────────────────────────
# Apply to all files of the run on disk; use --apply-specific-run-fraction
# to score a random subset (default 1.0 = all files, decoupled from training fraction)
python3 -m src.pipeline \
  --model-tag my_tag \
  --train-goodRunList \
  --train-goodRunList-quality Tight \
  --train-goodRunList-fraction 0.001 \
  --skip-train \
  --apply-specific-run $RUN_NUMBER \
  --apply-specific-run-fraction 1.0

# ── Step 3: combine once all per-run jobs are done ───────────────────────────
# '*' is a wildcard on the run-number part — quote it to prevent shell expansion
python3 -m src.pipeline \
  --model-tag my_tag \
  --train-goodRunList \
  --train-goodRunList-quality Tight \
  --combine-specific-run-outputs '*'

# Combine a subset only (e.g. runs 1340–1349)
python3 -m src.pipeline \
  --model-tag my_tag \
  --train-goodRunList \
  --train-goodRunList-quality Tight \
  --combine-specific-run-outputs '134?'

# ── Step 4: global evaluate, report, and plots ──────────────────────────────
python3 -m src.pipeline \
  --model-tag my_tag \
  --train-goodRunList \
  --train-goodRunList-quality Tight \
  --skip-train --skip-apply
```

**Notes:**
- The pipeline blocks step 4 if any `<tag>_run*.csv` files are newer than the combined log, forcing you to combine first.
- To re-run a tag from scratch: `python3 -m src.pipeline --model-tag my_tag --train-goodRunList --train-goodRunList-quality Tight --override-outputs` (prompts for confirmation before deleting).
- Per-run log files (`<tag>_run<N>.csv`) are kept on disk after combining so partial re-combines are possible.

---

## Known limitations

- **Single directory watch**: the monitor watches one directory. For multiple live paths,
  run a separate `monitor.py` instance per directory with a shared `--log-file`.
- **Polling**: the monitor uses polling rather than inotify, for compatibility with AFS
  and network filesystems. Reduce `--poll-interval` for lower latency if needed.
