"""
Classify runs from the anomaly log into quality categories.

Reads logs/anomalies.csv (produced by monitor.py) and writes three files:

  good_runs.txt               — runs where every subrun is nominal
  partial_good_runs.txt       — runs that start nominal then transition to anomalous
  persistent_fault_runs.txt   — runs with a channel anomalous in every subrun (below per-file threshold)
  run_summary.csv             — full per-run breakdown (all categories)

A subrun is "bad" if the fraction of anomalous channels meets or exceeds
--file-alert-n-channels (same default as monitor.py: 2).

A run is classified as:
  good              — all subruns good, no persistent channel faults
  partial           — at least one good subrun and at least one bad subrun, and the first
                      bad subrun comes strictly after the last good subrun (clean transition)
  bad               — all subruns bad
  mixed             — good and bad subruns interleaved (no clean transition)
  persistent_fault  — all subruns appear "good" by per-file threshold, but one or more
                      channels are anomalous in every subrun (e.g. a dead or missing channel)

Public API
----------
step_report(log_file, reports_dir, file_alert_n_channels)
    Pipeline step called by pipeline.py: auto-skip guard + classify + write.
classify_runs(log_path, file_alert_n_channels)
    Core classification logic; returns a per-run dict.
write_report(runs, out_dir)
    Writes good_runs.txt, partial_good_runs.txt, persistent_fault_runs.txt,
    and run_summary.csv.

Usage:
    python3 -m src.report
    python3 -m src.report --log-file logs/anomalies.csv --out-dir logs/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .args import preparse_config, add_config
from .config import print_step_header
from .run_list import parse_run_subrun


# ── Core logic ───────────────────────────────────────────────────────────────


def classify_runs(log_path: str, file_alert_n_channels: int = 2) -> dict:
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

    parsed = df["filename"].apply(lambda f: pd.Series(parse_run_subrun(f),
                                                       index=["run", "subrun"]))
    df = pd.concat([df, parsed], axis=1).dropna(subset=["run", "subrun"])
    df["run"]    = df["run"].astype(int)
    df["subrun"] = df["subrun"].astype(int)

    # Per-subrun anomaly count (mirrors monitor.py's process_file logic)
    per_subrun = (
        df.groupby(["run", "subrun"])
          .agg(total=("channel", "count"), n_bad=("anomalous", "sum"))
          .reset_index()
    )
    per_subrun["is_bad"] = per_subrun["n_bad"] >= file_alert_n_channels

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

        # Persistent channel check: a channel anomalous in every subrun of this run
        # is a systematic fault (e.g. dead/missing channel) that may not push any
        # individual subrun above the per-file threshold.
        run_df = df[df["run"] == run]
        n_subruns = len(subruns)
        channel_flags = (
            run_df.groupby(["channel", "subrun"])["anomalous"]
                  .any()
                  .groupby("channel")
                  .sum()
        )
        persistent_channels = sorted(
            channel_flags[channel_flags >= n_subruns].index.tolist(),
            key=str,
        )

        # Upgrade classification if persistent channels detected but per-file
        # threshold never triggered (run otherwise looks "good").
        # Require at least 2 subruns to avoid trivial 1/1 matches from sampling noise.
        if persistent_channels and classification == "good" and n_subruns >= 2:
            classification = "persistent_fault"

        runs[int(run)] = {
            "subruns":              subruns,
            "subrun_status":        subrun_status,
            "classification":       classification,
            "last_good_subrun":     last_good,
            "first_bad_subrun":     first_bad,
            "n_good":               len(good_subruns),
            "n_bad":                len(bad_subruns),
            "persistent_channels":  persistent_channels,
        }

    return runs


# ── Output writers ───────────────────────────────────────────────────────────

def write_report(runs: dict, out_dir: Path) -> None:
    """Write good_runs.txt, partial_good_runs.txt, and run_summary.csv."""
    out_dir.mkdir(parents=True, exist_ok=True)

    good       = sorted(r for r, v in runs.items() if v["classification"] == "good")
    partial    = sorted(r for r, v in runs.items() if v["classification"] == "partial")
    bad        = sorted(r for r, v in runs.items() if v["classification"] == "bad")
    mixed      = sorted(r for r, v in runs.items() if v["classification"] == "mixed")
    persistent = sorted(r for r, v in runs.items() if v["classification"] == "persistent_fault")

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

    # persistent_fault_runs.txt
    persistent_path = out_dir / "persistent_fault_runs.txt"
    with open(persistent_path, "w") as fh:
        fh.write("# Runs where one or more channels are anomalous in every subrun\n")
        fh.write("# (systematic fault — e.g. dead/missing channel — below per-file threshold)\n")
        fh.write("# Columns: run  n_subruns  persistent_channels\n")
        for r in persistent:
            v = runs[r]
            fh.write(
                f"run{r}  "
                f"n_subruns={v['n_good']}  "
                f"persistent_channels={v['persistent_channels']}\n"
            )
    print(f"  {persistent_path.name}  →  {len(persistent)} run(s): {persistent}")

    if bad:
        print(f"  bad runs   ({len(bad)}): {bad}   [not written to file]")
    if mixed:
        print(f"  mixed runs ({len(mixed)}): {mixed}   [not written to file]")

    # run_summary.csv — full breakdown of every run
    summary_path = out_dir / "run_summary.csv"
    rows = [
        {
            "run":                 r,
            "classification":      v["classification"],
            "n_good_subruns":      v["n_good"],
            "n_bad_subruns":       v["n_bad"],
            "last_good_subrun":    v["last_good_subrun"],
            "first_bad_subrun":    v["first_bad_subrun"],
            "persistent_channels": ";".join(str(c) for c in v["persistent_channels"]),
        }
        for r, v in sorted(runs.items())
    ]
    pd.DataFrame(rows).to_csv(summary_path, index=False)
    print(f"  {summary_path.name}  →  {len(rows)} run(s) total")


# ── Pipeline step ────────────────────────────────────────────────────────────

def step_report(log_file: Path, reports_dir: Path, file_alert_n_channels: int) -> bool:
    """
    Classify runs as good / partial / bad and write run_summary.csv to reports_dir.

    Returns True when the step ran, False when auto-skipped because run_summary.csv
    already exists.
    """
    print_step_header("STEP 4 — REPORT")

    if (reports_dir / "run_summary.csv").exists():
        print(f"[AUTO-SKIP] Report — {reports_dir}/run_summary.csv already exists.")
        print(f"            Delete {reports_dir}/ to regenerate.")
        return False

    runs = classify_runs(str(log_file), file_alert_n_channels)
    if not runs:
        print("  No runs found in log — skipping report.")
        return True
    write_report(runs, reports_dir)
    return True


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    _, cfg = preparse_config()

    tag = cfg["model_tag"]

    parser = argparse.ArgumentParser(
        description="Classify runs from the anomaly log into quality categories."
    )
    add_config(parser)
    parser.add_argument(
        "--log-file",
        help="Path to the anomaly log produced by monitor.py",
    )
    parser.add_argument(
        "--out-dir",
        help="Directory to write output files",
    )
    parser.add_argument(
        "--file-alert-n-channels",
        type=int,
        metavar="N",
        help="Number of anomalous channels that marks a subrun as bad",
    )

    parser.set_defaults(
        log_file             = str(Path(cfg["logs_dir"])    / f"{tag}.csv"),
        out_dir              = str(Path(cfg["reports_dir"]) / tag),
        file_alert_n_channels = cfg["file_alert_n_channels"],
    )

    args = parser.parse_args()

    from .config import print_banner
    print_banner("report", args.config, [
        ("log file",             args.log_file),
        ("out dir",              args.out_dir),
        ("alert threshold",      f"{args.file_alert_n_channels} channels"),
    ])

    if not Path(args.log_file).exists():
        print(f"ERROR: log file not found: {args.log_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {args.log_file} ...")
    runs = classify_runs(args.log_file, args.file_alert_n_channels)

    if not runs:
        print("No runs found in log.", file=sys.stderr)
        sys.exit(1)

    write_report(runs, Path(args.out_dir))


if __name__ == "__main__":
    main()
