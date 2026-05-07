#!/usr/bin/env python3
"""
Compare 260429 sweep outputs — FP and TN rate per model against a fixed goodRunsList quality.

Unlike compare_sweep_260429_onTrainingSample.py (which paginates by training quality and
keys FP/TN on the training quality), this script:

  • evaluates ALL models against each of the three goodRunsList quality thresholds
    in a single run, so results for Loose / Medium / Tight ground truth are produced
    at once;
  • reads predictions from framework_good_runs.json directly (not eval_confusion_data.json),
    making the ground-truth independent of training quality;
  • shows all three training qualities (Loose / Medium / Tight) as separate line styles
    on the SAME axes instead of paginating.

Y-axis range is controlled by the FIX_Y_RANGE flag near the top of the file:
  FIX_Y_RANGE = True   — fixed ranges from Y_RANGE_FIXED (lines clipped at axes edge)
  FIX_Y_RANGE = False  — automatic (data-driven) range
The y-axis grid is drawn at every 10 units (labelled) and every 5 units (unlabelled).

Layout:
  pages   : one per trigger-config variant (with / without triggerConfig)
  rows    : top = subrun level, bottom = run level
  columns : one per z_threshold (5 / 6 / 7 / 8 / 9 σ)
  lines   : 4 feature variants (colour) × 3 training qualities (line style)

Produces six PDFs in _auxiliar_scripts/plots/ (two per catalogue quality):
  fp_sweep_260429_on{Loose,Medium,Tight}_rel.pdf  — false-positive rate  (% known-good flagged as alert)
  tn_sweep_260429_on{Loose,Medium,Tight}_rel.pdf  — true-negative rate   (% known-good correctly called ok)

Usage (from _auxiliar_scripts/):
    python compare_sweep_260429_onSameRefSample.py

Paths are resolved relative to this script:
  reports  → ../reports
  plots    → _auxiliar_scripts/plots/
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
from matplotlib.ticker import MultipleLocator

# ── Sweep dimensions ──────────────────────────────────────────────────────────

CONTAMINATIONS = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05]
Z_THRESHOLDS   = [5, 6, 7, 8, 9]
QUALITIES      = ["Loose", "Medium", "Tight"]

# Feature variant → (label, colour)
VARIANT_META = {
    (False, False): ("digi only",        "#444444"),
    (True,  False): ("+ trigger rates",  "#1f77b4"),
    (False, True):  ("+ LVDS counts",    "#ff7f0e"),
    (True,  True):  ("+ trigger + LVDS", "#2ca02c"),
}

# Training quality → line style
QUALITY_STYLE = {
    "Loose":  ("Loose",  ":"),
    "Medium": ("Medium", "--"),
    "Tight":  ("Tight",  "-"),
}

# ── Y-axis range ──────────────────────────────────────────────────────────────
# Set FIX_Y_RANGE = False for automatic (data-driven) limits.
# When True the ranges below are applied; lines to out-of-range points are clipped
# at the axes edge so they point toward (but don't draw) out-of-bounds markers.
FIX_Y_RANGE = True

Y_RANGE_FIXED = {
    "fp_rel_subruns": (0,   55),
    "fp_rel_runs":    (40, 100),
    "tn_rel_subruns": (40, 100),
    "tn_rel_runs":    (0,   40),
}

# ── Tag parsing ───────────────────────────────────────────────────────────────

_CONT_RE = re.compile(r"ifContamination_([0-9p]+)")
_Z_RE    = re.compile(r"zThreshold_(\d+)sigma")
_QUAL_RE = re.compile(r"_260429(?:_EXT)?_(Loose|Medium|Tight)(?:_|$)")


def _cont_to_float(s: str) -> float:
    return float(s.replace("p", "."))


def parse_tag(tag: str) -> "dict | None":
    if "_260429_" not in tag:
        return None
    mc = _CONT_RE.search(tag)
    mz = _Z_RE.search(tag)
    mq = _QUAL_RE.search(tag)
    if not (mc and mz and mq):
        return None
    return {
        "tag":                    tag,
        "if_contamination":       _cont_to_float(mc.group(1)),
        "z_threshold":            int(mz.group(1)),
        "quality":                mq.group(1),
        "use_trigger":            "_noTrigger"         not in tag,
        "use_lvds":               "_noLVDS"            not in tag,
        "include_trigger_config": "_ignoreTriggerConfig" not in tag,
    }


# ── Catalogue loading ─────────────────────────────────────────────────────────

def load_catalogue(path: Path) -> dict:
    """Return {(run, subrun): {"loose": bool, "medium": bool, "tight": bool}}."""
    with open(path) as f:
        raw = json.load(f)
    cat = {}
    for row in raw.get("data", []):
        run, subrun = int(row[0]), int(row[1])
        cat[(run, subrun)] = {
            "loose":  bool(row[2]),
            "medium": bool(row[3]),
            "tight":  bool(row[4]),
        }
    return cat


def find_catalogue(reports_dir: Path) -> "Path | None":
    """Try to find goodRunsListSlab.json from any model's training_metadata.json."""
    models_dir = reports_dir.parent / "models"
    for meta_path in models_dir.glob("*/training_metadata.json"):
        try:
            meta = json.loads(meta_path.read_text())
            p = meta.get("effective_config", {}).get("goodRunsList_json", "")
            if p and Path(p).exists():
                return Path(p)
        except Exception:
            continue
    return None


# ── Per-model metrics (fixed catalogue quality) ───────────────────────────────

def load_metrics(reports_dir: Path, catalogue: dict, cat_quality: str) -> "dict | None":
    """
    Compute FP and TN at subrun and run level using a fixed catalogue quality.

    Known-good = (run, subrun) where catalogue[cat_quality] is True.
    Predicted alert  = all three quality cols in framework_good_runs.json are 0.
    Predicted ok     = tight col is 1  (strictest pass).

    Returns None if framework_good_runs.json is missing or unreadable.
    """
    fw_path = reports_dir / "framework_good_runs.json"
    if not fw_path.exists():
        return None
    try:
        with open(fw_path) as f:
            fw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    q_key = cat_quality.lower()

    # framework row: [run, subrun, loose_ok, medium_ok, tight_ok, 0, "autoDQM_IF"]
    subrun_fp = subrun_tn = subrun_good = 0
    run_alerts: dict = defaultdict(list)
    run_oks:    dict = defaultdict(list)

    for row in fw.get("data", []):
        run, subrun = int(row[0]), int(row[1])
        if not catalogue.get((run, subrun), {}).get(q_key, False):
            continue  # not known-good at this quality

        is_alert = (row[2] == 0 and row[3] == 0 and row[4] == 0)
        is_ok    = bool(row[4])

        subrun_good += 1
        if is_alert:
            subrun_fp += 1
        if is_ok:
            subrun_tn += 1

        run_alerts[run].append(is_alert)
        run_oks[run].append(is_ok)

    if subrun_good == 0:
        return None

    n_good_runs = len(run_alerts)
    fp_runs = sum(1 for alerts in run_alerts.values() if any(alerts))
    tn_runs = sum(1 for oks    in run_oks.values()    if all(oks))

    return {
        "n_good_subruns": subrun_good,
        "fp_subruns":     subrun_fp,
        "tn_subruns":     subrun_tn,
        "n_good_runs":    n_good_runs,
        "fp_runs":        fp_runs,
        "tn_runs":        tn_runs,
        "fp_rel_subruns": 100 * subrun_fp / subrun_good,
        "tn_rel_subruns": 100 * subrun_tn / subrun_good,
        "fp_rel_runs":    100 * fp_runs   / n_good_runs if n_good_runs else None,
        "tn_rel_runs":    100 * tn_runs   / n_good_runs if n_good_runs else None,
    }


# ── Data collection ───────────────────────────────────────────────────────────

def collect(reports_dir: Path, catalogue: dict, cat_quality: str) -> list[dict]:
    skipped = 0
    results = []
    for tag_dir in sorted(reports_dir.iterdir()):
        if not tag_dir.is_dir() or tag_dir.name == "applyToRuns_260429":
            continue
        params = parse_tag(tag_dir.name)
        if params is None:
            continue
        metrics = load_metrics(tag_dir, catalogue, cat_quality)
        if metrics is None:
            skipped += 1
            continue
        results.append({**params, **metrics})
    if skipped:
        print(f"  Skipped {skipped} model(s) — framework_good_runs.json missing or unreadable.",
              file=sys.stderr)
    print(f"  Loaded {len(results)} completed model(s).")
    return results


# ── Plotting ──────────────────────────────────────────────────────────────────

def _make_figure(rows: list[dict],
                 include_trigger_config: bool,
                 y_subrun_key: str,
                 y_run_key: str,
                 y_label_base: str,
                 title_prefix: str,
                 cat_quality: str) -> plt.Figure:
    tc_label = "with triggerConfig" if include_trigger_config else "ignoring triggerConfig"
    subset = [r for r in rows if r["include_trigger_config"] == include_trigger_config]

    fig, axes = plt.subplots(
        2, len(Z_THRESHOLDS),
        figsize=(4.5 * len(Z_THRESHOLDS), 9),
        sharey="row",
        constrained_layout=True,
    )
    fig.suptitle(
        f"{title_prefix}\n"
        f"ground truth: {cat_quality} goodRunsList  |  {tc_label}",
        fontsize=12, fontweight="bold",
    )

    row_labels = [f"subrun level  ({y_label_base})",
                  f"run level  ({y_label_base})"]
    y_keys     = [y_subrun_key, y_run_key]

    for row_idx, (y_key, row_label) in enumerate(zip(y_keys, row_labels)):
        for col_idx, z in enumerate(Z_THRESHOLDS):
            ax = axes[row_idx][col_idx]
            ax.set_title(f"z = {z}σ", fontsize=10)
            ax.set_xlabel("if_contamination", fontsize=9)
            if col_idx == 0:
                ax.set_ylabel(row_label, fontsize=9)
            ax.set_xscale("log")
            ax.set_xticks(CONTAMINATIONS)
            ax.set_xticklabels([str(c) for c in CONTAMINATIONS],
                               fontsize=8, rotation=45, ha="right")
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
                for qual, (qual_label, linestyle) in QUALITY_STYLE.items():
                    pts = sorted(
                        [r for r in cell
                         if r["use_trigger"] == use_trigger
                         and r["use_lvds"]   == use_lvds
                         and r["quality"]    == qual
                         and r.get(y_key) is not None],
                        key=lambda r: r["if_contamination"],
                    )
                    if not pts:
                        continue
                    xs = [p["if_contamination"] for p in pts]
                    ys = [p[y_key]              for p in pts]
                    ax.plot(xs, ys, color=colour, linestyle=linestyle,
                            linewidth=1.6, marker="o", markersize=4)

    # Legend
    colour_handles = [
        mpatches.Patch(color=colour, label=var_label)
        for (_, _), (var_label, colour) in VARIANT_META.items()
    ]
    style_handles = [
        mlines.Line2D([], [], color="black", linestyle=ls, label=f"trained {ql}")
        for ql, (_, ls) in QUALITY_STYLE.items()
    ]
    fig.legend(
        handles=colour_handles + style_handles,
        loc="lower center",
        ncol=7,
        fontsize=8,
        framealpha=0.9,
        bbox_to_anchor=(0.5, -0.06),
    )
    return fig


def make_pdf(rows: list[dict],
             y_subrun_key: str,
             y_run_key: str,
             y_label_base: str,
             title_prefix: str,
             cat_quality: str,
             out_path: Path) -> None:
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(out_path) as pdf:
        for include_tc in [True, False]:
            fig = _make_figure(rows, include_tc,
                               y_subrun_key, y_run_key,
                               y_label_base, title_prefix, cat_quality)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
    print(f"  Saved → {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_DIR   = _SCRIPT_DIR.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalogue", default="",
                        help="Path to goodRunsListSlab.json (auto-detected if omitted)")
    args = parser.parse_args()

    reports_dir = _REPO_DIR / "reports"
    out_dir     = _SCRIPT_DIR / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    cat_path = Path(args.catalogue) if args.catalogue else find_catalogue(reports_dir)
    if cat_path is None or not cat_path.exists():
        print("ERROR: goodRunsListSlab.json not found. Pass --catalogue <path>.",
              file=sys.stderr)
        sys.exit(1)
    print(f"Loading catalogue: {cat_path} ...")
    catalogue = load_catalogue(cat_path)
    print(f"  {len(catalogue):,} (run, subrun) entries.")

    for quality in QUALITIES:
        print(f"\n── Quality: {quality} ──")
        print(f"Scanning {reports_dir}/ ...")
        rows = collect(reports_dir, catalogue, quality)
        if not rows:
            print("  No completed models found — skipping.")
            continue

        print(f"Generating fp_sweep_260429_on{quality}_rel.pdf ...")
        make_pdf(rows,
                 y_subrun_key = "fp_rel_subruns",
                 y_run_key    = "fp_rel_runs",
                 y_label_base = "% known-good flagged as alert",
                 title_prefix = "False positive rate — % known-good subruns/runs flagged as alert",
                 cat_quality  = quality,
                 out_path     = out_dir / f"fp_sweep_260429_on{quality}_rel.pdf")

        print(f"Generating tn_sweep_260429_on{quality}_rel.pdf ...")
        make_pdf(rows,
                 y_subrun_key = "tn_rel_subruns",
                 y_run_key    = "tn_rel_runs",
                 y_label_base = "% known-good correctly called ok",
                 title_prefix = "True negative rate — % known-good subruns/runs correctly classified",
                 cat_quality  = quality,
                 out_path     = out_dir / f"tn_sweep_260429_on{quality}_rel.pdf")

    print("\nDone.")


if __name__ == "__main__":
    main()
