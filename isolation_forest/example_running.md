# Example running commands

All commands are run from `isolation_forest/`.

## Full pipeline — single command (recommended)

```bash
# End-to-end test (50 training files, 20 apply files)
python3 -m src.pipeline \
    --good-list  ../data/good_run_list_EOS.txt \
    --apply-list ../data/all_run_list_EOS.txt \
    --test-train 50 --test-apply 20

# Full production run
python3 -m src.pipeline \
    --good-list  ../data/good_run_list_EOS.txt \
    --apply-list ../data/all_run_list_EOS.txt
```

Runs all four steps in order: train → apply → report → plots.  
Use `--skip-train`, `--skip-apply`, `--skip-report`, `--skip-plots` to re-run individual steps.

## Step by step

### 1. Install dependencies

```bash
bash setup.sh
```

### 2. Train

```bash
python3 -m src.train --good-list ../data/good_run_list_EOS.txt
```

### 3. Monitor a live directory

```bash
python3 -m src.monitor --watch-dir /eos/experiment/milliqan/run3/slab/live/
```

## Quick test training on a random subset of files

To verify the pipeline works without waiting for a full training run:

```bash
python3 -m src.train --good-list ../data/good_run_list_EOS.txt --test 50
```

This randomly samples 50 files from the resolved run list and trains on those only.
Useful for checking that dependencies are installed, file paths resolve correctly,
and the models directory is writable before committing to a full run.
If the run list has fewer than 50 files, all of them are used.

## Incremental update (after collecting more good runs)

```bash
# Add new glob patterns to ../data/good_run_list_EOS.txt, then:
python3 -m src.train --good-list ../data/good_run_list_EOS.txt --update
```

## Process files already in a directory (e.g. for testing)

```bash
python3 -m src.monitor \
  --watch-dir ../data/noisy_channel \
  --log-file logs/anomalies.csv \
  --process-existing
```

## Quick test of model application

Apply to a random sample from a run list (processes files then exits — no polling loop):

```bash
python3 -m src.monitor \
    --run-list ../data/all_run_list_EOS.txt \
    --test 20

# Or sample from a directory instead
python3 -m src.monitor \
    --watch-dir /eos/user/t/tafoyava/autoDQM/data/ \
    --test 20
```

## Classify run quality from the anomaly log

After the monitor has processed files, generate good/partial run lists:

```bash
python3 -m src.report
```

Output in `reports/`:
- `good_runs.txt` — runs where every subrun passed
- `partial_good_runs.txt` — runs with a clean good→bad transition, with the last good and first bad subrun numbers
- `run_summary.csv` — full table covering all runs

## Generate plots manually

```bash
# Reference model statistics (3 plots)
python3 -m src.plot reference

# Anomaly analysis of a single file (4 plots)
python3 -m src.plot file /eos/user/t/tafoyava/autoDQM/data/Digitizer_run2068_subrun1.csv

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
