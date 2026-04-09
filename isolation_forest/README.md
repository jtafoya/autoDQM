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
A file is printed as `[ALERT]` if **≥ 20%** of its channels are flagged (configurable).

---

## Directory structure

```
isolation_forest/
  src/
    features.py      — per-channel feature extraction from Digitizer + TriggerBoard CSVs
    reference.py     — Welford online reference model (incremental, scalable)
    detector.py      — two-layer anomaly detector (z-score + Isolation Forest)
    run_list.py      — run list file parser (glob expansion)
    train.py         — CLI: build/update reference and train Isolation Forest
    monitor.py       — CLI: watch a directory for new files and log anomalies
    report.py        — CLI: classify runs from the anomaly log (good / partial / bad)
    plot.py          — CLI: generate diagnostic plots for training and detection output
    pipeline.py      — CLI: run the full pipeline (train → apply → report → plots) in one command
  models/            — saved reference stats and trained Isolation Forest (created by train.py)
  logs/              — anomaly log CSV files (created by monitor.py / pipeline.py)
  reports/           — run quality lists and summary table (created by report.py / pipeline.py)
  plots/             — diagnostic figures (created by plot.py / pipeline.py)
  ../data/
    good_run_list_EOS.txt  — known-good files used for training (default --good-list)
    bad_run_list_EOS.txt   — known-bad files (for reference and validation)
    all_run_list_EOS.txt   — all classified runs combined (good + bad); default --apply-list
  requirements.txt   — Python dependencies
  setup.sh           — install dependencies
```

---

## Setup

```bash
bash setup.sh
```

This installs `pandas`, `scikit-learn`, `numpy`, `scipy`, and `watchdog` into your user
site-packages (`--user`, no root needed). Works on lxplus/AFS.

Verify:
```bash
python3 -c "import pandas, sklearn, numpy, scipy, watchdog; print('OK')"
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

# Full training (all files)
python3 -m src.train

# Digitizer-only mode (no TriggerBoard features)
python3 -m src.train --no-trigger

# Disable LVDS pin count features
python3 -m src.train --no-trigger-LVDS
```

This creates:
- `models/reference.npz` — per-channel Welford statistics (mean, variance, count)
- `models/detector.pkl` — trained Isolation Forest
- `models/seen_files.json` — list of files already incorporated into the reference

The `use_trigger` and `use_lvds` settings are saved into `reference.npz` so all subsequent
steps (apply, plots) automatically use the same feature set.

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--good-list` | `../data/good_run_list_EOS.txt` | Path to the good run list file |
| `--models-dir` | `models/` | Where to save the trained models |
| `--z-threshold` | `5.0` | σ threshold for the statistical layer |
| `--if-contamination` | `0.05` | Expected anomaly fraction for Isolation Forest |
| `--no-trigger` | off | Exclude TriggerBoard features; use the 35 Digitizer-only features |
| `--no-trigger-LVDS` | off | Exclude LVDS pin count features (on by default: `LVDSpin0`–`LVDSpin49` + `LVDStotal`) |
| `--update` | off | Incremental mode: add new good files without reprocessing old ones |
| `--test [N]` | off | Test mode: randomly sample N files (default N=50 when flag is given) |

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

To apply the model to a run list instead of a live directory (test mode only):

```bash
python3 -m src.monitor \
  --run-list ../data/all_run_list_EOS.txt \
  --test 20
```

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--watch-dir` | (one of these required) | Directory to watch for new CSV files |
| `--run-list` | (one of these required) | Run list file; requires `--test N`; processes N random files then exits |
| `--models-dir` | `models/` | Directory with saved models |
| `--log-file` | `logs/anomalies.csv` | Output log path |
| `--poll-interval` | `5.0` | Seconds between directory scans |
| `--file-alert-threshold` | `0.20` | Fraction of anomalous channels needed to print `[ALERT]` |
| `--process-existing` | off | Also process files already in the directory at startup |
| `--plot-alerts` | off | Auto-generate 4 diagnostic plots for every alerted file, saved to `plots-dir/alerts/<stem>/` |
| `--plots-dir` | `plots/` | Root directory for all plot output |
| `--refresh-log-plots-every` | `0` | Regenerate log summary plots every N processed files (0 = disabled) |
| `--test [N]` | off | Test mode: randomly sample N files from the source (watch-dir or run-list), process them, then exit |

Terminal output:
```
[OK]    2026-04-08T17:00:00Z  Digitizer_run2090_subrun1.csv  —  96 channels, all nominal
[WARN]  2026-04-08T17:00:05Z  Digitizer_run2090_subrun2.csv  —  3/96 (3%) anomalous (below threshold)
[ALERT] 2026-04-08T17:00:10Z  Digitizer_run2091_subrun1.csv  —  91/96 (95%) anomalous: [1, 3, 4, ...]
         ch  1  method=statistical+IF        max_z=20.35     if_score=-0.59   features=[nPulses_std;occupancy]
         ch  3  method=statistical           max_z=2000000   if_score=-0.65   features=[sideband_mean_median;...]
```

### 4. Classify runs

After processing files with the monitor, summarise run quality from the anomaly log:

```bash
python3 -m src.report
```

This reads `logs/anomalies.csv` and writes:

| File | Description |
|---|---|
| `reports/good_runs.txt` | Runs where every subrun is nominal |
| `reports/partial_good_runs.txt` | Runs that start nominal then transition to anomalous, with the last good and first bad subrun noted |
| `reports/persistent_fault_runs.txt` | Runs with one or more channels anomalous in every subrun (systematic fault below the per-file threshold) |
| `reports/run_summary.csv` | Full per-run breakdown (all categories), including a `persistent_channels` column |

Runs are classified as:

| Classification | Meaning |
|---|---|
| `good` | All subruns below the alert threshold, no persistent channel faults |
| `partial` | At least one good subrun followed by at least one bad subrun (clean transition) |
| `bad` | All subruns above the alert threshold |
| `mixed` | Good and bad subruns interleaved with no clean transition |
| `persistent_fault` | All subruns appear nominal by the per-file threshold, but one or more channels are anomalous in every subrun — e.g. a dead or missing channel that never triggers enough to cross 20% on its own |

> **`persistent_fault` guard:** requires at least **2 subruns** in the log for the run.
> A run with only 1 subrun trivially satisfies "anomalous in every subrun" (1/1),
> which would produce false positives when sampling a sparse test set.

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--log-file` | `logs/anomalies.csv` | Anomaly log to read |
| `--out-dir` | `reports/` | Directory to write output files |
| `--file-alert-threshold` | `0.20` | Fraction of anomalous channels that marks a subrun as bad (must match the value used in monitor.py) |

### 5. Plot

Generate diagnostic figures after training or after processing files:

```bash
# Reference model statistics
python3 -m src.plot reference

# Anomaly analysis of a single file
python3 -m src.plot file <path/to/Digitizer_runXXXX_subrunY.csv>

# Summary of the anomaly log
python3 -m src.plot log
```

Figures are saved to `plots/` by default. Use `--out-dir` and `--models-dir` **before** the subcommand to override:

```bash
python3 -m src.plot --out-dir /tmp/myplots --models-dir models/ reference
```

See the [Plots](#plots) section for descriptions of each figure.

---

## Log format

`logs/anomalies.csv` is append-only. One row per channel per file:

| Column | Description |
|---|---|
| `timestamp` | UTC time the file was processed (ISO-8601) |
| `filename` | Base name of the Digitizer CSV |
| `channel` | Channel ID |
| `anomalous` | `True` / `False` |
| `method` | `statistical`, `isolation_forest`, `statistical+IF`, `new_channel`, `missing_channel`, or `""` |
| `triggered_features` | Semicolon-separated feature names with \|z\| > threshold |
| `max_z` | Largest absolute z-score across all features for this channel |
| `if_score` | Isolation Forest anomaly score (more negative = more anomalous) |

---

## Plots

Figures are generated by `src/plot.py` and saved to `plots/` (created automatically).  
All subcommands accept `--models-dir` and `--out-dir` to override defaults.

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

### Single-file analysis plots

```bash
python3 -m src.plot file <path/to/Digitizer_runXXXX_subrunY.csv>
```

| File | Description |
|---|---|
| `<stem>_zscore_heatmap.png` | Full channels × features z-score matrix, clamped at 50σ. Red shading highlights flagged channels. When trigger features are enabled, the rightmost columns show trigger rates — a vertical stripe there indicates a file-wide trigger condition change. |
| `<stem>_max_zscore.png` | Bar chart of the maximum absolute z-score per channel (log scale). The dashed line marks the alert threshold. Red bars are flagged channels, blue are nominal. |
| `<stem>_if_scores.png` | Isolation Forest anomaly score per channel. More negative = more anomalous. Complements the z-score plot by capturing multivariate anomalies not visible in any single feature. |
| `<stem>_geometry.png` | Detector layout plot: one panel per layer (all 4 layers in a single row), channels placed at their (row, column) position and coloured by max \|z\|. Red rings mark flagged channels. Useful for spotting spatially localised problems (e.g. a dead row or noisy column). |

### Log summary plots

```bash
python3 -m src.plot log
```

Files are ordered by **run number then subrun number** in all log plots.

| File | Description |
|---|---|
| `log_anomaly_rate.png` | Anomalous channel fraction per file, sorted by run/subrun. Red bars exceed the alert threshold; blue bars are below it. |
| `log_channel_frequency.png` | Bar chart of the 40 most frequently flagged channels across all processed files. Persistent entries point to channels with chronic issues rather than transient noise. |
| `log_feature_frequency.png` | Bar chart of the 20 most frequently triggered features. Identifies which metrics are driving alerts — useful for diagnosing systematic hardware problems (e.g. TDC drift, occupancy loss, trigger rate shifts). |
| `log_run_summary.png` | Bar chart with one bar per run showing what fraction of its subruns are good data (0–100%). Blue = all subruns good, orange = partial, red = all bad. Each bar is annotated with the raw count (good/total subruns). |

The `log` subcommand accepts `--file-alert-threshold` (default `0.20`) to match the threshold
used during monitoring.

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

By default these are enriched with **trigger rate features** from the matching TriggerBoard CSV:

```
triggerRate_bit{1–13}            →  13 features, per-bit trigger rate in Hz
triggerRate_tot                  →  1 feature,  total trigger rate in Hz
triggerCounts_tot                →  1 feature,  total trigger count for the subrun
                                    ─────────────────────────────────────────
                                     15 TriggerBoard features per file
```

By default, **LVDS count features** from the matching LVDSCounts CSV are also included (disable with `--no-trigger-LVDS`):

```
LVDSpin{0–49}                    →  50 features, per-pin LVDS counts for the subrun
LVDStotal                        →  1 feature,  sum of all LVDS pin counts
                                    ─────────────────────────────────────────
                                     51 LVDS features per file
```

**Total features per channel per file:**

| Mode | Features |
|---|---|
| Default (trigger on, LVDS on) | 35 + 15 + 51 = **101** |
| `--no-trigger-LVDS` | 35 + 15 = **50** |
| `--no-trigger` | 35 + 51 = **86** |
| `--no-trigger --no-trigger-LVDS` | **35** |

All TriggerBoard and LVDS files are located automatically from the Digitizer filename
in the same directory. Their values are constant within a file (one row per subrun),
so they are appended as the same value to every channel row — deviations are visible
on every channel simultaneously, reflecting that they are file-wide conditions.

If a companion file is absent or the subrun entry is missing (e.g. the last few subruns
of a run are sometimes not recorded), those features are set to `NaN` for that file.
The reference model handles this gracefully — NaN entries are skipped in the Welford
update so they do not corrupt the running mean or variance for other files.

Feature flags are saved in `models/reference.npz` and applied automatically by all
subsequent steps (apply, plots) — no flags needed at inference time.

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

Training data is capped at `max_samples=50_000` channel-file vectors; beyond that,
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

As the reference improves with more files:
- Per-channel mean and std estimates become tighter
- Isolation Forest has a larger, more representative training set
- The false positive rate drops; consider lowering `--file-alert-threshold` from 0.20 toward 0.05
- Consider also lowering `--if-contamination` from 0.05 toward 0.01

There is no hard limit on the number of files the reference can absorb — memory usage
is fixed at O(channels × features) regardless of how many files have been processed.

---

## Pipeline

`src/pipeline.py` runs all four steps — train, apply, report, plots — in sequence with a single command.
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
```

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--good-list` | `../data/good_run_list_EOS.txt` | Run list of good files for training |
| `--apply-list` | `../data/all_run_list_EOS.txt` | Run list of files to apply the trained model to |
| `--test-train [N]` | off | Sample N training files (default N=50 when flag is given) |
| `--test-apply [N]` | off | Sample N apply files (default N=50 when flag is given) |
| `--no-trigger` | off | Exclude TriggerBoard features (Digitizer-only mode) |
| `--no-trigger-LVDS` | off | Exclude LVDS pin count features (on by default; requires LVDSCounts files) |
| `--z-threshold` | `5.0` | σ threshold for the statistical layer (passed to train) |
| `--if-contamination` | `0.05` | Expected anomaly fraction for Isolation Forest (passed to train) |
| `--file-alert-threshold` | `0.20` | Fraction of anomalous channels to trigger a file-level ALERT (used in apply, report, and plots) |
| `--models-dir` | `models/` | Saved models directory |
| `--log-file` | `logs/anomalies.csv` | Output anomaly log |
| `--reports-dir` | `reports/` | Run quality report output |
| `--plots-dir` | `plots/` | Plot output directory |
| `--skip-train` | off | Skip training (requires existing models) |
| `--skip-apply` | off | Skip application (requires existing log) |
| `--skip-report` | off | Skip report generation |
| `--skip-plots` | off | Skip plot generation |

The pipeline also writes a path cache (`<log-stem>_paths.txt`) alongside the log so that the plots step can locate the full file paths needed for per-file ALERT plots.

---

## Known limitations

- **Small training set**: with fewer than ~20 good files, the Isolation Forest produces
  some false positives at the channel level. The 20% file-alert threshold compensates.
  This improves automatically as good data grows.
- **Single directory watch**: the monitor watches one directory. For multiple live paths,
  run a separate `monitor.py` instance per directory with a shared `--log-file`.
- **Polling**: the monitor uses polling rather than inotify, for compatibility with AFS
  and network filesystems. Reduce `--poll-interval` for lower latency if needed.
