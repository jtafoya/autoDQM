#!/usr/bin/env python3
"""
Compare training-fraction scan outputs — one summary figure for all fractions.

Collapses the per-fraction reports produced by the batch_submit.sh scan
(train → apply → combine DAG) into a single PDF, instead of five separate
report/plot directories.

Ground truth: the good_run_list_TRAINING.txt text list (the same list the
models are trained on).  All metrics are read from each model's
eval_confusion_data.json — nothing is recomputed here.

Scan dimension:
  training fraction ∈ whatever trainFrac<F> tags exist under the reports dir
  (batch_submit.sh default: 0.1, 0.2, 0.3, 0.4, 0.5)

Layout:
  panels : known-good subruns | not-certified subruns
  lines  : verdict rates (ok / warn / pend / alert), colour per verdict
  x-axis : training fraction

Produces one PDF in _auxiliar_scripts/plots/:
  scan_trainFrac_summary_rel.pdf

Also prints a per-fraction table of counts to stdout.

Usage (from _auxiliar_scripts/):
    python compare_scan_trainFrac.py

Default paths are resolved relative to this script and can be overridden:
  --reports-dir  (default ../reports/scan_trainFracSweep)
  --out-dir      (default _auxiliar_scripts/plots/)
"""

import argparse
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

# ── Verdict → (label, colour) — shared by both panels ─────────────────────────

VERDICTS = {
    "ok":    ("ok",    "#2ca02c"),
    "warn":  ("warn",  "#ff7f0e"),
    "pend":  ("pend",  "#7f7f7f"),
    "alert": ("alert", "#d62728"),
}

# Ground-truth group → panel title.  On known-good subruns ok = TN and
# alert = FP; on not-certified subruns ok = possible FN and alert = possible TP.
GT_GROUPS = {
    "known_good":    "known-good subruns  (ok = TN, alert = FP)",
    "not_certified": "not-certified subruns  (ok = poss. FN, alert = poss. TP)",
}

# ── Tag parsing ───────────────────────────────────────────────────────────────

_FRAC_RE = re.compile(r"trainFrac(\d+(?:p\d+)?)")


def parse_tag(tag: str) -> "float | None":
    """Extract the training fraction from a model tag ('0p1' → 0.1)."""
    m = _FRAC_RE.search(tag)
    if m is None:
        return None
    return float(m.group(1).replace("p", "."))


# ── Data collection ───────────────────────────────────────────────────────────

def collect(reports_dir: Path) -> list[dict]:
    """One row per model: fraction + per-group verdict counts and totals."""
    rows = []
    skipped = 0
    for tag_dir in sorted(reports_dir.iterdir()):
        if not tag_dir.is_dir():
            continue
        frac = parse_tag(tag_dir.name)
        if frac is None:
            continue
        confusion_path = tag_dir / "eval_confusion_data.json"
        try:
            with open(confusion_path) as fh:
                data = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            skipped += 1
            continue
        rows.append({
            "tag":      tag_dir.name,
            "fraction": frac,
            "counts":   data.get("counts", {}),
            "totals":   data.get("totals", {}),
        })
    if skipped:
        print(f"  Skipped {skipped} model(s) — eval_confusion_data.json missing or unreadable.",
              file=sys.stderr)
    rows.sort(key=lambda r: r["fraction"])
    print(f"  Loaded {len(rows)} completed model(s).")
    return rows


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_table(rows: list[dict]) -> None:
    header = f"  {'frac':>5}"
    for group in GT_GROUPS:
        for verdict in VERDICTS:
            header += f"  {group[:2]}_{verdict:<5}"
        header += f"  {group[:2]}_total"
    print(header)
    for r in rows:
        line = f"  {r['fraction']:>5.2f}"
        for group in GT_GROUPS:
            counts = r["counts"].get(group, {})
            for verdict in VERDICTS:
                line += f"  {counts.get(verdict, 0):>8}"
            line += f"  {r['totals'].get(group, 0):>8}"
        print(line)


def make_figure(rows: list[dict]) -> plt.Figure:
    fractions = [r["fraction"] for r in rows]

    fig, axes = plt.subplots(
        1, len(GT_GROUPS),
        figsize=(5.5 * len(GT_GROUPS), 5),
        sharey=True,
        constrained_layout=True,
    )

    fig.suptitle(
        "Training-fraction scan — verdict rates per fraction\n"
        "ground truth: training text list  |  one model per fraction, "
        "applied to the full run list",
        fontsize=12, fontweight="bold",
    )

    for ax, (group, panel_title) in zip(axes, GT_GROUPS.items()):
        n_total = max(r["totals"].get(group, 0) for r in rows)
        ax.set_title(f"{panel_title}\nN = {n_total}", fontsize=10)
        ax.set_xlabel("training fraction", fontsize=9)
        ax.set_xticks(fractions)
        ax.set_ylim(0, 100)
        ax.yaxis.set_major_locator(MultipleLocator(10))
        ax.yaxis.set_minor_locator(MultipleLocator(5))
        ax.grid(True, which="major", alpha=0.3)
        ax.yaxis.grid(True, which="minor", alpha=0.15)

        for verdict, (label, colour) in VERDICTS.items():
            xs, ys = [], []
            for r in rows:
                total = r["totals"].get(group, 0)
                if total == 0:
                    continue
                xs.append(r["fraction"])
                ys.append(100 * r["counts"].get(group, {}).get(verdict, 0) / total)
            ax.plot(xs, ys, marker="o", markersize=4, color=colour, label=label)

    axes[0].set_ylabel("subrun fraction  (%)", fontsize=9)
    axes[-1].legend(title="verdict", fontsize=8, title_fontsize=9, loc="best")
    return fig


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--reports-dir", type=Path,
                        default=script_dir.parent / "reports" / "scan_trainFracSweep")
    parser.add_argument("--out-dir", type=Path, default=script_dir / "plots")
    args = parser.parse_args()

    if not args.reports_dir.is_dir():
        sys.exit(f"ERROR: reports dir not found: {args.reports_dir}")

    print(f"Reading reports from {args.reports_dir}")
    rows = collect(args.reports_dir)
    if not rows:
        sys.exit("ERROR: no trainFrac model reports found — has the scan's combine phase run?")

    print_table(rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / "scan_trainFrac_summary_rel.pdf"
    fig = make_figure(rows)
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Summary figure → {out_path}")


if __name__ == "__main__":
    main()
