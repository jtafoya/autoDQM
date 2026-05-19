#!/usr/bin/env python3
"""
Compare 260429 IFhp applyToRuns outputs — FP/TN and not-listed ok/alert counts and rates.

All 108 IFhp models are applied to the full run-by-run dataset (runs 1422–2276) and
evaluated against each of the three goodRunsList quality thresholds.

Metrics:
  FP        : known-good subruns/runs flagged as alert  (want low)
  TN        : known-good subruns/runs correctly called ok  (want high)
  NL-GOOD   : not-listed subruns/runs classified as ok
  NL-ALERT  : not-listed subruns/runs triggering alert

  known-good  = (run, subrun) present in catalogue with the active quality flag True
  not-listed  = (run, subrun) absent from the catalogue entirely

Layout per PDF:
  pages   : one per contamination × z_threshold combo
            (cont=0.001,z=7σ) | (cont=0.001,z=8σ) | (cont=0.002,z=7σ) | (cont=0.002,z=8σ)
  columns : FP | TN | NL-GOOD | NL-ALERT   (subrun level)
  lines   : training quality (Loose / Medium / Tight) — colour + line style
  x-axis  : if_n_estimators (100, 200, 300, 500)
             100 comes from 260429_EXT models (trigger+LVDS, ignoreDAQConfig, sklearn defaults)

NOTE: Each panel shows one max_samples value per page is not feasible with 4 metric
columns; instead max_samples is encoded as hollow marker shape:
  256  → hollow circle   (o)
  1024 → hollow square   (s)
  4096 → hollow triangle (^)
Lines within the same (quality, cont, z) group connect points of the same max_samples.

Produces eight PDFs in _auxiliar_scripts/plots/ (two per catalogue quality):
  applyToRuns_260429_IFhp_on{Loose,Medium,Tight}_counts.pdf
  applyToRuns_260429_IFhp_on{Loose,Medium,Tight}_rel.pdf
  applyToRuns_260429_IFhp_onOrOfAllQualities_counts.pdf
  applyToRuns_260429_IFhp_onOrOfAllQualities_rel.pdf

Usage (from _auxiliar_scripts/):
    python compare_applyToRuns_260429_IFhp_onSameRefSample.py
    python compare_applyToRuns_260429_IFhp_onSameRefSample.py --catalogue <path>

Paths are resolved relative to this script:
  reports → ../reports/applyToRuns_260429_IFhp
             ../reports/applyToRuns_260429_EXT  (EXT baseline at n_est=100)
  plots   → _auxiliar_scripts/plots/
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
from matplotlib.ticker import MultipleLocator

# ── Sweep dimensions ──────────────────────────────────────────────────────────

N_ESTIMATORS = [100, 200, 300, 500]
MAX_SAMPLES  = [256, 1024, 4096]
QUALITIES    = ["Loose", "Medium", "Tight"]

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

# max_samples → hollow marker shape
MSAMP_MARKER = {
    256:  "o",
    1024: "s",
    4096: "^",
}
MSAMP_MARKERSIZE = 7

METRIC_COLS_COUNTS = [
    ("fp_count_subruns",
     "FP count\n# known-good flagged as alert"),
    ("tn_count_subruns",
     "TN count\n# known-good correctly called ok"),
]

METRIC_COLS_REL = [
    ("fp_rel_subruns",
     "FP rate\n% known-good flagged as alert"),
    ("tn_rel_subruns",
     "TN rate\n% known-good correctly called ok"),
]

# ── Y-axis range (rel plots only; NL columns keep full 0–100 %) ───────────────


# ── Tag parsing ───────────────────────────────────────────────────────────────

_CONT_RE      = re.compile(r"ifContamination_([0-9p]+)")
_Z_RE         = re.compile(r"zThreshold_(\d+)sigma")
_NEST_RE      = re.compile(r"nEst_(\d+)")
_MSAMP_RE     = re.compile(r"maxSamp_(\d+)")
_QUAL_RE      = re.compile(r"_260429_IFhp_(Loose|Medium|Tight)(?:_|$)")
_QUAL_EXT_RE  = re.compile(r"_260429_EXT_(Loose|Medium|Tight)(?:_|$)")

_CONT_Z_SET   = {(c, z) for c, z in [(0.001, 7), (0.001, 8), (0.002, 7), (0.002, 8)]}


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


def parse_tag_ext(tag: str) -> "dict | None":
    """Parse 260429_EXT tags (trigger+LVDS, ignoreDAQConfig only) as n_est=100, max_samp=256."""
    if "_260429_EXT_" not in tag:
        return None
    if "_noTrigger" in tag or "_noLVDS" in tag or "_ignoreTriggerConfig" in tag:
        return None
    mc = _CONT_RE.search(tag)
    mz = _Z_RE.search(tag)
    mq = _QUAL_EXT_RE.search(tag)
    if not (mc and mz and mq):
        return None
    cont = _cont_to_float(mc.group(1))
    z    = int(mz.group(1))
    if (cont, z) not in _CONT_Z_SET:
        return None
    return {
        "tag":             tag,
        "if_contamination": cont,
        "z_threshold":     z,
        "if_n_estimators": 100,
        "if_max_samples":  256,
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


def find_catalogue(reports_base: Path) -> "Path | None":
    models_dir = reports_base.parent.parent / "models"
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
    fw_path = reports_dir / "framework_good_runs.json"
    if not fw_path.exists():
        return None
    try:
        with open(fw_path) as f:
            fw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    use_or = (cat_quality == "OR")
    q_key  = None if use_or else cat_quality.lower()

    kg_fp = kg_tn = kg_total = 0
    run_ok: dict = defaultdict(lambda: [0, 0])  # [n_ok, n_total]

    for row in fw.get("data", []):
        run, subrun = int(row[0]), int(row[1])
        cat_entry = catalogue.get((run, subrun))
        is_alert  = (row[2] == 0 and row[3] == 0 and row[4] == 0)
        is_ok     = bool(row[2])

        run_ok[run][1] += 1
        if is_ok:
            run_ok[run][0] += 1

        if (use_or and cat_entry is not None
                and (cat_entry.get("loose", False) or cat_entry.get("medium", False) or cat_entry.get("tight", False))) \
                or (not use_or and cat_entry is not None and cat_entry.get(q_key, False)):
            kg_total += 1
            if is_alert:
                kg_fp += 1
            if is_ok:
                kg_tn += 1

    if not run_ok:
        return None

    return {
        "n_kg_subruns":     kg_total,
        "fp_count_subruns": kg_fp,
        "tn_count_subruns": kg_tn,
        "fp_rel_subruns":   100 * kg_fp / kg_total if kg_total else None,
        "tn_rel_subruns":   100 * kg_tn / kg_total if kg_total else None,
        "run_ok_rates":     {run: 100 * ok / n
                             for run, (ok, n) in sorted(run_ok.items()) if n},
    }


# ── Data collection ───────────────────────────────────────────────────────────

def collect(reports_dir: Path, catalogue: dict, cat_quality: str,
            ext_dir: "Path | None" = None) -> list:
    skipped = 0
    results = []
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
    if ext_dir and ext_dir.exists():
        for tag_dir in sorted(ext_dir.iterdir()):
            if not tag_dir.is_dir():
                continue
            params = parse_tag_ext(tag_dir.name)
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
                 cat_quality: str,
                 metric_cols: list,
                 y_axis_unit: str) -> plt.Figure:
    fig, axes = plt.subplots(
        1, 3,
        figsize=(20, 5),
        gridspec_kw={"width_ratios": [1, 1, 2]},
        constrained_layout=True,
    )
    gt_label = "OR(Loose ∨ Medium ∨ Tight)" if cat_quality == "OR" else f"{cat_quality} goodRunsList"
    fig.suptitle(
        f"applyToRuns 260429 IFhp  |  ground truth: {gt_label}  |  "
        f"cont = {cont}  |  z = {z}σ",
        fontsize=10, fontweight="bold",
    )

    cell = [r for r in rows if r["if_contamination"] == cont and r["z_threshold"] == z]

    for col_idx, (y_key, col_title) in enumerate(metric_cols):
        ax = axes[col_idx]
        ax.set_title(col_title, fontsize=10)
        ax.set_xlabel("if_n_estimators", fontsize=9)
        if col_idx == 0:
            ax.set_ylabel(f"subrun level  ({y_axis_unit})", fontsize=9)
        ax.set_xticks(N_ESTIMATORS)
        ax.set_xticklabels([str(n) for n in N_ESTIMATORS], fontsize=9)
        ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        if y_axis_unit == "%":
            ax.yaxis.set_major_locator(MultipleLocator(20))
            ax.yaxis.set_minor_locator(MultipleLocator(10))
            ax.grid(True, which="major", alpha=0.3)
            ax.yaxis.grid(True, which="minor", alpha=0.15)
            ax.set_ylim(0, 100)
        else:
            ax.grid(True, alpha=0.3)

        for qual, (qual_label, colour, linestyle) in QUALITY_META.items():
            for ms, mkshape in MSAMP_MARKER.items():
                pts = sorted(
                    [r for r in cell
                     if r["quality"] == qual
                     and r["if_max_samples"] == ms
                     and r.get(y_key) is not None],
                    key=lambda r: r["if_n_estimators"],
                )
                if not pts:
                    continue
                xs = [p["if_n_estimators"] for p in pts]
                ys = [p[y_key]             for p in pts]
                ax.plot(xs, ys, color=colour, linestyle=linestyle,
                        linewidth=1.4, marker=mkshape,
                        markersize=MSAMP_MARKERSIZE,
                        markerfacecolor="none", markeredgewidth=1.5,
                        alpha=0.85)

    # ── Per-run ok-rate panel ─────────────────────────────────────────────────
    ax_run = axes[2]
    ax_run.set_title("% ok subruns per run", fontsize=10)
    ax_run.set_xlabel("run number", fontsize=9)
    ax_run.set_ylabel("% ok subruns", fontsize=9)
    ax_run.set_ylim(0, 100)
    ax_run.yaxis.set_major_locator(MultipleLocator(20))
    ax_run.yaxis.set_minor_locator(MultipleLocator(10))
    ax_run.grid(True, which="major", alpha=0.3)
    ax_run.yaxis.grid(True, which="minor", alpha=0.15)

    for qual, (qual_label, colour, linestyle) in QUALITY_META.items():
        for r in cell:
            if r["quality"] != qual:
                continue
            rr = r.get("run_ok_rates")
            if not rr:
                continue
            xs = sorted(rr.keys())
            ys = [rr[x] for x in xs]
            ax_run.plot(xs, ys, color=colour, linestyle=linestyle,
                        linewidth=0.9, alpha=0.4)

    # Legend: quality (colour+style) + max_samples (hollow marker shape)
    qual_handles = [
        mlines.Line2D([], [], color=colour, linestyle=ls, linewidth=1.4,
                      marker="o", markersize=MSAMP_MARKERSIZE,
                      markerfacecolor="none", markeredgewidth=1.5,
                      label=f"trained {ql}")
        for ql, (_, colour, ls) in QUALITY_META.items()
    ]
    msamp_handles = [
        mlines.Line2D([], [], color="gray", linestyle="-", linewidth=1,
                      marker=mkshape, markersize=MSAMP_MARKERSIZE,
                      markerfacecolor="none", markeredgewidth=1.5,
                      label=f"max_samples={ms}")
        for ms, mkshape in MSAMP_MARKER.items()
    ]
    fig.legend(
        handles=qual_handles + msamp_handles,
        loc="lower center",
        ncol=6,
        fontsize=8,
        framealpha=0.9,
        bbox_to_anchor=(0.5, -0.06),
    )
    return fig


def make_pdf(rows: list,
             cat_quality: str,
             metric_cols: list,
             y_axis_unit: str,
             out_path: Path) -> None:
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(out_path) as pdf:
        for cont, z in CONT_Z_COMBOS:
            fig = _make_figure(rows, cont, z, cat_quality, metric_cols, y_axis_unit)
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

    reports_dir = _REPO_DIR / "reports" / "applyToRuns_260429_IFhp"
    ext_dir     = _REPO_DIR / "reports" / "applyToRuns_260429_EXT"
    out_dir     = _SCRIPT_DIR / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not reports_dir.exists():
        print(f"ERROR: reports dir '{reports_dir}' not found. "
              "Run combine_and_evaluate_applyToRuns_260429_IFhp.sh first.",
              file=sys.stderr)
        sys.exit(1)

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
        rows = collect(reports_dir, catalogue, quality, ext_dir)
        if not rows:
            print("  No completed IFhp applyToRuns models found — skipping.")
            continue

        counts_name = f"applyToRuns_260429_IFhp_on{quality}_counts.pdf"
        print(f"Generating {counts_name} ...")
        make_pdf(rows, quality, METRIC_COLS_COUNTS, "#", out_dir / counts_name)

        rel_name = f"applyToRuns_260429_IFhp_on{quality}_rel.pdf"
        print(f"Generating {rel_name} ...")
        make_pdf(rows, quality, METRIC_COLS_REL, "%", out_dir / rel_name)

    print("\n── OR of all qualities ──")
    print(f"Scanning {reports_dir}/ ...")
    rows = collect(reports_dir, catalogue, "OR", ext_dir)
    if rows:
        print("Generating applyToRuns_260429_IFhp_onOrOfAllQualities_counts.pdf ...")
        make_pdf(rows, "OR", METRIC_COLS_COUNTS, "#",
                 out_dir / "applyToRuns_260429_IFhp_onOrOfAllQualities_counts.pdf")
        print("Generating applyToRuns_260429_IFhp_onOrOfAllQualities_rel.pdf ...")
        make_pdf(rows, "OR", METRIC_COLS_REL, "%",
                 out_dir / "applyToRuns_260429_IFhp_onOrOfAllQualities_rel.pdf")
    else:
        print("  No completed IFhp applyToRuns models found — skipping.")

    print("\nDone.")


if __name__ == "__main__":
    main()
