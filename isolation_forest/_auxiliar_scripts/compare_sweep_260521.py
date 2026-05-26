#!/usr/bin/env python3
"""
Compare 260521 sweep outputs — FP and TN rate per model against the training text list.

Ground truth: every (run, subrun) resolved from good_run_list_TRAINING.txt is
known_good; all others are unknown.  FP/TN rates are read directly from
eval_confusion_data.json (written by the evaluate step) — no external catalogue.

Sweep dimensions:
  contamination    ∈ {0.001, 0.005, 0.01, 0.05}
  z_threshold      ∈ {6, 7, 8}
  alert_consec_n   ∈ {1, 2, 3, 4, 5}
  4 feature variants (digi / +trigger / +LVDS / +trigger+LVDS)
  2 trigger-config states (withConfig / ignoreConfig)

Layout:
  pages   : one per trigger-config variant (with / without triggerConfig)
  columns : one per z_threshold (6 / 7 / 8 σ)
  lines   : 4 feature variants (colour) × 5 alert_consecutive_n (line style)
  x-axis  : contamination (log scale)

Produces two PDFs in _auxiliar_scripts/plots/:
  fp_sweep_260521_rel.pdf  — false-positive rate  (% known-good flagged as alert)
  tn_sweep_260521_rel.pdf  — true-negative rate   (% known-good correctly called ok)

Usage (from _auxiliar_scripts/):
    python compare_sweep_260521.py

Paths are resolved relative to this script:
  reports  → ../reports/applyToRuns_260521
  plots    → _auxiliar_scripts/plots/
"""

import json
import re
import sys
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

# alert_consecutive_n → (label, line style)
CONSEC_STYLE = {
    1: ("consec=1", "-"),
    2: ("consec=2", "--"),
    3: ("consec=3", "-."),
    4: ("consec=4", ":"),
    5: ("consec=5", (0, (3, 1, 1, 1))),
}

# Y-axis range control.  Set FIX_Y_RANGE = False for data-driven limits.
FIX_Y_RANGE = True
Y_RANGE_FIXED = {
    "fp_rel_subruns": (0,   55),
    "tn_rel_subruns": (40, 100),
}

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
    """Read FP/TN counts from eval_confusion_data.json (text-list ground truth)."""
    confusion_path = reports_dir / "eval_confusion_data.json"
    if not confusion_path.exists():
        return None
    try:
        with open(confusion_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    counts   = data.get("counts", {})
    totals   = data.get("totals", {})
    kg_total = totals.get("known_good", 0)
    if kg_total == 0:
        return None

    kg_fp = counts.get("known_good", {}).get("alert", 0)
    kg_tn = counts.get("known_good", {}).get("ok",    0)

    return {
        "n_kg_subruns":     kg_total,
        "fp_count_subruns": kg_fp,
        "tn_count_subruns": kg_tn,
        "fp_rel_subruns":   100 * kg_fp / kg_total,
        "tn_rel_subruns":   100 * kg_tn / kg_total,
    }


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
        print(f"  Skipped {skipped} model(s) — eval_confusion_data.json missing or unreadable.",
              file=sys.stderr)
    print(f"  Loaded {len(results)} completed model(s).")
    return results


# ── Plotting ──────────────────────────────────────────────────────────────────

def _make_figure(rows: list[dict],
                 include_trigger_config: bool,
                 y_key: str,
                 y_label_base: str,
                 title_prefix: str) -> plt.Figure:
    tc_label = "with triggerConfig" if include_trigger_config else "ignoring triggerConfig"
    subset   = [r for r in rows if r["include_trigger_config"] == include_trigger_config]

    fig, axes = plt.subplots(
        1, len(Z_THRESHOLDS),
        figsize=(4.5 * len(Z_THRESHOLDS), 5),
        sharey=True,
        constrained_layout=True,
    )
    if len(Z_THRESHOLDS) == 1:
        axes = [axes]

    fig.suptitle(
        f"{title_prefix}\n"
        f"ground truth: training text list  |  {tc_label}",
        fontsize=12, fontweight="bold",
    )

    for col_idx, z in enumerate(Z_THRESHOLDS):
        ax = axes[col_idx]
        ax.set_title(f"z = {z}σ", fontsize=10)
        ax.set_xlabel("if_contamination", fontsize=9)
        if col_idx == 0:
            ax.set_ylabel(f"subrun level  ({y_label_base})", fontsize=9)
        ax.set_xscale("log")
        ax.set_xticks(CONTAMINATIONS)
        ax.set_xticklabels([str(c) for c in CONTAMINATIONS],
                           fontsize=8, rotation=0, ha="center")
        ax.xaxis.set_minor_locator(NullLocator())
        ax.yaxis.set_major_locator(MultipleLocator(10))
        ax.yaxis.set_minor_locator(MultipleLocator(5))
        ax.grid(True, which="major", alpha=0.3)
        ax.yaxis.grid(True, which="minor", alpha=0.15)
        if FIX_Y_RANGE and col_idx == 0:
            y_range = Y_RANGE_FIXED.get(y_key)
            if y_range:
                ax.set_ylim(*y_range)

        cell = [r for r in subset if r["z_threshold"] == z]

        for (use_trigger, use_lvds), (var_label, colour) in VARIANT_META.items():
            for consec, (consec_label, linestyle) in CONSEC_STYLE.items():
                pts = sorted(
                    [r for r in cell
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
                        linewidth=1.6, marker="o", markersize=4)

    colour_handles = [
        mpatches.Patch(color=colour, label=var_label)
        for (_, _), (var_label, colour) in VARIANT_META.items()
    ]
    style_handles = [
        mlines.Line2D([], [], color="black", linestyle=ls, label=label)
        for consec, (label, ls) in CONSEC_STYLE.items()
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


def make_pdf(rows: list[dict],
             y_key: str,
             y_label_base: str,
             title_prefix: str,
             out_path: Path) -> None:
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(out_path) as pdf:
        for include_tc in [True, False]:
            fig = _make_figure(rows, include_tc, y_key, y_label_base, title_prefix)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
    print(f"  Saved → {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_DIR   = _SCRIPT_DIR.parent


def main() -> None:
    reports_dir = _REPO_DIR / "reports" / "applyToRuns_260521"
    out_dir     = _SCRIPT_DIR / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {reports_dir}/ ...")
    rows = collect(reports_dir)
    if not rows:
        print("No completed models found — exiting.")
        return

    print("Generating fp_sweep_260521_rel.pdf ...")
    make_pdf(rows,
             y_key        = "fp_rel_subruns",
             y_label_base = "% known-good flagged as alert",
             title_prefix = "False positive rate — % known-good subruns flagged as alert",
             out_path     = out_dir / "fp_sweep_260521_rel.pdf")

    print("Generating tn_sweep_260521_rel.pdf ...")
    make_pdf(rows,
             y_key        = "tn_rel_subruns",
             y_label_base = "% known-good correctly called ok",
             title_prefix = "True negative rate — % known-good subruns correctly classified",
             out_path     = out_dir / "tn_sweep_260521_rel.pdf")

    print("\nDone.")


if __name__ == "__main__":
    main()
