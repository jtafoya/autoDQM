#!/usr/bin/env python3
"""
Compare 260429 IFhp training-sample outputs — FP/TN rate against a fixed goodRunsList quality.

Unlike compare_sweep_260429_IFhp_onTrainingSample.py (which keys FP/TN on the model's
own training quality), this script evaluates all models against each of the three
goodRunsList quality thresholds so Loose / Medium / Tight trained models can be
compared on equal footing.

Layout per PDF:
  pages   : one per contamination × z_threshold combo
            (cont=0.001,z=7σ) | (cont=0.001,z=8σ) | (cont=0.002,z=7σ) | (cont=0.002,z=8σ)
  rows    : top = subrun level, bottom = run level
  columns : one per max_samples value (256 / 1024 / 4096)
  lines   : training quality (Loose / Medium / Tight)
  x-axis  : if_n_estimators (200, 300, 500)

Produces six PDFs in _auxiliar_scripts/plots/ (two per catalogue quality):
  fp_sweep_260429_IFhp_on{Loose,Medium,Tight}_rel.pdf
  tn_sweep_260429_IFhp_on{Loose,Medium,Tight}_rel.pdf

Usage (from _auxiliar_scripts/):
    python compare_sweep_260429_IFhp_onSameRefSample.py
    python compare_sweep_260429_IFhp_onSameRefSample.py --catalogue <path>

Paths are resolved relative to this script:
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

N_ESTIMATORS   = [200, 300, 500]
MAX_SAMPLES    = [256, 1024, 4096]
CONTAMINATIONS = [0.001, 0.002]
Z_THRESHOLDS   = [7, 8]
QUALITIES      = ["Loose", "Medium", "Tight"]

# (contamination, z_threshold) → page title
CONT_Z_COMBOS = [
    (0.001, 7),
    (0.001, 8),
    (0.002, 7),
    (0.002, 8),
]

# Training quality → (label, colour, linestyle)
QUALITY_META = {
    "Loose":  ("Loose",  "#1f77b4", ":"),
    "Medium": ("Medium", "#2ca02c", "--"),
    "Tight":  ("Tight",  "#d62728", "-"),
}

# ── Y-axis range ──────────────────────────────────────────────────────────────

Y_RANGE_FIXED = {
    "fp_rel_subruns": (0,   15),
    "fp_rel_runs":    (0,  100),
    "tn_rel_subruns": (85, 100),
    "tn_rel_runs":    (0,  100),
}

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
    models_dir = reports_dir.parent / "models"
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

def load_metrics(reports_dir: Path, catalogue: dict, cat_quality: str) -> "dict | None":
    """Compute FP/TN using a fixed catalogue quality as ground truth."""
    fw_path = reports_dir / "framework_good_runs.json"
    if not fw_path.exists():
        return None
    try:
        with open(fw_path) as f:
            fw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    q_key = cat_quality.lower()
    subrun_fp = subrun_tn = subrun_good = 0
    run_alerts: dict = defaultdict(list)
    run_oks:    dict = defaultdict(list)

    for row in fw.get("data", []):
        run, subrun = int(row[0]), int(row[1])
        if not catalogue.get((run, subrun), {}).get(q_key, False):
            continue
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
    fp_runs = sum(1 for a in run_alerts.values() if any(a))
    tn_runs = sum(1 for o in run_oks.values()    if all(o))

    return {
        "fp_rel_subruns": 100 * subrun_fp / subrun_good,
        "tn_rel_subruns": 100 * subrun_tn / subrun_good,
        "fp_rel_runs":    100 * fp_runs   / n_good_runs if n_good_runs else None,
        "tn_rel_runs":    100 * tn_runs   / n_good_runs if n_good_runs else None,
    }


# ── Data collection ───────────────────────────────────────────────────────────

def collect(reports_dir: Path, catalogue: dict, cat_quality: str) -> list:
    results = []
    skipped = 0
    for tag_dir in sorted(reports_dir.iterdir()):
        if not tag_dir.is_dir():
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

def _make_figure(rows: list,
                 cont: float,
                 z: int,
                 y_subrun_key: str,
                 y_run_key: str,
                 y_label_base: str,
                 title_prefix: str,
                 cat_quality: str) -> plt.Figure:
    fig, axes = plt.subplots(
        2, len(MAX_SAMPLES),
        figsize=(5 * len(MAX_SAMPLES), 9),
        sharey="row",
        constrained_layout=True,
    )
    fig.suptitle(
        f"{title_prefix}\n"
        f"ground truth: {cat_quality} goodRunsList  |  "
        f"cont = {cont}  |  z = {z}σ",
        fontsize=11, fontweight="bold",
    )

    row_labels = [f"subrun level  ({y_label_base})",
                  f"run level  ({y_label_base})"]
    y_keys     = [y_subrun_key, y_run_key]

    subset = [r for r in rows
              if r["if_contamination"] == cont and r["z_threshold"] == z]

    for row_idx, (y_key, row_label) in enumerate(zip(y_keys, row_labels)):
        for col_idx, ms in enumerate(MAX_SAMPLES):
            ax = axes[row_idx][col_idx]
            ax.set_title(f"max_samples = {ms}", fontsize=10)
            ax.set_xlabel("if_n_estimators", fontsize=9)
            if col_idx == 0:
                ax.set_ylabel(row_label, fontsize=9)
            ax.set_xticks(N_ESTIMATORS)
            ax.set_xticklabels([str(n) for n in N_ESTIMATORS], fontsize=9)
            ax.xaxis.set_minor_locator(NullLocator())
            prefix = y_key.split("_")[0]
            ax.yaxis.set_major_locator(MultipleLocator(_TICK_MAJOR.get(prefix, 10)))
            ax.yaxis.set_minor_locator(MultipleLocator(_TICK_MINOR.get(prefix, 5)))
            ax.grid(True, which="major", alpha=0.3)
            ax.yaxis.grid(True, which="minor", alpha=0.15)
            y_range = Y_RANGE_FIXED.get(y_key)
            if y_range:
                ax.set_ylim(*y_range)

            cell = [r for r in subset if r["if_max_samples"] == ms]

            for qual, (qual_label, colour, linestyle) in QUALITY_META.items():
                pts = sorted(
                    [r for r in cell
                     if r["quality"] == qual and r.get(y_key) is not None],
                    key=lambda r: r["if_n_estimators"],
                )
                if not pts:
                    continue
                xs = [p["if_n_estimators"] for p in pts]
                ys = [p[y_key]             for p in pts]
                ax.plot(xs, ys, color=colour, linestyle=linestyle,
                        linewidth=1.8, marker="o", markersize=5)

    handles = [
        mlines.Line2D([], [], color=colour, linestyle=ls, label=f"trained {ql}")
        for ql, (_, colour, ls) in QUALITY_META.items()
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3,
               fontsize=9, framealpha=0.9, bbox_to_anchor=(0.5, -0.06))
    return fig


def make_pdf(rows: list,
             y_subrun_key: str,
             y_run_key: str,
             y_label_base: str,
             title_prefix: str,
             cat_quality: str,
             out_path: Path) -> None:
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(out_path) as pdf:
        for cont, z in CONT_Z_COMBOS:
            fig = _make_figure(rows, cont, z,
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
        print(f"\n── Catalogue quality: {quality} ──")
        print(f"Scanning {reports_dir}/ ...")
        rows = collect(reports_dir, catalogue, quality)
        if not rows:
            print("  No completed IFhp models found — skipping.")
            continue

        fp_name = f"fp_sweep_260429_IFhp_on{quality}_rel.pdf"
        print(f"Generating {fp_name} ...")
        make_pdf(rows,
                 y_subrun_key = "fp_rel_subruns",
                 y_run_key    = "fp_rel_runs",
                 y_label_base = "% known-good flagged as alert",
                 title_prefix = "False positive rate — % known-good subruns/runs flagged as alert",
                 cat_quality  = quality,
                 out_path     = out_dir / fp_name)

        tn_name = f"tn_sweep_260429_IFhp_on{quality}_rel.pdf"
        print(f"Generating {tn_name} ...")
        make_pdf(rows,
                 y_subrun_key = "tn_rel_subruns",
                 y_run_key    = "tn_rel_runs",
                 y_label_base = "% known-good correctly called ok",
                 title_prefix = "True negative rate — % known-good subruns/runs correctly classified",
                 cat_quality  = quality,
                 out_path     = out_dir / tn_name)

    print("\nDone.")


if __name__ == "__main__":
    main()
