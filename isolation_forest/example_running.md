# Example running commands

All commands are run from `isolation_forest/`.

## HTCondor — per-run apply array jobs over the full sample

To process the complete slab catalogue in parallel (one Condor job per run).
`--apply-specific-run` combined with `--train-goodRunList` scans the slab directory
on disk for all subruns of the requested run (catalogue-independent — any run can be
targeted regardless of quality).  Use `--apply-specific-run-fraction` to score a
random subset of the run's files (default 1.0 = all files), decoupled from
`--train-goodRunList-fraction`.  No `--read-full-sample-apply` flag is needed.

```bash
# 1. Train once on 0.1 % of Tight-quality files
python3 -m src.pipeline \
  --train-goodRunList \
  --train-goodRunList-quality Tight \
  --train-goodRunList-fraction 0.001 \
  --skip-apply --skip-evaluate --skip-report --skip-all-plots

# 2. Submit one job per run — applies to all files of that run on disk
#    (wire RUN_NUMBER from a Condor job-array variable or similar)
#    Use --apply-specific-run-fraction to score a fraction of the run's files
python3 -m src.pipeline \
  --train-goodRunList \
  --train-goodRunList-quality Tight \
  --train-goodRunList-fraction 0.001 \
  --skip-train --apply-specific-run $RUN_NUMBER

# 3. Combine all per-run outputs when every job is done
#    Quote '*' to prevent shell expansion
python3 -m src.pipeline --train-goodRunList --combine-specific-run-outputs '*'

# Combine only a subset (shell wildcard on the run number; absent files are silently skipped)
python3 -m src.pipeline --train-goodRunList --combine-specific-run-outputs '100?'

# 4. Generate global evaluate, report, and plots from the combined log
python3 -m src.pipeline --train-goodRunList --skip-train --skip-apply
```

The pipeline refuses to produce global plots if uncombined per-run files exist
(i.e. any `<tag>_run*.csv` newer than the combined `<tag>.csv`).

---

## HTCondor — all 4 feature variants in parallel (production)

Before submitting, verify `config.yaml` has correct absolute paths and that
`INSTALLATION_PATH` in `env.sh` is correct (it is the only variable defined there), then:

```bash
bash setup.sh                    # install deps on lxplus (once)
condor_submit condor/submit.sub  # submit 4 jobs
condor_q <cluster_id>            # check status
```

Each job runs the full pipeline for one variant using `--model-tag condor`; the
feature-set suffixes (`_noTrigger`, `_noLVDS`) are appended automatically.
Output goes to `models/condor<suffix>/`, `logs/condor<suffix>.csv`,
`reports/condor<suffix>/`, `plots/condor<suffix>/` (base dirs from `config.yaml`).
Stdout/stderr land in `condor/logs/<cluster>.<process>.<variant>.{out,err}`.
You receive an email on completion.

---

## Full pipeline — single command (recommended)

Both `--good-list` and `--apply-list` default to the standard EOS run lists,
so the minimal invocations are:

```bash
# Quick end-to-end test (50 random training files, 50 random apply files)
python3 -m src.pipeline --test-train --test-apply

# Custom sample sizes
python3 -m src.pipeline --test-train 100 --test-apply 50

# Full production run (all files)
python3 -m src.pipeline

# Named run — all outputs go to models/myrun/, logs/myrun.csv, reports/myrun/, plots/myrun/
python3 -m src.pipeline --model-tag myrun

# Digitizer-only mode (no TriggerBoard features)
python3 -m src.pipeline --test-train --test-apply --no-trigger

# Disable LVDS pin count features
python3 -m src.pipeline --test-train --test-apply --no-trigger-LVDS
```

Runs all five steps in order: train → apply → evaluate → report → plots.  
Use `--skip-train`, `--skip-apply`, `--skip-evaluate`, `--skip-report`, `--skip-all-plots` to skip individual steps.

Output directories are controlled by `--model-tag` (default: `default`). The base directories
are read from `$MODELS_DIR`, `$LOGS_DIR`, `$REPORTS_DIR`, `$PLOTS_DIR` (set by `env.sh`),
falling back to `models/`, `logs/`, `reports/`, `plots/` when those env vars are unset.

## Step by step

### 1. Install dependencies

```bash
bash setup.sh
```

### 2. Train

```bash
# Quick test (50 random files, default)
python3 -m src.train --test

# Custom sample size
python3 -m src.train --test 100

# Full training (all files in the default good run list)
python3 -m src.train

# Digitizer-only mode (exclude TriggerBoard features)
python3 -m src.train --no-trigger

# Disable LVDS pin count features
python3 -m src.train --no-trigger-LVDS
```

### 3. Monitor a live directory

```bash
python3 -m src.monitor --watch-dir /eos/experiment/milliqan/run3/slab/live/
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

## Incremental update (after collecting more good runs)

```bash
# Add new glob patterns to ../data/good_run_list_EOS.txt, then:
python3 -m src.train --update
```

## Process files already in a directory (e.g. for testing)

```bash
python3 -m src.monitor \
  --watch-dir ../data/noisy_channel \
  --log-file logs/anomalies.csv \
  --process-existing
```

## Classify run quality from the anomaly log

After the monitor has processed files, generate good/partial run lists:

```bash
python3 -m src.report
```

Output in `reports/`:
- `good_runs.txt` — runs where every subrun passed
- `partial_good_runs.txt` — runs with a clean good→bad transition, with the last good and first bad subrun numbers
- `persistent_fault_runs.txt` — runs where one or more channels are anomalous in every subrun (e.g. a dead or missing channel), even if no individual subrun crossed the per-file threshold
- `run_summary.csv` — full table covering all runs, including `persistent_channels` column

> **Note on `persistent_fault`:** a run is only upgraded to `persistent_fault` if it has
> at least **2 subruns** in the log. A single-subrun sample trivially satisfies "anomalous
> in every subrun" (1/1), which would produce false positives in test mode with sparse sampling.

## Generate plots manually

```bash
# Reference model statistics (3 plots)
python3 -m src.plot reference

# Anomaly analysis of a single file (4 plots)
python3 -m src.plot file /eos/user/t/tafoyava/autoDQM/data/Digitizer_run2068_subrun1.csv

# Summary of the anomaly log (4 plots, sorted by run/subrun)
python3 -m src.plot log

# Save all figures as PDF (vector, lossless zoom) instead of the default PNG
python3 -m src.plot --plot-format pdf reference
python3 -m src.plot --plot-format pdf log
```

All figures are saved to `plots/` by default. Use `--out-dir` to change the output directory.
`--plot-format` accepts `png` (default), `pdf`, or `svg`; the default can also be set with `plot_format` in `config.yaml`.

## Validate against separate good / bad run lists

After training, run the model against the known-good and known-bad lists separately
and generate plots for each to assess false positive and detection rates.
All four commands can run in parallel:

```bash
# Apply to good runs (no trigger)
python3 -m src.monitor \
  --run-list ../data/good_run_list_EOS.txt \
  --log-file logs/check_good_notrigger.csv \
  --test 50 &

# Apply to bad runs (no trigger)
python3 -m src.monitor \
  --run-list ../data/bad_run_list_EOS.txt \
  --log-file logs/check_bad_notrigger.csv \
  --test 50 &

wait
```

Classify and plot for each log:

```bash
python3 -m src.report \
  --log-file logs/check_good_notrigger.csv \
  --out-dir  reports/check_good_notrigger

python3 -m src.report \
  --log-file logs/check_bad_notrigger.csv \
  --out-dir  reports/check_bad_notrigger

python3 -m src.plot --out-dir plots/check_good_notrigger \
  log --log-file logs/check_good_notrigger.csv

python3 -m src.plot --out-dir plots/check_bad_notrigger \
  log --log-file logs/check_bad_notrigger.csv
```

Repeat with the trigger-enabled model (`--log-file logs/check_good_trigger.csv`, etc.).

## Monitor with automatic alert plots

Auto-generate diagnostic plots for every file that crosses the alert threshold,
and refresh the log summary plots every 50 processed files:

```bash
python3 -m src.monitor \
  --watch-dir /eos/experiment/milliqan/run3/slab/live/ \
  --plot-alerts \
  --refresh-log-plots-every 50

# Same, but save all figures as PDF for lossless zooming
python3 -m src.monitor \
  --watch-dir /eos/experiment/milliqan/run3/slab/live/ \
  --plot-alerts \
  --refresh-log-plots-every 50 \
  --plot-format pdf
```

Alert plots are saved to `plots/alerts/<stem>/`, one subdirectory per flagged file.
File extensions match the chosen `--plot-format` (default `png`):

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
  log_run_summary.png
```
