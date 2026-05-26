#!/usr/bin/env python3
"""
Compare 260521 applyToRuns outputs — FP/TN rates and per-run ok-rate profiles.

Models are applied run-by-run to runs 1601–2238, scoring 20 % of each run's
subruns.  This script shows:
  • FP rate (% known-good subruns flagged as alert) vs contamination
  • TN rate (% known-good subruns correctly called ok) vs contamination
  • Per-run goodness (% subruns classified as ok per run)

Ground truth source: good_run_list_TRAINING.txt (text list, no external catalogue).
FP/TN are read from eval_confusion_data.json; per-run goodness from
framework_good_runs.json.

Layout per PDF:
  pages   : one per z_threshold (6,7,8σ) × trigger-config variant (with / without) = 6 pages
  columns : FP rate | TN rate | per-run goodness
  lines   : 4 feature variants (colour) × 5 alert_consecutive_n (line style + hollow marker)
  FP/TN x-axis         : contamination (log scale)
  per-run goodness panel: run number — fixed contamination (--contamination)

Produces two PDFs in _auxiliar_scripts/plots/:
  applyToRuns_260521_counts.pdf  — FP/TN absolute counts + per-run profile
  applyToRuns_260521_rel.pdf     — FP/TN rates (%) + per-run profile

Usage (from _auxiliar_scripts/):
    python compare_applyToRuns_260521.py
    python compare_applyToRuns_260521.py --contamination 0.001

Paths are resolved relative to this script:
  reports  → ../reports/applyToRuns_260521
  plots    → _auxiliar_scripts/plots/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from itertools import groupby
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
from matplotlib.ticker import MultipleLocator, NullLocator

# ── Sweep dimensions ──────────────────────────────────────────────────────────

CONTAMINATIONS = [0.001, 0.005, 0.01, 0.05]
Z_THRESHOLDS   = [6, 7, 8]
CONSEC_VALUES  = [1, 2, 3, 4, 5]

# Feature variant → (label, colour)
VARIANT_META = {
    (False, False): ("digi only",        "#444444"),
    (True,  False): ("+ trigger rates",  "#1f77b4"),
    (False, True):  ("+ LVDS counts",    "#ff7f0e"),
    (True,  True):  ("+ trigger + LVDS", "#2ca02c"),
}

# alert_consecutive_n → (label, line style, hollow marker)
CONSEC_STYLE = {
    1: ("consec=1", "-",               "o"),
    2: ("consec=2", "--",              "s"),
    3: ("consec=3", "-.",              "^"),
    4: ("consec=4", ":",               "D"),
    5: ("consec=5", (0, (3, 1, 1, 1)), "v"),
}

METRIC_COLS_COUNTS = [
    ("fp_count_subruns", "FP count\n# known-good flagged as alert"),
    ("tn_count_subruns", "TN count\n# known-good correctly called ok"),
]
METRIC_COLS_REL = [
    ("fp_rel_subruns", "FP rate\n% known-good flagged as alert"),
    ("tn_rel_subruns", "TN rate\n% known-good correctly called ok"),
]

# ── Tag parsing ───────────────────────────────────────────────────────────────

_CONT_RE   = re.compile(r"ifContamination_([0-9p]+)")
_Z_RE      = re.compile(r"zThreshold_(\d+)sigma")
_CONSEC_RE = re.compile(r"alertConsec_(\d+)")


def _cont_to_float(s: str) -> float:
    return float(s.replace("p", "."))


def parse_tag(tag: str) -> "dict | None":
    if "260521" not in tag:
        return None
    mc = _CONT_RE.search(tag)
    mz = _Z_RE.search(tag)
    mn = _CONSEC_RE.search(tag)
    if not (mc and mz and mn):
        return None
    return {
        "tag":                    tag,
        "if_contamination":       _cont_to_float(mc.group(1)),
        "z_threshold":            int(mz.group(1)),
        "alert_consecutive_n":    int(mn.group(1)),
        "use_trigger":            "_noTrigger"           not in tag,
        "use_lvds":               "_noLVDS"              not in tag,
        "include_trigger_config": "_ignoreTriggerConfig" not in tag,
    }


# ── Per-model metrics ─────────────────────────────────────────────────────────

def load_metrics(reports_dir: Path) -> "dict | None":
    """Read FP/TN and per-run ok-rates from eval and framework JSON files."""
    confusion_path = reports_dir / "eval_confusion_data.json"
    fw_path        = reports_dir / "framework_good_runs.json"

    metrics: dict = {}

    # FP/TN from confusion data
    if confusion_path.exists():
        try:
            with open(confusion_path) as f:
                data = json.load(f)
            counts   = data.get("counts", {})
            totals   = data.get("totals", {})
            kg_total = totals.get("known_good", 0)
            if kg_total > 0:
                kg_fp = counts.get("known_good", {}).get("alert", 0)
                kg_tn = counts.get("known_good", {}).get("ok",    0)
                metrics.update({
                    "n_kg_subruns":     kg_total,
                    "fp_count_subruns": kg_fp,
                    "tn_count_subruns": kg_tn,
                    "fp_rel_subruns":   100 * kg_fp / kg_total,
                    "tn_rel_subruns":   100 * kg_tn / kg_total,
                })
        except (json.JSONDecodeError, OSError):
            pass

    # Per-run ok-rate from framework_good_runs.json
    if fw_path.exists():
        try:
            with open(fw_path) as f:
                fw = json.load(f)
            run_ok: dict = defaultdict(lambda: [0, 0])   # [n_ok, n_total]
            for row in fw.get("data", []):
                run    = int(row[0])
                is_ok  = bool(row[4])   # tight column
                run_ok[run][1] += 1
                if is_ok:
                    run_ok[run][0] += 1
            if run_ok:
                metrics["run_ok_rates"] = {
                    run: 100 * ok / n
                    for run, (ok, n) in sorted(run_ok.items()) if n
                }
        except (json.JSONDecodeError, OSError):
            pass

    return metrics if metrics else None


# ── Training run list ─────────────────────────────────────────────────────────

_RUN_RE = re.compile(r"Digitizer_run(\d+)")


def load_training_runs(path: Path) -> set[int]:
    """Return the set of run numbers listed in a good_run_list text file."""
    runs: set[int] = set()
    if not path.exists():
        print(f"  WARNING: good run list not found at {path}", file=sys.stderr)
        return runs
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _RUN_RE.search(line)
        if m:
            runs.add(int(m.group(1)))
    return runs


def _consecutive_blocks(runs: set[int]) -> list[tuple[int, int]]:
    """Group sorted run numbers into (start, end) contiguous blocks."""
    blocks = []
    for _, g in groupby(enumerate(sorted(runs)), lambda t: t[1] - t[0]):
        group = [v for _, v in g]
        blocks.append((group[0], group[-1]))
    return blocks


# ── Data collection ───────────────────────────────────────────────────────────

def collect(reports_dir: Path) -> list[dict]:
    skipped = 0
    results = []
    for tag_dir in sorted(reports_dir.iterdir()):
        if not tag_dir.is_dir():
            continue
        params = parse_tag(tag_dir.name)
        if params is None:
            continue
        metrics = load_metrics(tag_dir)
        if metrics is None:
            skipped += 1
            continue
        results.append({**params, **metrics})
    if skipped:
        print(f"  Skipped {skipped} model(s) — no metrics available.",
              file=sys.stderr)
    print(f"  Loaded {len(results)} completed model(s).")
    return results


# ── Plotting ──────────────────────────────────────────────────────────────────

def _make_figure(rows: list[dict],
                 include_trigger_config: bool,
                 metric_cols: list,
                 y_axis_unit: str,
                 z_for_fp_tn: int,
                 cont_for_profile: float,
                 training_runs: set[int] | None = None) -> plt.Figure:
    tc_label = "with triggerConfig" if include_trigger_config else "ignoring triggerConfig"
    subset   = [r for r in rows if r["include_trigger_config"] == include_trigger_config]

    fig, axes = plt.subplots(
        1, 3,
        figsize=(21, 5),
        gridspec_kw={"width_ratios": [1, 1, 2]},
        constrained_layout=True,
    )
    fig.suptitle(
        f"applyToRuns 260521  |  ground truth: training text list  |  {tc_label}\n"
        f"FP/TN columns: z = {z_for_fp_tn}σ",
        fontsize=11, fontweight="bold",
    )

    fp_tn_subset = [r for r in subset if r["z_threshold"] == z_for_fp_tn]

    for col_idx, (y_key, col_title) in enumerate(metric_cols):
        ax = axes[col_idx]
        ax.set_title(col_title, fontsize=10)
        ax.set_xlabel("if_contamination", fontsize=9)
        if col_idx == 0:
            ax.set_ylabel(f"subrun level  ({y_axis_unit})", fontsize=9)
        ax.set_xscale("log")
        ax.set_xticks(CONTAMINATIONS)
        ax.set_xticklabels([str(c) for c in CONTAMINATIONS],
                           fontsize=9, rotation=0, ha="center")
        ax.xaxis.set_minor_locator(NullLocator())
        if y_axis_unit == "%":
            ax.yaxis.set_major_locator(MultipleLocator(20))
            ax.yaxis.set_minor_locator(MultipleLocator(10))
            ax.set_ylim(0, 100)
        ax.grid(True, which="major", alpha=0.3)
        ax.yaxis.grid(True, which="minor", alpha=0.15)

        for (use_trigger, use_lvds), (var_label, colour) in VARIANT_META.items():
            for consec, (consec_label, linestyle, marker) in CONSEC_STYLE.items():
                pts = sorted(
                    [r for r in fp_tn_subset
                     if r["use_trigger"]          == use_trigger
                     and r["use_lvds"]            == use_lvds
                     and r["alert_consecutive_n"] == consec
                     and r.get(y_key) is not None],
                    key=lambda r: r["if_contamination"],
                )
                if not pts:
                    continue
                xs = [p["if_contamination"] for p in pts]
                ys = [p[y_key]              for p in pts]
                ax.plot(xs, ys, color=colour, linestyle=linestyle,
                        linewidth=1.6, marker=marker, markersize=6,
                        markerfacecolor="none", markeredgewidth=1.5)

    # ── Per-run ok-rate profile panel ─────────────────────────────────────────
    ax_run = axes[2]
    ax_run.set_title(f"% ok subruns per run  (@ contamination = {cont_for_profile})", fontsize=10)
    ax_run.set_xlabel("run number", fontsize=9)
    ax_run.set_ylabel("% ok subruns", fontsize=9)
    ax_run.set_ylim(0, 100)
    ax_run.yaxis.set_major_locator(MultipleLocator(20))
    ax_run.yaxis.set_minor_locator(MultipleLocator(10))
    ax_run.grid(True, which="major", alpha=0.3)
    ax_run.yaxis.grid(True, which="minor", alpha=0.15)

    if training_runs:
        for start, end in _consecutive_blocks(training_runs):
            ax_run.axvspan(start - 0.5, end + 0.5,
                           color="lightgray", alpha=0.35, linewidth=0, zorder=0)

    profile_subset = [
        r for r in subset
        if abs(r["if_contamination"] - cont_for_profile) < 1e-9
        and r["z_threshold"] == z_for_fp_tn
    ]
    for (use_trigger, use_lvds), (var_label, colour) in VARIANT_META.items():
        for consec, (consec_label, linestyle, marker) in CONSEC_STYLE.items():
            for r in profile_subset:
                if (r["use_trigger"] != use_trigger or r["use_lvds"] != use_lvds
                        or r["alert_consecutive_n"] != consec):
                    continue
                rr = r.get("run_ok_rates")
                if not rr:
                    continue
                xs = sorted(rr.keys())
                ys = [rr[x] for x in xs]
                ax_run.plot(xs, ys, color=colour, linestyle=linestyle,
                            linewidth=1.2, alpha=0.6,
                            marker=marker, markersize=5, markevery=40,
                            markerfacecolor="none", markeredgewidth=1.2)

    colour_handles = [
        mpatches.Patch(color=colour, label=var_label)
        for (_, _), (var_label, colour) in VARIANT_META.items()
    ]
    style_handles = [
        mlines.Line2D([], [], color="black", linestyle=ls, marker=mk,
                      markerfacecolor="none", markeredgewidth=1.5,
                      markersize=6, label=label)
        for consec, (label, ls, mk) in CONSEC_STYLE.items()
    ]
    fig.legend(
        handles=colour_handles + style_handles,
        loc="lower center",
        ncol=9,
        fontsize=8,
        framealpha=0.9,
        bbox_to_anchor=(0.5, -0.06),
    )
    return fig


def _model_label(row: dict) -> str:
    """Short human-readable label for a model row."""
    v  = VARIANT_META[(row["use_trigger"], row["use_lvds"])][0]
    tc = "withTC" if row["include_trigger_config"] else "noTC"
    return (f"c={row['if_contamination']}, z={row['z_threshold']}σ, "
            f"n_consec={row['alert_consecutive_n']}, {v}, {tc}")


def _make_best_fp_figure(rows: list[dict],
                         top_n: int,
                         training_runs: "set[int] | None" = None) -> "plt.Figure | None":
    """Per-run ok-rate profiles for the top_n models with lowest FP rate."""
    eligible = [r for r in rows
                if r.get("fp_rel_subruns") is not None and r.get("run_ok_rates")]
    if not eligible:
        return None
    ranked = sorted(eligible, key=lambda r: r["fp_rel_subruns"])[:top_n]

    fig, ax = plt.subplots(figsize=(16, 6), constrained_layout=True)
    fig.suptitle(
        f"Top {top_n} models — lowest FP rate (% known-good subruns flagged as alert)",
        fontsize=12, fontweight="bold",
    )
    ax.set_title("% ok subruns per run", fontsize=10)
    ax.set_xlabel("run number", fontsize=9)
    ax.set_ylabel("% ok subruns", fontsize=9)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_locator(MultipleLocator(20))
    ax.yaxis.set_minor_locator(MultipleLocator(10))
    ax.grid(True, which="major", alpha=0.3)
    ax.yaxis.grid(True, which="minor", alpha=0.15)

    if training_runs:
        for start, end in _consecutive_blocks(training_runs):
            ax.axvspan(start - 0.5, end + 0.5,
                       color="lightgray", alpha=0.35, linewidth=0, zorder=0)

    import matplotlib.cm as cm
    for i, r in enumerate(ranked):
        rr  = r["run_ok_rates"]
        xs  = sorted(rr.keys())
        ys  = [rr[x] for x in xs]
        lbl = f"{_model_label(r)}  [FP = {r['fp_rel_subruns']:.2f}%]"
        ax.plot(xs, ys, color=cm.tab10(i % 10), linewidth=1.5, alpha=0.85, label=lbl)

    ax.legend(fontsize=7.5, loc="lower left", framealpha=0.9)
    return fig


def _make_best_fp_per_z_figure(rows: list[dict],
                               top_n_per_z: int,
                               training_runs: "set[int] | None" = None) -> "plt.Figure | None":
    """Per-run ok-rate for the top top_n_per_z models by FP rate within each z-threshold.
    Colour encodes z-threshold; line style encodes rank within that z group."""
    eligible = [r for r in rows
                if r.get("fp_rel_subruns") is not None and r.get("run_ok_rates")]
    if not eligible:
        return None

    import matplotlib.cm as cm
    z_colour  = {z: cm.tab10(i) for i, z in enumerate(Z_THRESHOLDS)}
    rank_style = ["-", "--", "-."]

    fig, ax = plt.subplots(figsize=(16, 6), constrained_layout=True)
    fig.suptitle(
        f"Top {top_n_per_z} models per z-threshold — lowest FP rate  "
        f"({top_n_per_z * len(Z_THRESHOLDS)} models total)",
        fontsize=12, fontweight="bold",
    )
    ax.set_title("% ok subruns per run", fontsize=10)
    ax.set_xlabel("run number", fontsize=9)
    ax.set_ylabel("% ok subruns", fontsize=9)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_locator(MultipleLocator(20))
    ax.yaxis.set_minor_locator(MultipleLocator(10))
    ax.grid(True, which="major", alpha=0.3)
    ax.yaxis.grid(True, which="minor", alpha=0.15)

    if training_runs:
        for start, end in _consecutive_blocks(training_runs):
            ax.axvspan(start - 0.5, end + 0.5,
                       color="lightgray", alpha=0.35, linewidth=0, zorder=0)

    for z in Z_THRESHOLDS:
        z_rows = sorted(
            [r for r in eligible if r["z_threshold"] == z],
            key=lambda r: r["fp_rel_subruns"],
        )[:top_n_per_z]
        for rank, r in enumerate(z_rows):
            rr  = r["run_ok_rates"]
            xs  = sorted(rr.keys())
            ys  = [rr[x] for x in xs]
            lbl = f"z={z}σ rank{rank+1}: {_model_label(r)}  [FP = {r['fp_rel_subruns']:.2f}%]"
            ax.plot(xs, ys, color=z_colour[z], linestyle=rank_style[rank],
                    linewidth=1.5, alpha=0.85, label=lbl)

    ax.legend(fontsize=7.5, loc="lower left", framealpha=0.9)
    return fig


def _make_best_coverage_figure(rows: list[dict],
                                top_n: int,
                                training_runs: "set[int] | None" = None) -> "plt.Figure | None":
    """Per-run ok-rate profiles for the top_n models with highest mean ok-rate (coverage)."""
    eligible = [r for r in rows if r.get("run_ok_rates")]
    if not eligible:
        return None
    ranked = sorted(
        eligible,
        key=lambda r: sum(r["run_ok_rates"].values()) / len(r["run_ok_rates"]),
        reverse=True,
    )[:top_n]

    fig, ax = plt.subplots(figsize=(16, 6), constrained_layout=True)
    fig.suptitle(
        f"Top {top_n} models — highest mean % ok subruns integrated over all runs (best coverage)",
        fontsize=12, fontweight="bold",
    )
    ax.set_title("% ok subruns per run", fontsize=10)
    ax.set_xlabel("run number", fontsize=9)
    ax.set_ylabel("% ok subruns", fontsize=9)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_locator(MultipleLocator(20))
    ax.yaxis.set_minor_locator(MultipleLocator(10))
    ax.grid(True, which="major", alpha=0.3)
    ax.yaxis.grid(True, which="minor", alpha=0.15)

    if training_runs:
        for start, end in _consecutive_blocks(training_runs):
            ax.axvspan(start - 0.5, end + 0.5,
                       color="lightgray", alpha=0.35, linewidth=0, zorder=0)

    import matplotlib.cm as cm
    for i, r in enumerate(ranked):
        rr      = r["run_ok_rates"]
        xs      = sorted(rr.keys())
        ys      = [rr[x] for x in xs]
        mean_ok = sum(ys) / len(ys)
        lbl     = f"{_model_label(r)}  [mean ok = {mean_ok:.1f}%]"
        ax.plot(xs, ys, color=cm.tab10(i % 10), linewidth=1.5, alpha=0.85, label=lbl)

    ax.legend(fontsize=7.5, loc="lower left", framealpha=0.9)
    return fig


def make_pdf(rows: list[dict],
             metric_cols: list,
             y_axis_unit: str,
             cont_for_profile: float,
             out_path: Path,
             training_runs: set[int] | None = None) -> None:
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(out_path) as pdf:
        for z in Z_THRESHOLDS:
            for include_tc in [True, False]:
                fig = _make_figure(rows, include_tc, metric_cols, y_axis_unit,
                                   z, cont_for_profile,
                                   training_runs=training_runs)
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
        fig = _make_best_fp_figure(rows, 5, training_runs)
        if fig is not None:
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
        fig = _make_best_fp_per_z_figure(rows, 3, training_runs)
        if fig is not None:
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
        fig = _make_best_coverage_figure(rows, 5, training_runs)
        if fig is not None:
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
    print(f"  Saved → {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_DIR   = _SCRIPT_DIR.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--contamination", type=float, default=0.001,
                        help="if_contamination shown in the per-run goodness panel (default: 0.001)")
    parser.add_argument("--good-run-list", type=Path,
                        default=_REPO_DIR.parent / "data" / "good_run_list_TRAINING.txt",
                        help="path to training good run list (used to shade trained runs in profile panel)")
    args = parser.parse_args()

    reports_dir = _REPO_DIR / "reports" / "applyToRuns_260521"
    out_dir     = _SCRIPT_DIR / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {reports_dir}/ ...")
    rows = collect(reports_dir)
    if not rows:
        print("No completed models found — exiting.")
        return

    cnt = args.contamination

    print(f"Loading training runs from {args.good_run_list} ...")
    training_runs = load_training_runs(args.good_run_list)
    print(f"  {len(training_runs)} training run(s) found.")

    print(f"Generating applyToRuns_260521_counts.pdf  (all z, cont={cnt} for per-run goodness) ...")
    make_pdf(rows,
             metric_cols      = METRIC_COLS_COUNTS,
             y_axis_unit      = "#",
             cont_for_profile = cnt,
             out_path         = out_dir / "applyToRuns_260521_counts.pdf",
             training_runs    = training_runs)

    print(f"Generating applyToRuns_260521_rel.pdf ...")
    make_pdf(rows,
             metric_cols      = METRIC_COLS_REL,
             y_axis_unit      = "%",
             cont_for_profile = cnt,
             out_path         = out_dir / "applyToRuns_260521_rel.pdf",
             training_runs    = training_runs)

    print("\nDone.")


if __name__ == "__main__":
    main()
