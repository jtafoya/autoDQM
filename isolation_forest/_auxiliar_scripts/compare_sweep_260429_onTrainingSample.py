#!/usr/bin/env python3
"""
Compare parameter sweep results (submitted 2026-04-29, including EXT extension).

Covers both the original 260429 sweep and the 260429 EXT extension:
  original : contamination ∈ {0.005, 0.01, 0.02, 0.05}, z ∈ {5, 6, 7}σ
  EXT      : contamination ∈ {0.001, 0.002},             z ∈ {5, 6, 7, 8, 9}σ
             contamination ∈ {0.005, 0.01, 0.02, 0.05}, z ∈ {8, 9}σ

Full grid: contamination ∈ {0.001, 0.002, 0.005, 0.01, 0.02, 0.05} × z ∈ {5…9}σ

For each completed sweep model, reads:
  models/<tag>/eval_confusion_data.json  — subrun-level FP/TN counts
  models/<tag>/framework_good_runs.json  — per-subrun predicted status
  goodRunsListSlab.json catalogue        — ground truth per (run, subrun)

Produces four multi-page PDFs in _auxiliar_scripts/plots/:
  fp_sweep_260429_onTrainingSample_counts.pdf — # known-good subruns misclassified as bad (alert)
  tn_sweep_260429_onTrainingSample_counts.pdf — # known-good subruns correctly classified as good (ok)
  fp_sweep_260429_onTrainingSample_rel.pdf    — same as above, as percentages
  tn_sweep_260429_onTrainingSample_rel.pdf    — same as above, as percentages

"Bad" and "good" are defined by the persistence and bulk conditions already
encoded in framework_good_runs.json (alert = all three quality cols are 0;
ok = tight col is 1).

Layout per PDF:
  pages   : one per goodRunsList quality (Loose / Medium / Tight)
  single row : subrun level
  columns : one per z_threshold (5 / 6 / 7 / 8 / 9 sigma)
  lines   : 4 feature combinations (colour) × 2 triggerConfig settings (solid/dashed)

Usage (from _auxiliar_scripts/):
    python compare_sweep_260429_onTrainingSample.py

Paths are resolved relative to this script:
  models   → ../models
  reports  → ../reports
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

CONTAMINATIONS = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05]
Z_THRESHOLDS   = [5, 6, 7, 8, 9]
QUALITIES      = ["Loose", "Medium", "Tight"]

# (use_trigger, use_lvds) → (label, colour)
VARIANT_META = {
    (False, False): ("digi only",           "#444444"),
    (True,  False): ("+ trigger rates",     "#1f77b4"),
    (False, True):  ("+ LVDS counts",       "#ff7f0e"),
    (True,  True):  ("+ trigger + LVDS",    "#2ca02c"),
}

# ── Y-axis range ──────────────────────────────────────────────────────────────
# Set FIX_Y_RANGE = False for automatic (data-driven) limits.
# When True the ranges below are applied; lines to out-of-range points are clipped
# at the axes edge so they point toward (but don't draw) out-of-bounds markers.
FIX_Y_RANGE = True

Y_RANGE_FIXED = {
    "fp_pct_subruns": (0,   55),
    "tn_pct_subruns": (40, 100),
}

# ── Tag parsing ───────────────────────────────────────────────────────────────

_CONT_RE = re.compile(r"ifContamination_([0-9p]+)")
_Z_RE    = re.compile(r"zThreshold_(\d+)sigma")
_QUAL_RE = re.compile(r"_260429(?:_EXT)?_(Loose|Medium|Tight)(?:_|$)")


def _cont_to_float(s: str) -> float:
    return float(s.replace("p", "."))


def parse_tag(tag: str) -> "dict | None":
    """Return parsed parameter dict or None if tag is not a 260429 sweep model."""
    if "_260429_" not in tag:
        return None
    mc = _CONT_RE.search(tag)
    mz = _Z_RE.search(tag)
    mq = _QUAL_RE.search(tag)
    if not (mc and mz and mq):
        return None
    use_trigger = "_noTrigger" not in tag
    use_lvds    = "_noLVDS"    not in tag
    return {
        "tag":                    tag,
        "if_contamination":       _cont_to_float(mc.group(1)),
        "z_threshold":            int(mz.group(1)),
        "quality":                mq.group(1),
        "use_trigger":            use_trigger,
        "use_lvds":               use_lvds,
        "include_trigger_config": "_ignoreTriggerConfig" not in tag,
    }


# ── Catalogue loading ─────────────────────────────────────────────────────────

# ── Per-model metrics ─────────────────────────────────────────────────────────

def load_metrics(reports_dir: Path, catalogue: "dict | None", quality: str) -> "dict | None":
    """
    Load subrun-level metrics from eval_confusion_data.json.

    Returns None if the file is missing (job not done) or unreadable
    (job crashed mid-write).
    """
    confusion_path = reports_dir / "eval_confusion_data.json"
    if not confusion_path.exists():
        return None

    try:
        with open(confusion_path) as f:
            confusion = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    cnts   = confusion.get("counts", {})
    totals = confusion.get("totals", {})
    kg     = cnts.get("known_good", {})

    n_good_subruns = totals.get("known_good", 0)
    fp_subruns     = kg.get("alert", 0)
    tn_subruns     = kg.get("ok",    0)

    return {
        "n_good_subruns": n_good_subruns,
        "fp_subruns":     fp_subruns,
        "tn_subruns":     tn_subruns,
    }


# ── Data collection ───────────────────────────────────────────────────────────

def collect(models_dir: Path, reports_dir: Path, catalogue: "dict | None") -> list[dict]:
    """Scan models_dir for tags; load eval metrics from the matching reports_dir sub-directory."""
    results = []
    skipped = 0
    for model_dir in sorted(models_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        params = parse_tag(model_dir.name)
        if params is None:
            continue
        tag_reports_dir = reports_dir / model_dir.name
        metrics = load_metrics(tag_reports_dir, catalogue, params["quality"])
        if metrics is None:
            skipped += 1
            continue
        r = {**params, **metrics}
        n_sr = r["n_good_subruns"] or 0
        r["fp_pct_subruns"] = 100 * r["fp_subruns"] / n_sr if n_sr else None
        r["tn_pct_subruns"] = 100 * r["tn_subruns"] / n_sr if n_sr else None
        results.append(r)
    if skipped:
        print(f"  Skipped {skipped} model(s) — eval not yet complete.", file=sys.stderr)
    print(f"  Loaded {len(results)} completed model(s).")
    return results


# ── Plotting ──────────────────────────────────────────────────────────────────

def _make_figure(rows_data: list[dict],
                 y_key: str,
                 quality: str,
                 y_label_base: str,
                 title_prefix: str,
                 is_rel: bool = False) -> plt.Figure:
    fig, axes = plt.subplots(
        1, len(Z_THRESHOLDS),
        figsize=(4.5 * len(Z_THRESHOLDS), 5),
        sharey=True,
        constrained_layout=True,
    )
    fig.suptitle(
        f"{title_prefix}  |  goodRunsList quality: {quality}",
        fontsize=13, fontweight="bold",
    )

    for col_idx, z in enumerate(Z_THRESHOLDS):
        ax = axes[col_idx]
        ax.set_title(f"z-threshold = {z}σ", fontsize=10)
        ax.set_xlabel("if_contamination", fontsize=9)
        if col_idx == 0:
            ax.set_ylabel(f"subrun level  ({y_label_base})", fontsize=9)
        ax.set_xscale("log")
        ax.set_xticks(CONTAMINATIONS)
        ax.set_xticklabels([str(c) for c in CONTAMINATIONS],
                           fontsize=8, rotation=0, ha="center")
        ax.xaxis.set_minor_locator(NullLocator())
        if is_rel:
            ax.yaxis.set_major_locator(MultipleLocator(10))
            ax.yaxis.set_minor_locator(MultipleLocator(5))
            ax.grid(True, which="major", alpha=0.3)
            ax.yaxis.grid(True, which="minor", alpha=0.15)
            if FIX_Y_RANGE and col_idx == 0:
                y_range = Y_RANGE_FIXED.get(y_key)
                if y_range:
                    ax.set_ylim(*y_range)
        else:
            ax.grid(True, alpha=0.3)

        subset = [r for r in rows_data if r["quality"] == quality
                                       and r["z_threshold"] == z]

        for (use_trigger, use_lvds), (label, colour) in VARIANT_META.items():
            for include_tc, linestyle in [(True, "-"), (False, "--")]:
                pts = sorted(
                    [r for r in subset
                     if r["use_trigger"]            == use_trigger
                     and r["use_lvds"]              == use_lvds
                     and r["include_trigger_config"] == include_tc],
                    key=lambda r: r["if_contamination"],
                )
                pts = [(p["if_contamination"], p[y_key]) for p in pts
                       if p.get(y_key) is not None]
                if not pts:
                    continue
                xs, ys = zip(*pts)
                ax.plot(xs, ys, color=colour, linestyle=linestyle,
                        linewidth=1.8, marker="o", markersize=5)

    # ── Legend ────────────────────────────────────────────────────────────────
    colour_handles = [
        mpatches.Patch(color=colour, label=label)
        for (_, _), (label, colour) in VARIANT_META.items()
    ]
    style_handles = [
        mlines.Line2D([], [], color="black", linestyle="-",  label="with triggerConfig"),
        mlines.Line2D([], [], color="black", linestyle="--", label="w/o triggerConfig"),
    ]
    fig.legend(
        handles=colour_handles + style_handles,
        loc="lower center",
        ncol=6,
        fontsize=8,
        framealpha=0.9,
        bbox_to_anchor=(0.5, -0.06),
    )
    return fig


def make_pdf(rows_data: list[dict],
             y_key: str,
             y_label_base: str,
             title_prefix: str,
             out_path: Path,
             is_rel: bool = False) -> None:
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(out_path) as pdf:
        for quality in QUALITIES:
            fig = _make_figure(rows_data, y_key, quality,
                               y_label_base, title_prefix, is_rel)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
    print(f"  Saved → {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_DIR   = _SCRIPT_DIR.parent


def main() -> None:
    models_dir  = _REPO_DIR  / "models"
    reports_dir = _REPO_DIR  / "reports"
    out_dir     = _SCRIPT_DIR / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Collect metrics ───────────────────────────────────────────────────────
    if not models_dir.exists():
        print(f"  WARNING: models dir '{models_dir}' does not exist yet — nothing to plot.",
              file=sys.stderr)
        return
    print(f"Scanning {models_dir}/ (eval from {reports_dir}/) ...")
    rows = collect(models_dir, reports_dir, None)
    if not rows:
        print("  No completed sweep models found yet — try again later.")
        return

    print("Generating fp_sweep_260429_onTrainingSample_counts.pdf ...")
    make_pdf(
        rows,
        y_key        = "fp_subruns",
        y_label_base = "# known-good flagged as alert",
        title_prefix = "False positives — known-good subruns flagged as alert",
        out_path     = out_dir / "fp_sweep_260429_onTrainingSample_counts.pdf",
    )

    print("Generating tn_sweep_260429_onTrainingSample_counts.pdf ...")
    make_pdf(
        rows,
        y_key        = "tn_subruns",
        y_label_base = "# known-good correctly classified",
        title_prefix = "True negatives — known-good subruns correctly classified",
        out_path     = out_dir / "tn_sweep_260429_onTrainingSample_counts.pdf",
    )

    print("Generating fp_sweep_260429_onTrainingSample_rel.pdf ...")
    make_pdf(
        rows,
        y_key        = "fp_pct_subruns",
        y_label_base = "% known-good flagged as alert",
        title_prefix = "False positive rate — % known-good subruns flagged as alert",
        out_path     = out_dir / "fp_sweep_260429_onTrainingSample_rel.pdf",
        is_rel       = True,
    )

    print("Generating tn_sweep_260429_onTrainingSample_rel.pdf ...")
    make_pdf(
        rows,
        y_key        = "tn_pct_subruns",
        y_label_base = "% known-good correctly classified",
        title_prefix = "True negative rate — % known-good subruns correctly classified",
        out_path     = out_dir / "tn_sweep_260429_onTrainingSample_rel.pdf",
        is_rel       = True,
    )

    print("Done.")


if __name__ == "__main__":
    main()
