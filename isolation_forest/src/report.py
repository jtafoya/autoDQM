"""
Classify runs from the anomaly log into quality categories.

Reads logs/anomalies.csv (produced by monitor.py) and writes three files:

  good_runs.txt          — runs where every subrun is nominal
  partial_good_runs.txt  — runs that start nominal then transition to anomalous
  run_summary.csv        — full per-run breakdown (all categories)

A subrun is "bad" if the fraction of anomalous channels meets or exceeds
--file-alert-threshold (same default as monitor.py: 0.20).

A run is classified as:
  good    — all subruns good
  partial — at least one good subrun and at least one bad subrun, and the first
            bad subrun comes strictly after the last good subrun (clean transition)
  bad     — all subruns bad
  mixed   — good and bad subruns interleaved (no clean transition)

Usage:
    python3 -m src.report
    python3 -m src.report --log-file logs/anomalies.csv --out-dir logs/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

_FILENAME_RE = re.compile(r"Digitizer_run(\d+)_subrun(\d+)", re.IGNORECASE)


# ── Core logic ───────────────────────────────────────────────────────────────

def _parse_run_subrun(filename: str):
    m = _FILENAME_RE.search(str(filename))
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def classify_runs(log_path: str, file_alert_threshold: float = 0.20) -> dict:
    """
    Read the anomaly log and return a per-run classification dict.

    Returns
    -------
    dict mapping run_number (int) -> {
        "subruns"          : sorted list of subrun numbers seen in the log,
        "subrun_status"    : {subrun: "good" | "bad"},
        "classification"   : "good" | "partial" | "bad" | "mixed",
        "last_good_subrun" : int or None,
        "first_bad_subrun" : int or None,
        "n_good"           : int,
        "n_bad"            : int,
    }
    """
    df = pd.read_csv(log_path)
    if df.empty:
        return {}

    parsed = df["filename"].apply(lambda f: pd.Series(_parse_run_subrun(f),
                                                       index=["run", "subrun"]))
    df = pd.concat([df, parsed], axis=1).dropna(subset=["run", "subrun"])
    df["run"]    = df["run"].astype(int)
    df["subrun"] = df["subrun"].astype(int)

    # Per-subrun anomaly fraction (mirrors monitor.py's process_file logic)
    per_subrun = (
        df.groupby(["run", "subrun"])
          .agg(total=("channel", "count"), n_bad=("anomalous", "sum"))
          .assign(frac_bad=lambda x: x["n_bad"] / x["total"])
          .reset_index()
    )
    per_subrun["is_bad"] = per_subrun["frac_bad"] >= file_alert_threshold

    runs: dict = {}
    for run, grp in per_subrun.groupby("run"):
        grp = grp.sort_values("subrun")
        subruns = grp["subrun"].tolist()
        subrun_status = {
            int(row["subrun"]): ("bad" if row["is_bad"] else "good")
            for _, row in grp.iterrows()
        }

        good_subruns = [s for s in subruns if subrun_status[s] == "good"]
        bad_subruns  = [s for s in subruns if subrun_status[s] == "bad"]

        last_good = max(good_subruns) if good_subruns else None
        first_bad = min(bad_subruns)  if bad_subruns  else None

        if not bad_subruns:
            classification = "good"
        elif not good_subruns:
            classification = "bad"
        elif first_bad > last_good:
            # All good subruns come before all bad subruns → clean transition
            classification = "partial"
        else:
            # Good and bad subruns interleaved
            classification = "mixed"

        runs[int(run)] = {
            "subruns":           subruns,
            "subrun_status":     subrun_status,
            "classification":    classification,
            "last_good_subrun":  last_good,
            "first_bad_subrun":  first_bad,
            "n_good":            len(good_subruns),
            "n_bad":             len(bad_subruns),
        }

    return runs


# ── Output writers ───────────────────────────────────────────────────────────

def write_report(runs: dict, out_dir: Path) -> None:
    """Write good_runs.txt, partial_good_runs.txt, and run_summary.csv."""
    out_dir.mkdir(parents=True, exist_ok=True)

    good    = sorted(r for r, v in runs.items() if v["classification"] == "good")
    partial = sorted(r for r, v in runs.items() if v["classification"] == "partial")
    bad     = sorted(r for r, v in runs.items() if v["classification"] == "bad")
    mixed   = sorted(r for r, v in runs.items() if v["classification"] == "mixed")

    # good_runs.txt
    good_path = out_dir / "good_runs.txt"
    with open(good_path, "w") as fh:
        fh.write("# Runs where every subrun is nominal\n")
        for r in good:
            v = runs[r]
            fh.write(f"run{r}  ({v['n_good']} subrun(s))\n")
    print(f"  {good_path.name}  →  {len(good)} run(s): {good}")

    # partial_good_runs.txt
    partial_path = out_dir / "partial_good_runs.txt"
    with open(partial_path, "w") as fh:
        fh.write("# Runs that start nominal then transition to anomalous\n")
        fh.write("# Columns: run  n_good_subruns  n_bad_subruns"
                 "  last_good_subrun  first_bad_subrun\n")
        for r in partial:
            v = runs[r]
            fh.write(
                f"run{r}  "
                f"n_good={v['n_good']}  n_bad={v['n_bad']}  "
                f"last_good_subrun={v['last_good_subrun']}  "
                f"first_bad_subrun={v['first_bad_subrun']}\n"
            )
    print(f"  {partial_path.name}  →  {len(partial)} run(s): {partial}")

    if bad:
        print(f"  bad runs   ({len(bad)}): {bad}   [not written to file]")
    if mixed:
        print(f"  mixed runs ({len(mixed)}): {mixed}   [not written to file]")

    # run_summary.csv — full breakdown of every run
    summary_path = out_dir / "run_summary.csv"
    rows = [
        {
            "run":              r,
            "classification":   v["classification"],
            "n_good_subruns":   v["n_good"],
            "n_bad_subruns":    v["n_bad"],
            "last_good_subrun": v["last_good_subrun"],
            "first_bad_subrun": v["first_bad_subrun"],
        }
        for r, v in sorted(runs.items())
    ]
    pd.DataFrame(rows).to_csv(summary_path, index=False)
    print(f"  {summary_path.name}  →  {len(rows)} run(s) total")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify runs from the anomaly log into quality categories."
    )
    parser.add_argument(
        "--log-file",
        default="logs/anomalies.csv",
        help="Path to the anomaly log produced by monitor.py (default: logs/anomalies.csv)",
    )
    parser.add_argument(
        "--out-dir",
        default="reports",
        help="Directory to write output files (default: reports/)",
    )
    parser.add_argument(
        "--file-alert-threshold",
        type=float,
        default=0.20,
        metavar="FRAC",
        help="Fraction of anomalous channels that marks a subrun as bad "
             "(default: 0.20, same as monitor.py)",
    )
    args = parser.parse_args()

    if not Path(args.log_file).exists():
        print(f"ERROR: log file not found: {args.log_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {args.log_file} ...")
    runs = classify_runs(args.log_file, args.file_alert_threshold)

    if not runs:
        print("No runs found in log.", file=sys.stderr)
        sys.exit(1)

    write_report(runs, Path(args.out_dir))


if __name__ == "__main__":
    main()
