# Example running commands

All commands are run from `isolation_forest/`.

## From scratch

```bash
# 1. Install dependencies
bash setup.sh

# 2. Edit ../data/good_run_list.txt to point at your good data, then train
python3 -m src.train --good-list ../data/good_run_list.txt

# 3. Monitor a live directory for new files
python3 -m src.monitor --watch-dir /eos/experiment/milliqan/run3/slab/live/
```

## Quick test training on a random subset of files

To verify the pipeline works without waiting for a full training run:

```bash
python3 -m src.train --good-list ../data/good_run_list.txt --test 50
```

This randomly samples 50 files from the resolved run list and trains on those only.
Useful for checking that dependencies are installed, file paths resolve correctly,
and the models directory is writable before committing to a full run.
If the run list has fewer than 50 files, all of them are used.

## Incremental update (after collecting more good runs)

```bash
# Add new glob patterns to ../data/good_run_list.txt, then:
python3 -m src.train --good-list ../data/good_run_list.txt --update
```

## Process files already in a directory (e.g. for testing)

```bash
python3 -m src.monitor \
  --watch-dir ../data/noisy_channel \
  --log-file logs/anomalies.csv \
  --process-existing
```

## Generate plots manually

```bash
# Reference model statistics (3 plots)
python3 -m src.plot reference

# Anomaly analysis of a single file (4 plots)
python3 -m src.plot file ../data/noisy_channel/Digitizer_run2068_subrun1.csv

# Summary of the anomaly log (3 plots)
python3 -m src.plot log
```

All figures are saved to `plots/` by default. Use `--out-dir` to change the output directory.

## Monitor with automatic alert plots

Auto-generate diagnostic plots for every file that crosses the alert threshold,
and refresh the log summary plots every 50 processed files:

```bash
python3 -m src.monitor \
  --watch-dir /eos/experiment/milliqan/run3/slab/live/ \
  --plot-alerts \
  --refresh-log-plots-every 50
```

Alert plots are saved to `plots/alerts/<stem>/`, one subdirectory per flagged file:

```
plots/
  alerts/
    Digitizer_run2068_subrun1/
      zscore_heatmap.png
      max_zscore.png
      if_scores.png
      geometry.png
    Digitizer_run2071_subrun3/
      ...
  log_anomaly_rate.png
  log_channel_frequency.png
  log_feature_frequency.png
```
