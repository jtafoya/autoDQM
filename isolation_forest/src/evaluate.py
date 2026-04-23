"""
Evaluate the anomaly detector against the goodRunsListSlab.json ground truth.

Reads the anomaly log produced by the apply step, replays the full alert logic
(persistence + bulk + extreme) to assign per-subrun predicted status
(ok / warn / pend / alert), then cross-references each subrun against the
goodRunsListSlab.json catalogue to compute:

  Known good (quality ≥ threshold):
    True Negative  (TN) : predicted ok
    Mild anomaly        : predicted warn   (anomaly present but below alert threshold)
    Unconfirmed (PEND)  : predicted pend   (too few within-run subruns to confirm)
    False Positive (FP) : predicted alert

  Not certified good (in catalogue, all quality flags = 0):
    Possible FN         : predicted ok
    Mild anomaly        : predicted warn
    Unconfirmed (PEND)  : predicted pend
    Possible TP         : predicted alert

  Unknown (not in catalogue): shown separately.

Outputs:
  <out_dir>/eval_summary.txt         — printed evaluation table
  <out_dir>/eval_confusion_data.json — counts/totals serialised for the confusion plot
                                       (rendered by the plots step via src.plot)
  <out_dir>/framework_good_runs.json — JSON in goodRunsListSlab format listing
                                       subruns with their framework quality flags

Quality mapping in framework_good_runs.json (same column order as goodRunsListSlab):
  Tight  = predicted ok only (most conservative — no anomalies, past probation)
  Medium = predicted ok or warn (anomaly present but not persisted to alert level)
  Loose  = predicted ok, warn, or pend (includes run-start unconfirmed subruns)
  All zero → predicted alert (framework considers the subrun anomalous)

Usage:
    python3 -m src.evaluate \\
        --log-file logs/myrun_Tight.csv \\
        --json-path /path/to/goodRunsListSlab.json \\
        --out-dir reports/myrun_Tight/ \\
        --gt-quality Tight
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

from .run_list import (
    _COL_RUN, _COL_FILE,
    _COL_GOOD_RUN_LOOSE, _COL_GOOD_RUN_MEDIUM, _COL_GOOD_RUN_TIGHT,
    QUALITY_ALL_CHOICES,
)


_FILENAME_RE = re.compile(r"Digitizer_run(\d+)_subrun(\d+)", re.IGNORECASE)  # extracts run/subrun from filenames

_STAT_ORDER = ["ok", "warn", "pend", "alert"]          # canonical predicted-status ordering
_GT_ORDER   = ["known_good", "not_certified", "unknown"]  # canonical ground-truth category ordering


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_run_subrun(filename: str):
    """Return (run, subrun) ints from a Digitizer filename, or (None, None) if unparseable."""
    m = _FILENAME_RE.search(str(filename))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _load_catalogue(json_path: str) -> dict:
    """Return dict mapping (run, subrun) → {loose, medium, tight, any_good}."""
    with open(json_path) as fh:
        cat = json.load(fh)
    lookup = {}
    for row in cat["data"]:
        run, subrun = row[_COL_RUN], row[_COL_FILE]
        loose  = bool(row[_COL_GOOD_RUN_LOOSE])
        medium = bool(row[_COL_GOOD_RUN_MEDIUM])
        tight  = bool(row[_COL_GOOD_RUN_TIGHT])
        lookup[(run, subrun)] = {
            "loose":    loose,
            "medium":   medium,
            "tight":    tight,
            "any_good": loose or medium or tight,
        }
    return lookup


# ── Core step ─────────────────────────────────────────────────────────────────

def step_evaluate(
    log_file: Path,
    json_path: str,
    out_dir: Path,
    file_alert_n_channels: int = 2,
    alert_consecutive_n: int = 1,
    single_file_alert_n_channels: int = 0,
    single_file_alert_max_z: float = 0.0,
    gt_quality: str = "Tight",
) -> bool:
    """
    Compare per-subrun predicted status against goodRunsListSlab.json ground truth.

    Parameters
    ----------
    log_file : Path
        Anomaly log produced by the apply step.
    json_path : str
        Path to goodRunsListSlab.json.
    out_dir : Path
        Directory for eval_summary.txt, eval_confusion_data.json, and
        framework_good_runs.json.
    file_alert_n_channels : int
        Persistent alert threshold (channels).
    alert_consecutive_n : int
        Persistence window (consecutive files).
    single_file_alert_n_channels : int
        Bulk single-file alert threshold (0 = disabled).
    single_file_alert_max_z : float
        Extreme single-file alert threshold (0 = disabled).
    gt_quality : str
        Quality level used to define 'known good' ground truth
        (Loose / Medium / Tight / All).

    Returns
    -------
    bool
        True when evaluation ran, False when auto-skipped.
    """
    from .plot import _compute_persistence_status

    eval_summary_path = out_dir / "eval_summary.txt"
    if eval_summary_path.exists():
        print(f"[AUTO-SKIP] Evaluate — {eval_summary_path} already exists.")
        print(f"            Delete {out_dir}/ to regenerate.")
        return False

    if not Path(json_path).exists():
        print(
            f"  [SKIP] Evaluate — catalogue not found: {json_path}\n"
            f"         Set full_sample_json in config.yaml to enable evaluation.",
            file=sys.stderr,
        )
        return True

    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(str(log_file))
    if df.empty:
        print("  [evaluate] Log file is empty — skipping.")
        return True

    # Replay the full alert logic over the log
    n_files = df["filename"].nunique()
    print(f"  Replaying alert logic on {n_files} subruns ...")
    status_df = _compute_persistence_status(
        df,
        file_alert_n_channels=file_alert_n_channels,
        alert_consecutive_n=alert_consecutive_n,
        single_file_alert_n_channels=single_file_alert_n_channels,
        single_file_alert_max_z=single_file_alert_max_z,
    )

    cat = _load_catalogue(json_path)
    print(f"  Loaded catalogue: {len(cat):,} run+subrun entries.")

    # Classify each subrun: ground-truth category + predicted status
    rows = []
    for _, row in status_df.iterrows():
        run, subrun = _parse_run_subrun(row["filename"])
        if run is None:
            continue
        pred = row["status"]

        if (run, subrun) in cat:
            q = cat[(run, subrun)]
            is_good = q["any_good"] if gt_quality == "All" else q[gt_quality.lower()]
            gt = "known_good" if is_good else "not_certified"
        else:
            gt = "unknown"

        rows.append({"run": run, "subrun": subrun, "status": pred, "gt": gt})

    eval_df = pd.DataFrame(rows)

    # Aggregate: gt category × predicted status
    counts: dict = {g: defaultdict(int) for g in _GT_ORDER}
    for _, r in eval_df.iterrows():
        counts[r["gt"]][r["status"]] += 1
    totals = {g: sum(counts[g].values()) for g in _GT_ORDER}

    # ── Printed summary ────────────────────────────────────────────────────────
    lines = [
        "",
        f"  {'─'*62}",
        f"  EVALUATION SUMMARY",
        f"  Ground truth quality level : {gt_quality}",
        f"  Total subruns in log       : {len(eval_df)}",
        f"  {'─'*62}",
    ]

    gt_label_long = {
        "known_good":    f"Known good ({gt_quality}) (N={totals['known_good']})",
        "not_certified": f"Not certified good (N={totals['not_certified']})",
        "unknown":       f"Unknown — not in catalogue (N={totals['unknown']})",
    }

    for g in _GT_ORDER:
        n = totals[g]
        if n == 0:
            continue
        lines.append(f"\n  {gt_label_long[g]}")
        for s in _STAT_ORDER:
            c = counts[g][s]
            pct = c / n * 100 if n else 0
            lines.append(f"    {s:<8} : {c:>6}  ({pct:>5.1f}%)")

    # Summary rates
    n_kg = totals["known_good"]
    if n_kg:
        tn  = counts["known_good"]["ok"]
        fp  = counts["known_good"]["alert"]
        fw  = counts["known_good"]["warn"]
        fu  = counts["known_good"]["pend"]
        lines += [
            "",
            f"  ── Rates on known-good subruns ──",
            f"    True Negative  (ok)    : {tn:>6}  ({tn /n_kg*100:>5.1f}%)",
            f"    Mild anomaly   (warn)  : {fw:>6}  ({fw /n_kg*100:>5.1f}%)",
            f"    Unconfirmed    (pend)  : {fu:>6}  ({fu /n_kg*100:>5.1f}%)",
            f"    False Positive (alert) : {fp:>6}  ({fp /n_kg*100:>5.1f}%)",
        ]

    n_nc = totals["not_certified"]
    if n_nc:
        poss_fn = counts["not_certified"]["ok"]
        w_nc    = counts["not_certified"]["warn"]
        p_nc    = counts["not_certified"]["pend"]
        poss_tp = counts["not_certified"]["alert"]
        lines += [
            "",
            f"  ── Rates on not-certified subruns ──",
            f"    Possible FN    (ok)    : {poss_fn:>6}  ({poss_fn/n_nc*100:>5.1f}%)",
            f"    Mild anomaly   (warn)  : {w_nc:>6}  ({w_nc  /n_nc*100:>5.1f}%)",
            f"    Unconfirmed    (pend)  : {p_nc:>6}  ({p_nc  /n_nc*100:>5.1f}%)",
            f"    Possible TP    (alert) : {poss_tp:>6}  ({poss_tp/n_nc*100:>5.1f}%)",
        ]

    lines.append(f"\n  {'─'*62}")
    summary_text = "\n".join(lines)
    print(summary_text)

    eval_summary_path.write_text(summary_text.lstrip("\n"))
    print(f"\n  Evaluation summary → {eval_summary_path}")

    # ── Confusion data + framework JSON ───────────────────────────────────────
    confusion_path = out_dir / "eval_confusion_data.json"
    with open(confusion_path, "w") as fh:
        json.dump(
            {
                "gt_quality": gt_quality,
                "counts":     {g: dict(counts[g]) for g in _GT_ORDER},
                "totals":     totals,
            },
            fh,
            indent=2,
        )
    print(f"  Confusion data → {confusion_path}")

    _write_framework_json(eval_df, out_dir)

    return True


# ── JSON writer ───────────────────────────────────────────────────────────────

def _write_framework_json(eval_df: "pd.DataFrame", out_dir: Path) -> None:
    """
    Write framework_good_runs.json in goodRunsListSlab column order:
      [run, subrun, loose, medium, tight, 0, "autoDQM_IF"]

    Tight  = predicted ok  (no anomalies, past probation window)
    Medium = predicted ok or warn
    Loose  = predicted ok, warn, or pend
    0/0/0  = predicted alert (framework considers the subrun anomalous)
    """
    data = []
    for _, row in eval_df.sort_values(["run", "subrun"]).iterrows():
        s      = row["status"]
        tight  = 1 if s == "ok"                   else 0
        medium = 1 if s in ("ok", "warn")          else 0
        loose  = 1 if s in ("ok", "warn", "pend")  else 0
        data.append([
            int(row["run"]), int(row["subrun"]),
            loose, medium, tight,
            0, "autoDQM_IF",
        ])

    out_path = out_dir / "framework_good_runs.json"
    with open(out_path, "w") as fh:
        json.dump({"data": data}, fh, indent=2)

    n_tight  = sum(1 for r in data if r[4])
    n_medium = sum(1 for r in data if r[3])
    n_loose  = sum(1 for r in data if r[2])
    print(f"  Framework good runs JSON → {out_path}")
    print(f"    Tight={n_tight}  Medium={n_medium}  Loose={n_loose}"
          f"  (total subruns: {len(data)})")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    from .args import preparse_config, add_config, add_alert_thresholds

    _, cfg = preparse_config()
    tag = cfg["model_tag"]

    parser = argparse.ArgumentParser(
        description="Evaluate the anomaly detector against goodRunsListSlab.json ground truth."
    )
    add_config(parser)
    parser.add_argument("--log-file",  help="Anomaly log produced by the apply step")
    parser.add_argument("--json-path", help="Path to goodRunsListSlab.json")
    parser.add_argument("--out-dir",   help="Directory for eval_summary.txt, eval_confusion_data.json, and framework_good_runs.json")
    parser.add_argument(
        "--gt-quality",
        choices=QUALITY_ALL_CHOICES,
        metavar="{" + ",".join(QUALITY_ALL_CHOICES) + "}",
        help="Quality level used to define 'known good' ground truth (default: %(default)s)",
    )
    add_alert_thresholds(parser, cfg)

    parser.set_defaults(
        log_file   = str(Path(cfg["logs_dir"])    / f"{tag}.csv"),
        json_path  = cfg.get("full_sample_json", ""),
        out_dir    = str(Path(cfg["reports_dir"]) / tag),
        gt_quality = "Tight",
    )

    args = parser.parse_args()

    from .config import print_banner
    print_banner("evaluate", args.config, [
        ("log file",             args.log_file),
        ("catalogue",            args.json_path),
        ("out dir",              args.out_dir),
        ("gt quality",           args.gt_quality),
        ("alert threshold",      f"{args.file_alert_n_channels} channels"),
        ("alert window",         f"{args.alert_consecutive_n} consecutive file(s)"),
        ("bulk alert",           f"{args.single_file_alert_n_channels} ch"
                                 if args.single_file_alert_n_channels else "disabled"),
        ("extreme alert",        f"z≥{args.single_file_alert_max_z}"
                                 if args.single_file_alert_max_z else "disabled"),
    ])

    step_evaluate(
        log_file                     = Path(args.log_file),
        json_path                    = args.json_path,
        out_dir                      = Path(args.out_dir),
        file_alert_n_channels        = args.file_alert_n_channels,
        alert_consecutive_n          = args.alert_consecutive_n,
        single_file_alert_n_channels = args.single_file_alert_n_channels,
        single_file_alert_max_z      = args.single_file_alert_max_z,
        gt_quality                   = args.gt_quality,
    )


if __name__ == "__main__":
    main()
