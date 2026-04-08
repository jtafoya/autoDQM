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

## Generate plots

```bash
# Reference model statistics (3 plots)
python3 -m src.plot reference

# Anomaly analysis of a single file (4 plots)
python3 -m src.plot file ../data/noisy_channel/Digitizer_run2068_subrun1.csv

# Summary of the anomaly log (3 plots)
python3 -m src.plot log
```

All figures are saved to `plots/` by default. Use `--out-dir` to change the output directory.
