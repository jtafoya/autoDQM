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
  rows    : top = subrun level, bottom = run level
  columns : FP | TN | NL-GOOD | NL-ALERT
  lines   : training quality (Loose / Medium / Tight) — colour + line style
  x-axis  : if_n_estimators (200, 300, 500)

NOTE: Each panel shows one max_samples value per page is not feasible with 4 metric
columns; instead max_samples is encoded as marker size:
  256  → small marker  (size 4)
  1024 → medium marker (size 7)
  4096 → large marker  (size 11)
Lines within the same (quality, cont, z) group connect points of the same max_samples.

Produces six PDFs in _auxiliar_scripts/plots/ (two per catalogue quality):
  applyToRuns_260429_IFhp_on{Loose,Medium,Tight}_counts.pdf
  applyToRuns_260429_IFhp_on{Loose,Medium,Tight}_rel.pdf

Usage (from _auxiliar_scripts/):
    python compare_applyToRuns_260429_IFhp_onSameRefSample.py
    python compare_applyToRuns_260429_IFhp_onSameRefSample.py --catalogue <path>

Paths are resolved relative to this script:
  reports → ../reports/applyToRuns_260429_IFhp
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

N_ESTIMATORS = [200, 300, 500]
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

# max_samples → marker size
MSAMP_MARKER = {
    256:  4,
    1024: 7,
    4096: 11,
}

METRIC_COLS_COUNTS = [
    ("fp_count_subruns", "fp_count_runs",
     "FP count\n# known-good flagged as alert"),
    ("tn_count_subruns", "tn_count_runs",
     "TN count\n# known-good correctly called ok"),
    ("nl_good_count_subruns", "nl_good_count_runs",
     "not-listed: GOOD\n# not-listed called ok"),
    ("nl_alert_count_subruns", "nl_alert_count_runs",
     "not-listed: ALERT\n# not-listed triggering alert"),
]

METRIC_COLS_REL = [
    ("fp_rel_subruns", "fp_rel_runs",
     "FP rate\n% known-good flagged as alert"),
    ("tn_rel_subruns", "tn_rel_runs",
     "TN rate\n% known-good correctly called ok"),
    ("nl_good_rel_subruns", "nl_good_rel_runs",
     "not-listed: GOOD rate\n% not-listed called ok"),
    ("nl_alert_rel_subruns", "nl_alert_rel_runs",
     "not-listed: ALERT rate\n% not-listed triggering alert"),
]

# ── Y-axis range (rel plots only; NL columns keep full 0–100 %) ───────────────

Y_RANGE_FIXED = {
    "fp_rel_subruns": (0,   15),
    "fp_rel_runs":    (0,   15),
    "tn_rel_subruns": (85, 100),
    "tn_rel_runs":    (85, 100),
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

    q_key = cat_quality.lower()

    kg_fp = kg_tn = kg_total = 0
    run_kg_alerts: dict = defaultdict(list)
    run_kg_oks:    dict = defaultdict(list)

    nl_good_sr = nl_alert_sr = nl_total = 0
    run_nl_goods:  dict = defaultdict(list)
    run_nl_alerts: dict = defaultdict(list)

    for row in fw.get("data", []):
        run, subrun = int(row[0]), int(row[1])
        cat_entry = catalogue.get((run, subrun))
        is_alert  = (row[2] == 0 and row[3] == 0 and row[4] == 0)
        is_ok     = bool(row[4])

        if cat_entry is None:
            nl_total += 1
            if is_ok:
                nl_good_sr += 1
            if is_alert:
                nl_alert_sr += 1
            run_nl_goods[run].append(is_ok)
            run_nl_alerts[run].append(is_alert)
        elif cat_entry.get(q_key, False):
            kg_total += 1
            if is_alert:
                kg_fp += 1
            if is_ok:
                kg_tn += 1
            run_kg_alerts[run].append(is_alert)
            run_kg_oks[run].append(is_ok)

    if kg_total == 0 and nl_total == 0:
        return None

    n_kg_runs      = len(run_kg_alerts)
    fp_runs        = sum(1 for a in run_kg_alerts.values() if any(a))
    tn_runs        = sum(1 for o in run_kg_oks.values()    if all(o))
    n_nl_runs      = len(run_nl_goods)
    nl_good_runs   = sum(1 for o in run_nl_goods.values()  if all(o))
    nl_alert_runs  = sum(1 for a in run_nl_alerts.values() if any(a))

    return {
        "n_kg_subruns":   kg_total,
        "n_kg_runs":      n_kg_runs,
        "n_nl_subruns":   nl_total,
        "n_nl_runs":      n_nl_runs,
        "fp_count_subruns":       kg_fp,
        "tn_count_subruns":       kg_tn,
        "nl_good_count_subruns":  nl_good_sr,
        "nl_alert_count_subruns": nl_alert_sr,
        "fp_count_runs":          fp_runs,
        "tn_count_runs":          tn_runs,
        "nl_good_count_runs":     nl_good_runs,
        "nl_alert_count_runs":    nl_alert_runs,
        "fp_rel_subruns":       100 * kg_fp         / kg_total   if kg_total  else None,
        "tn_rel_subruns":       100 * kg_tn         / kg_total   if kg_total  else None,
        "nl_good_rel_subruns":  100 * nl_good_sr    / nl_total   if nl_total  else None,
        "nl_alert_rel_subruns": 100 * nl_alert_sr   / nl_total   if nl_total  else None,
        "fp_rel_runs":          100 * fp_runs        / n_kg_runs  if n_kg_runs else None,
        "tn_rel_runs":          100 * tn_runs        / n_kg_runs  if n_kg_runs else None,
        "nl_good_rel_runs":     100 * nl_good_runs   / n_nl_runs  if n_nl_runs else None,
        "nl_alert_rel_runs":    100 * nl_alert_runs  / n_nl_runs  if n_nl_runs else None,
    }


# ── Data collection ───────────────────────────────────────────────────────────

def collect(reports_dir: Path, catalogue: dict, cat_quality: str) -> list:
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
    n_cols = len(metric_cols)
    fig, axes = plt.subplots(
        2, n_cols,
        figsize=(5 * n_cols, 9),
        sharey="row",
        constrained_layout=True,
    )
    fig.set_constrained_layout_pads(h_pad=0.15)
    fig.suptitle(
        f"applyToRuns 260429 IFhp  |  ground truth: {cat_quality} goodRunsList  |  "
        f"cont = {cont}  |  z = {z}σ",
        fontsize=10, fontweight="bold",
    )

    row_labels = ["subrun level", "run level"]

    for col_idx, (y_subrun_key, y_run_key, col_title) in enumerate(metric_cols):
        for row_idx, (y_key, row_label) in enumerate(
                zip([y_subrun_key, y_run_key], row_labels)):
            ax = axes[row_idx][col_idx]
            ax.set_title(col_title, fontsize=10)
            ax.set_xlabel("if_n_estimators", fontsize=9)
            if col_idx == 0:
                ax.set_ylabel(f"{row_label}  ({y_axis_unit})", fontsize=9)
            ax.set_xticks(N_ESTIMATORS)
            ax.set_xticklabels([str(n) for n in N_ESTIMATORS], fontsize=9)
            ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
            if y_axis_unit == "%":
                prefix = y_key.split("_")[0]
                ax.yaxis.set_major_locator(MultipleLocator(_TICK_MAJOR.get(prefix, 20)))
                ax.yaxis.set_minor_locator(MultipleLocator(_TICK_MINOR.get(prefix, 10)))
                ax.grid(True, which="major", alpha=0.3)
                ax.yaxis.grid(True, which="minor", alpha=0.15)
                y_range = Y_RANGE_FIXED.get(y_key, (0, 100))
                ax.set_ylim(*y_range)
            else:
                ax.grid(True, alpha=0.3)

            cell = [r for r in rows
                    if r["if_contamination"] == cont and r["z_threshold"] == z]

            for qual, (qual_label, colour, linestyle) in QUALITY_META.items():
                for ms, mksize in MSAMP_MARKER.items():
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
                            linewidth=1.4, marker="o", markersize=mksize,
                            alpha=0.85)

    # Legend: quality (colour+style) + max_samples (marker size)
    qual_handles = [
        mlines.Line2D([], [], color=colour, linestyle=ls, linewidth=1.4,
                      marker="o", markersize=7, label=f"trained {ql}")
        for ql, (_, colour, ls) in QUALITY_META.items()
    ]
    msamp_handles = [
        mlines.Line2D([], [], color="gray", linestyle="-", linewidth=1,
                      marker="o", markersize=mksize, label=f"max_samples={ms}")
        for ms, mksize in MSAMP_MARKER.items()
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
        rows = collect(reports_dir, catalogue, quality)
        if not rows:
            print("  No completed IFhp applyToRuns models found — skipping.")
            continue

        counts_name = f"applyToRuns_260429_IFhp_on{quality}_counts.pdf"
        print(f"Generating {counts_name} ...")
        make_pdf(rows, quality, METRIC_COLS_COUNTS, "#", out_dir / counts_name)

        rel_name = f"applyToRuns_260429_IFhp_on{quality}_rel.pdf"
        print(f"Generating {rel_name} ...")
        make_pdf(rows, quality, METRIC_COLS_REL, "%", out_dir / rel_name)

    print("\nDone.")


if __name__ == "__main__":
    main()
