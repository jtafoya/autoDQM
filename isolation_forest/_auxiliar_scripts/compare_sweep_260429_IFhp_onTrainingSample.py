#!/usr/bin/env python3
"""
Compare 260429 IFhp training-sample outputs — FP/TN against each model's own training quality.

Sweeps n_estimators ∈ {200, 300, 500} × max_samples ∈ {256, 1024, 4096} at the best
contamination/z region found in the main 260429 sweep:
  contamination ∈ {0.001, 0.002}  ×  z ∈ {7, 8}σ  ×  trigger+LVDS  ×  ignoreDAQConfig

For each completed model the confusion data is read from the model's own training quality,
so all pages within one PDF use the same quality as both ground truth and training label.

Layout per PDF:
  pages   : one per training quality (Loose / Medium / Tight)
  single row : subrun level
  columns : one per max_samples value (256 / 1024 / 4096)
  lines   : contamination (colour) × z_threshold (line style)
  x-axis  : if_n_estimators (200, 300, 500)

Produces four PDFs in _auxiliar_scripts/plots/:
  fp_sweep_260429_IFhp_onTrainingSample_counts.pdf
  tn_sweep_260429_IFhp_onTrainingSample_counts.pdf
  fp_sweep_260429_IFhp_onTrainingSample_rel.pdf
  tn_sweep_260429_IFhp_onTrainingSample_rel.pdf

Usage (from _auxiliar_scripts/):
    python compare_sweep_260429_IFhp_onTrainingSample.py
    python compare_sweep_260429_IFhp_onTrainingSample.py --catalogue <path>

Paths are resolved relative to this script:
  models  → ../models
  reports → ../reports
  plots   → _auxiliar_scripts/plots/
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
from matplotlib.ticker import MultipleLocator, NullLocator

# ── Sweep dimensions ──────────────────────────────────────────────────────────

N_ESTIMATORS = [200, 300, 500]
MAX_SAMPLES  = [256, 1024, 4096]
QUALITIES    = ["Loose", "Medium", "Tight"]

# contamination → (label, colour)
CONT_META = {
    0.001: ("cont = 0.001", "#1f77b4"),
    0.002: ("cont = 0.002", "#ff7f0e"),
}

# z_threshold → line style
Z_STYLE = {
    7: ("z = 7σ", "-"),
    8: ("z = 8σ", "--"),
}

# ── Y-axis range ──────────────────────────────────────────────────────────────

Y_RANGE_FIXED = {
    "fp_pct_subruns": (0,   15),
    "tn_pct_subruns": (85, 100),
}

# Major/minor tick interval for rel plots, keyed by metric prefix
_TICK_MAJOR = {"fp": 5, "tn": 5}
_TICK_MINOR = {"fp": 1, "tn": 1}

# ── Tag parsing ───────────────────────────────────────────────────────────────

_CONT_RE  = re.compile(r"ifContamination_([0-9p]+)")
_Z_RE     = re.compile(r"zThreshold_(\d+)sigma")
_NEST_RE  = re.compile(r"nEst_(\d+)")
_MSAMP_RE = re.compile(r"maxSamp_(\d+)")
_QUAL_RE  = re.compile(r"_260429_IFhp_(Loose|Medium|Tight)(?:_|$)")


def _cont_to_float(s: str) -> float:
    return float(s.replace("p", "."))


def parse_tag(tag: str) -> "dict | None":
    if "_260429_IFhp_" not in tag:
        return None
    mc = _CONT_RE.search(tag)
    mz = _Z_RE.search(tag)
    mn = _NEST_RE.search(tag)
    ms = _MSAMP_RE.search(tag)
    mq = _QUAL_RE.search(tag)
    if not (mc and mz and mn and ms and mq):
        return None
    return {
        "tag":             tag,
        "if_contamination": _cont_to_float(mc.group(1)),
        "z_threshold":     int(mz.group(1)),
        "if_n_estimators": int(mn.group(1)),
        "if_max_samples":  int(ms.group(1)),
        "quality":         mq.group(1),
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


def find_catalogue(models_dir: Path) -> "Path | None":
    """Try to find goodRunsListSlab.json from any IFhp model's training_metadata.json."""
    for meta_path in models_dir.glob("*_260429_IFhp_*/training_metadata.json"):
        try:
            meta = json.loads(meta_path.read_text())
            p = meta.get("effective_config", {}).get("goodRunsList_json", "")
            if p and Path(p).exists():
                return Path(p)
        except Exception:
            continue
    return None


# ── Per-model metrics ─────────────────────────────────────────────────────────

def load_metrics(reports_dir: Path, catalogue: "dict | None", quality: str) -> "dict | None":
    """
    Load subrun-level FP/TN from eval_confusion_data.json.

    Returns None if the file is missing or unreadable.
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

def collect(models_dir: Path, reports_dir: Path, catalogue: "dict | None") -> list:
    results = []
    skipped = 0
    for model_dir in sorted(models_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        params = parse_tag(model_dir.name)
        if params is None:
            continue
        metrics = load_metrics(reports_dir / model_dir.name, catalogue, params["quality"])
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

def _make_figure(rows: list,
                 y_key: str,
                 quality: str,
                 y_label_base: str,
                 title_prefix: str,
                 is_rel: bool = False) -> plt.Figure:
    fig, axes = plt.subplots(
        1, len(MAX_SAMPLES),
        figsize=(5 * len(MAX_SAMPLES), 5),
        sharey=True,
        constrained_layout=True,
    )
    fig.suptitle(
        f"{title_prefix}  |  training quality: {quality}",
        fontsize=12, fontweight="bold",
    )

    for col_idx, ms in enumerate(MAX_SAMPLES):
        ax = axes[col_idx]
        ax.set_title(f"max_samples = {ms}", fontsize=10)
        ax.set_xlabel("if_n_estimators", fontsize=9)
        if col_idx == 0:
            ax.set_ylabel(f"subrun level  ({y_label_base})", fontsize=9)
        ax.set_xticks(N_ESTIMATORS)
        ax.set_xticklabels([str(n) for n in N_ESTIMATORS], fontsize=9)
        ax.xaxis.set_minor_locator(NullLocator())
        if is_rel:
            prefix = y_key.split("_")[0]
            ax.yaxis.set_major_locator(MultipleLocator(_TICK_MAJOR.get(prefix, 10)))
            ax.yaxis.set_minor_locator(MultipleLocator(_TICK_MINOR.get(prefix, 5)))
            ax.grid(True, which="major", alpha=0.3)
            ax.yaxis.grid(True, which="minor", alpha=0.15)
            y_range = Y_RANGE_FIXED.get(y_key)
            if y_range:
                ax.set_ylim(*y_range)
        else:
            ax.grid(True, alpha=0.3)

        cell = [r for r in rows if r["quality"] == quality
                                and r["if_max_samples"] == ms]

        for cont, (cont_label, colour) in CONT_META.items():
            for z, (z_label, linestyle) in Z_STYLE.items():
                pts = sorted(
                    [r for r in cell
                     if r["if_contamination"] == cont
                     and r["z_threshold"]      == z
                     and r.get(y_key) is not None],
                    key=lambda r: r["if_n_estimators"],
                )
                if not pts:
                    continue
                xs = [p["if_n_estimators"] for p in pts]
                ys = [p[y_key]             for p in pts]
                ax.plot(xs, ys, color=colour, linestyle=linestyle,
                        linewidth=1.8, marker="o", markersize=5,
                        label=f"{cont_label}, {z_label}")

    colour_handles = [
        mpatches.Patch(color=colour, label=label)
        for _, (label, colour) in CONT_META.items()
    ]
    style_handles = [
        mlines.Line2D([], [], color="black", linestyle=ls, label=label)
        for _, (label, ls) in Z_STYLE.items()
    ]
    fig.legend(
        handles=colour_handles + style_handles,
        loc="lower center",
        ncol=4,
        fontsize=8,
        framealpha=0.9,
        bbox_to_anchor=(0.5, -0.06),
    )
    return fig


def make_pdf(rows: list,
             y_key: str,
             y_label_base: str,
             title_prefix: str,
             out_path: Path,
             is_rel: bool = False) -> None:
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(out_path) as pdf:
        for quality in QUALITIES:
            fig = _make_figure(rows, y_key, quality, y_label_base, title_prefix, is_rel)
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

    models_dir  = _REPO_DIR / "models"
    reports_dir = _REPO_DIR / "reports"
    out_dir     = _SCRIPT_DIR / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    catalogue = None
    cat_path = Path(args.catalogue) if args.catalogue else find_catalogue(models_dir)
    if cat_path is not None and cat_path.exists():
        print(f"Loading catalogue: {cat_path} ...")
        catalogue = load_catalogue(cat_path)
        print(f"  {len(catalogue):,} (run, subrun) entries loaded.")
    else:
        print("  WARNING: goodRunsListSlab.json not found — run-level plots will be empty.",
              file=sys.stderr)

    print(f"Scanning {models_dir}/ (eval from {reports_dir}/) ...")
    rows = collect(models_dir, reports_dir, catalogue)
    if not rows:
        print("  No completed IFhp models found yet — try again later.")
        return

    print("Generating fp_sweep_260429_IFhp_onTrainingSample_counts.pdf ...")
    make_pdf(rows,
             y_key        = "fp_subruns",
             y_label_base = "# known-good flagged as alert",
             title_prefix = "False positives — known-good subruns flagged as alert",
             out_path     = out_dir / "fp_sweep_260429_IFhp_onTrainingSample_counts.pdf")

    print("Generating tn_sweep_260429_IFhp_onTrainingSample_counts.pdf ...")
    make_pdf(rows,
             y_key        = "tn_subruns",
             y_label_base = "# known-good correctly called ok",
             title_prefix = "True negatives — known-good subruns correctly classified",
             out_path     = out_dir / "tn_sweep_260429_IFhp_onTrainingSample_counts.pdf")

    print("Generating fp_sweep_260429_IFhp_onTrainingSample_rel.pdf ...")
    make_pdf(rows,
             y_key        = "fp_pct_subruns",
             y_label_base = "% known-good flagged as alert",
             title_prefix = "False positive rate — % known-good subruns flagged as alert",
             out_path     = out_dir / "fp_sweep_260429_IFhp_onTrainingSample_rel.pdf",
             is_rel       = True)

    print("Generating tn_sweep_260429_IFhp_onTrainingSample_rel.pdf ...")
    make_pdf(rows,
             y_key        = "tn_pct_subruns",
             y_label_base = "% known-good correctly called ok",
             title_prefix = "True negative rate — % known-good subruns correctly classified",
             out_path     = out_dir / "tn_sweep_260429_IFhp_onTrainingSample_rel.pdf",
             is_rel       = True)

    print("Done.")


if __name__ == "__main__":
    main()
