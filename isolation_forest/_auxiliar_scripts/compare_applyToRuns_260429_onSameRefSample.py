#!/usr/bin/env python3
"""
Compare 260429 applyToRuns outputs — FP/TN/TP counts and rates against a fixed goodRunsList quality.

Models are applied to the full run-by-run dataset (not just the training sample).
This covers a small subset of the sweep:
  contamination ∈ {0.005, 0.01}  ×  z = 7σ  ×  3 qualities  ×  4 feature variants  ×  2 triggerConfig

Unlike compare_applyToRuns_260429_onTrainingSample.py (not yet written), this script
evaluates all models against all three catalogue qualities in a single run, so training
qualities can be compared on equal footing.

Metrics (against fixed catalogue ground truth):
  FP : known-good subruns/runs flagged as alert  (want low)
  TN : known-good subruns/runs correctly called ok  (want high)
  TP : not-certified subruns/runs flagged as alert  (want high)

Layout per PDF:
  pages   : one per trigger-config variant (with / without triggerConfig)
  rows    : top = subrun level, bottom = run level
  columns : FP | TN | TP
  lines   : 4 feature variants (colour) × 3 training qualities (line style)
  x-axis  : contamination (only the two data points 0.005 and 0.01 are shown)

Produces six PDFs in _auxiliar_scripts/plots/ (one per quality × one per counts/rel):
  applyToRuns_260429_on{Loose,Medium,Tight}_counts.pdf
  applyToRuns_260429_on{Loose,Medium,Tight}_rel.pdf

Usage (from _auxiliar_scripts/):
    python compare_applyToRuns_260429_onSameRefSample.py
    python compare_applyToRuns_260429_onSameRefSample.py --catalogue <path>

Paths are resolved relative to this script:
  reports  → ../reports/applyToRuns_260429
  plots    → _auxiliar_scripts/plots/
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

# ── Sweep dimensions ──────────────────────────────────────────────────────────

CONTAMINATIONS = [0.005, 0.01]
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

METRIC_COLS_COUNTS = [
    ("fp_count_subruns", "fp_count_runs",
     "FP count\n# known-good flagged as alert"),
    ("tn_count_subruns", "tn_count_runs",
     "TN count\n# known-good correctly called ok"),
    ("tp_count_subruns", "tp_count_runs",
     "TP count\n# not-certified flagged as alert"),
]

METRIC_COLS_REL = [
    ("fp_rel_subruns", "fp_rel_runs",
     "FP rate\n% known-good flagged as alert"),
    ("tn_rel_subruns", "tn_rel_runs",
     "TN rate\n% known-good correctly called ok"),
    ("tp_rel_subruns", "tp_rel_runs",
     "TP rate\n% not-certified flagged as alert"),
]

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
        "use_trigger":            "_noTrigger"           not in tag,
        "use_lvds":               "_noLVDS"              not in tag,
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


def find_catalogue(reports_base: Path) -> "Path | None":
    """Try to find goodRunsListSlab.json from any model's training_metadata.json."""
    models_dir = reports_base.parent.parent / "models"
    for meta_path in models_dir.glob("*/training_metadata.json"):
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
    """
    Compute FP/TN on known-good and TP on not-certified at subrun and run level.

    known-good     = (run, subrun) where catalogue[cat_quality] is True
    not-certified  = (run, subrun) in catalogue where catalogue[cat_quality] is False
    is_alert       = all three quality cols in framework_good_runs.json are 0
    is_ok          = tight col (col 4) is 1

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

    kg_fp = kg_tn = kg_total = 0
    nc_tp = nc_total = 0

    run_kg_alerts: dict = defaultdict(list)
    run_kg_oks:    dict = defaultdict(list)
    run_nc_alerts: dict = defaultdict(list)

    for row in fw.get("data", []):
        run, subrun = int(row[0]), int(row[1])
        cat_entry = catalogue.get((run, subrun))
        if cat_entry is None:
            continue  # unknown — skip

        is_alert = (row[2] == 0 and row[3] == 0 and row[4] == 0)
        is_ok    = bool(row[4])

        if cat_entry.get(q_key, False):
            kg_total += 1
            if is_alert:
                kg_fp += 1
            if is_ok:
                kg_tn += 1
            run_kg_alerts[run].append(is_alert)
            run_kg_oks[run].append(is_ok)
        else:
            nc_total += 1
            if is_alert:
                nc_tp += 1
            run_nc_alerts[run].append(is_alert)

    if kg_total == 0 and nc_total == 0:
        return None

    n_kg_runs = len(run_kg_alerts)
    n_nc_runs = len(run_nc_alerts)

    fp_runs = sum(1 for alerts in run_kg_alerts.values() if any(alerts))
    tn_runs = sum(1 for oks    in run_kg_oks.values()    if all(oks))
    tp_runs = sum(1 for alerts in run_nc_alerts.values() if any(alerts))

    return {
        "n_kg_subruns":   kg_total,
        "n_nc_subruns":   nc_total,
        "n_kg_runs":      n_kg_runs,
        "n_nc_runs":      n_nc_runs,
        # counts
        "fp_count_subruns": kg_fp,
        "tn_count_subruns": kg_tn,
        "tp_count_subruns": nc_tp,
        "fp_count_runs":    fp_runs,
        "tn_count_runs":    tn_runs,
        "tp_count_runs":    tp_runs,
        # rates
        "fp_rel_subruns": 100 * kg_fp    / kg_total   if kg_total  else None,
        "tn_rel_subruns": 100 * kg_tn    / kg_total   if kg_total  else None,
        "tp_rel_subruns": 100 * nc_tp    / nc_total   if nc_total  else None,
        "fp_rel_runs":    100 * fp_runs  / n_kg_runs  if n_kg_runs else None,
        "tn_rel_runs":    100 * tn_runs  / n_kg_runs  if n_kg_runs else None,
        "tp_rel_runs":    100 * tp_runs  / n_nc_runs  if n_nc_runs else None,
    }


# ── Data collection ───────────────────────────────────────────────────────────

def collect(reports_dir: Path, catalogue: dict, cat_quality: str) -> list[dict]:
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

def _make_figure(rows: list[dict],
                 include_trigger_config: bool,
                 cat_quality: str,
                 metric_cols: list,
                 y_axis_unit: str) -> plt.Figure:
    tc_label = "with triggerConfig" if include_trigger_config else "ignoring triggerConfig"
    subset = [r for r in rows if r["include_trigger_config"] == include_trigger_config]

    n_cols = len(metric_cols)
    fig, axes = plt.subplots(
        2, n_cols,
        figsize=(5 * n_cols, 9),
        sharey="row",
        constrained_layout=True,
    )
    fig.suptitle(
        f"applyToRuns 260429  (z = 7σ)  |  ground truth: {cat_quality} goodRunsList  |  {tc_label}",
        fontsize=12, fontweight="bold",
    )

    row_labels = ["subrun level", "run level"]

    for col_idx, (y_subrun_key, y_run_key, col_title) in enumerate(metric_cols):
        for row_idx, (y_key, row_label) in enumerate(
                zip([y_subrun_key, y_run_key], row_labels)):
            ax = axes[row_idx][col_idx]
            ax.set_title(col_title, fontsize=10)
            ax.set_xlabel("if_contamination", fontsize=9)
            if col_idx == 0:
                ax.set_ylabel(f"{row_label}  ({y_axis_unit})", fontsize=9)
            ax.set_xscale("log")
            ax.set_xticks(CONTAMINATIONS)
            ax.set_xticklabels([str(c) for c in CONTAMINATIONS],
                               fontsize=9, rotation=45, ha="right")
            ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
            ax.grid(True, alpha=0.3)

            for (use_trigger, use_lvds), (var_label, colour) in VARIANT_META.items():
                for qual, (qual_label, linestyle) in QUALITY_STYLE.items():
                    pts = sorted(
                        [r for r in subset
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
                            linewidth=1.6, marker="o", markersize=5)

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
             cat_quality: str,
             metric_cols: list,
             y_axis_unit: str,
             out_path: Path) -> None:
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(out_path) as pdf:
        for include_tc in [True, False]:
            fig = _make_figure(rows, include_tc, cat_quality, metric_cols, y_axis_unit)
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

    reports_dir = _REPO_DIR / "reports" / "applyToRuns_260429"
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

        counts_name = f"applyToRuns_260429_on{quality}_counts.pdf"
        print(f"Generating {counts_name} ...")
        make_pdf(rows, quality, METRIC_COLS_COUNTS, "#", out_dir / counts_name)

        rel_name = f"applyToRuns_260429_on{quality}_rel.pdf"
        print(f"Generating {rel_name} ...")
        make_pdf(rows, quality, METRIC_COLS_REL, "%", out_dir / rel_name)

    print("\nDone.")


if __name__ == "__main__":
    main()
