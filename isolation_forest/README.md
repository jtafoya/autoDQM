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
    plot.py          — CLI: generate diagnostic plots for training and detection output
  models/            — saved reference stats and trained Isolation Forest (created by train.py)
  logs/              — anomaly log CSV files (created by monitor.py)
  plots/             — diagnostic figures (created by plot.py)
  ../data/
    good_run_list.txt  — list of known-good files used for training
    bad_run_list.txt   — list of known-bad files (for reference and validation)
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

### 1. Edit the run lists

`../data/good_run_list.txt` lists the files used to build the reference model.  
`../data/bad_run_list.txt` lists known-bad files (for validation only — not used in training).

Each non-empty, non-comment line is a **glob pattern** resolved from the `isolation_forest/` directory:

```
# ../data/good_run_list.txt
../data/broken_base_BeforeIncident/Digitizer_*.csv
../data/broken_base_AfterFix/Digitizer_run1644_subrun*.csv
../data/noisy_channel__AfterFix/Digitizer_*.csv
```

Lines starting with `#` and blank lines are ignored.

### 2. Train

Build the reference model and train the Isolation Forest:

```bash
python3 -m src.train --good-list ../data/good_run_list.txt
```

This creates:
- `models/reference.npz` — per-channel Welford statistics (mean, variance, count)
- `models/detector.pkl` — trained Isolation Forest
- `models/seen_files.json` — list of files already incorporated into the reference

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--good-list` | (required) | Path to the good run list file |
| `--models-dir` | `models/` | Where to save the trained models |
| `--z-threshold` | `5.0` | σ threshold for the statistical layer |
| `--if-contamination` | `0.05` | Expected anomaly fraction for Isolation Forest |
| `--update` | off | Incremental mode: add new good files without reprocessing old ones |
| `--test N` | off | Test mode: randomly sample N files from the run list instead of using all of them |

### 3. Monitor

Watch a directory for new `Digitizer_*.csv` files and log anomalies:

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

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--watch-dir` | (required) | Directory to watch for new CSV files |
| `--models-dir` | `models/` | Directory with saved models |
| `--log-file` | `logs/anomalies.csv` | Output log path |
| `--poll-interval` | `5.0` | Seconds between directory scans |
| `--file-alert-threshold` | `0.20` | Fraction of anomalous channels needed to print `[ALERT]` |
| `--process-existing` | off | Also process files already in the directory at startup |
| `--plot-alerts` | off | Auto-generate 4 diagnostic plots for every alerted file, saved to `plots-dir/alerts/<stem>/` |
| `--plots-dir` | `plots/` | Root directory for all plot output |
| `--refresh-log-plots-every` | `0` | Regenerate log summary plots every N processed files (0 = disabled) |

Terminal output:
```
[OK]    2026-04-08T17:00:00Z  Digitizer_run2090_subrun1.csv  —  96 channels, all nominal
[WARN]  2026-04-08T17:00:05Z  Digitizer_run2090_subrun2.csv  —  3/96 (3%) anomalous (below threshold)
[ALERT] 2026-04-08T17:00:10Z  Digitizer_run2091_subrun1.csv  —  91/96 (95%) anomalous: [1, 3, 4, ...]
         ch  1  method=statistical+IF        max_z=20.35     if_score=-0.59   features=[nPulses_std;occupancy]
         ch  3  method=statistical           max_z=2000000   if_score=-0.65   features=[sideband_mean_median;...]
```

### 4. Plot

Generate diagnostic figures after training or after processing files:

```bash
# Reference model statistics
python3 -m src.plot reference

# Anomaly analysis of a single file
python3 -m src.plot file <path/to/Digitizer_runXXXX_subrunY.csv>

# Summary of the anomaly log
python3 -m src.plot log
```

Figures are saved to `plots/`. See the [Plots](#plots) section for descriptions of each figure.

---

## Log format

`logs/anomalies.csv` is append-only. One row per channel per file:

| Column | Description |
|---|---|
| `timestamp` | UTC time the file was processed (ISO-8601) |
| `filename` | Base name of the Digitizer CSV |
| `channel` | Channel ID |
| `anomalous` | `True` / `False` |
| `method` | `statistical`, `isolation_forest`, `statistical+IF`, `new_channel`, or `""` |
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
```

Good files and files below the alert threshold generate no plots, keeping storage proportional
to the number of anomalies rather than the total number of files processed.

### Reference plots

```bash
python3 -m src.plot reference
```

| File | Description |
|---|---|
| `reference_means.png` | Heatmap of per-channel reference means, column-normalised to z-scores so all features share a common colour scale. Shows the nominal state of each channel across all 50 features, including trigger rates at the bottom. |
| `reference_stds.png` | Heatmap of reference uncertainties (log-normalised σ). Bright cells indicate features with high run-to-run variability; these contribute less to anomaly detection. |
| `reference_coverage.png` | Bar chart of how many training files each channel appeared in. Channels with low coverage have less reliable reference statistics. |

### Single-file analysis plots

```bash
python3 -m src.plot file <path/to/Digitizer_runXXXX_subrunY.csv>
```

| File | Description |
|---|---|
| `<stem>_zscore_heatmap.png` | Full channels × 50 features z-score matrix, clamped at 50σ. Red shading highlights flagged channels. The rightmost columns are trigger rate features — a vertical stripe there indicates a file-wide trigger condition change. |
| `<stem>_max_zscore.png` | Bar chart of the maximum absolute z-score per channel (log scale). The dashed line marks the alert threshold. Red bars are flagged channels, blue are nominal. |
| `<stem>_if_scores.png` | Isolation Forest anomaly score per channel. More negative = more anomalous. Complements the z-score plot by capturing multivariate anomalies not visible in any single feature. |
| `<stem>_geometry.png` | Detector layout plot: one panel per layer, channels placed at their (row, column) position and coloured by max \|z\|. Red rings mark flagged channels. Useful for spotting spatially localised problems (e.g. a dead row or noisy column). |

### Log summary plots

```bash
python3 -m src.plot log
```

| File | Description |
|---|---|
| `log_anomaly_rate.png` | Anomalous channel fraction per file in chronological order. Red bars exceed the 20% alert threshold; blue bars are below it. Shows run quality at a glance and makes gradual degradation visible. |
| `log_channel_frequency.png` | Bar chart of the 40 most frequently flagged channels across all processed files. Persistent entries point to channels with chronic issues rather than transient noise. |
| `log_feature_frequency.png` | Bar chart of the 20 most frequently triggered features. Identifies which metrics are driving alerts — useful for diagnosing systematic hardware problems (e.g. TDC drift, occupancy loss, trigger rate shifts). |

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

These are then enriched with **trigger rate features** from the matching TriggerBoard CSV:

```
triggerRate_bit{1–13}            →  13 features, per-bit trigger rate in Hz
triggerRate_tot                  →  1 feature,  total trigger rate in Hz
triggerCounts_tot                →  1 feature,  total trigger count for the subrun
                                    ─────────────────────────────────────────
                                     15 TriggerBoard features per file
```

The TriggerBoard file (`TriggerBoard_run<N>.csv`) is located automatically from the
Digitizer filename in the same directory. Its trigger rates are constant within a file
(one value per subrun), so they are appended as the same value to every channel row.
This means a deviation in trigger rate is visible on every channel simultaneously —
reflecting that it is a file-wide condition, not a per-channel one.

If the TriggerBoard file is absent or the subrun is not found, the trigger features
are set to `NaN` and detection falls back to the 35 Digitizer features only.

**Total: 50 features per channel per file.**

### Reference model (`src/reference.py`)

Built from good-data files using **Welford's online algorithm**. For each
(channel, feature) pair it maintains three numbers — `count`, `mean`, `M2` — from
which the mean and standard deviation can be derived at any time. Adding a new file
costs O(channels × features) and never touches previously processed files.
This is the mechanism that keeps training tractable at 10^6-file scale.

### Isolation Forest (`src/detector.py`)

The IF is trained on **z-scored** feature vectors from good data, not raw values.
Z-scoring first makes the IF scale-invariant (channels at different detector positions
have different baseline values but similar nominal z-score distributions), and means
the IF learns *patterns of deviation* rather than memorising absolute scales.

Training data is capped at `max_samples=50_000` channel-file vectors; beyond that,
a random subsample is drawn. This keeps training fast regardless of corpus size.

---

## Scaling to > 10^6 files

When the corpus of good runs grows, add the new patterns to `../data/good_run_list.txt`
and run training in incremental mode:

```bash
python3 -m src.train --good-list ../data/good_run_list.txt --update
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

## Known limitations

- **Small training set**: with fewer than ~20 good files, the Isolation Forest produces
  some false positives at the channel level. The 20% file-alert threshold compensates.
  This improves automatically as good data grows.
- **Single directory watch**: the monitor watches one directory. For multiple live paths,
  run a separate `monitor.py` instance per directory with a shared `--log-file`.
- **Polling**: the monitor uses polling rather than inotify, for compatibility with AFS
  and network filesystems. Reduce `--poll-interval` for lower latency if needed.
