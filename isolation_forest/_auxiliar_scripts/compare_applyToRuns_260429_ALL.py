#!/usr/bin/env python3
"""
Combined comparison of applyToRuns outputs from the 260429 and 260429_EXT sweeps.

The 260429 sweep covered:
  contamination ∈ {0.005, 0.01}  ×  z = 7σ  ×  4 feature variants  ×  2 triggerConfig modes

The 260429_EXT sweep extended into the low-contamination regime:
  contamination ∈ {0.001, 0.002}  ×  z ∈ {7, 8}σ  ×  trigger+LVDS  ×  ignoreDAQConfig

The overlap at z = 7σ allows combined pages covering the full contamination range
{0.001, 0.002, 0.005, 0.01}.  The z = 8σ region is EXT-only and appears as separate pages.

Layout per PDF (three pages per catalogue quality):
  page 1: z = 7σ, with triggerConfig
           main sweep (all 4 feature variants) + EXT (trigger+LVDS added to that series)
           x-axis: contamination ∈ {0.001, 0.002, 0.005, 0.01}
  page 2: z = 7σ, ignoring triggerConfig  — main sweep only
           x-axis: contamination ∈ {0.005, 0.01}
  page 3: z = 8σ  — EXT only (trigger+LVDS, ignoreDAQConfig)
           x-axis: contamination ∈ {0.001, 0.002}

  columns : FP | TN | NL-GOOD | NL-ALERT   (subrun level)

  encoding for z = 7σ pages:
    colour     → feature variant (digi only / +trigger rates / +LVDS counts / +trigger+LVDS)
    line style → training quality (Loose / Medium / Tight)

  encoding for z = 8σ page:
    colour + line style → training quality (Loose / Medium / Tight)

Produces six PDFs in _auxiliar_scripts/plots/ (two per catalogue quality):
  applyToRuns_260429_ALL_on{Loose,Medium,Tight}_counts.pdf
  applyToRuns_260429_ALL_on{Loose,Medium,Tight}_rel.pdf

Usage (from _auxiliar_scripts/):
    python compare_applyToRuns_260429_ALL_onSameRefSample.py
    python compare_applyToRuns_260429_ALL_onSameRefSample.py --catalogue <path>

Paths are resolved relative to this script:
  reports  → ../reports/applyToRuns_260429
             ../reports/applyToRuns_260429_EXT
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
from matplotlib.ticker import MultipleLocator

# ── Sweep dimensions ──────────────────────────────────────────────────────────

CONTS_Z7_ALL  = [0.001, 0.002, 0.005, 0.01]   # page 1: combined z=7 range
CONTS_Z7_NOTC = [0.005, 0.01]                  # page 2: main sweep only
CONTS_Z8      = [0.001, 0.002]                 # page 3: EXT z=8 only
QUALITIES     = ["Loose", "Medium", "Tight"]

# Feature variant (use_trigger, use_lvds) → (label, colour)
VARIANT_META = {
    (False, False): ("digi only",        "#444444"),
    (True,  False): ("+ trigger rates",  "#1f77b4"),
    (False, True):  ("+ LVDS counts",    "#ff7f0e"),
    (True,  True):  ("+ trigger + LVDS", "#2ca02c"),
}

# Training quality → (colour, line style)  — used for z=8 page
QUALITY_META = {
    "Loose":  ("#1f77b4", ":"),
    "Medium": ("#2ca02c", "--"),
    "Tight":  ("#d62728", "-"),
}

# Training quality → line style  — used for z=7 pages
QUALITY_STYLE = {
    "Loose":  ("Loose",  ":"),
    "Medium": ("Medium", "--"),
    "Tight":  ("Tight",  "-"),
}

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

# ── Tag parsing ───────────────────────────────────────────────────────────────

_CONT_RE = re.compile(r"ifContamination_([0-9p]+)")
_Z_RE    = re.compile(r"zThreshold_(\d+)sigma")
_QUAL_260429_RE  = re.compile(r"_260429_(Loose|Medium|Tight)(?:_|$)")
_QUAL_EXT_RE     = re.compile(r"_260429_EXT_(Loose|Medium|Tight)(?:_|$)")


def _cont_to_float(s: str) -> float:
    return float(s.replace("p", "."))


def parse_tag_260429(tag: str) -> "dict | None":
    """Parse main 260429 sweep tags (excludes EXT and IFhp)."""
    if "_260429_EXT_" in tag or "_260429_IFhp_" in tag:
        return None
    if "_260429_" not in tag:
        return None
    mc = _CONT_RE.search(tag)
    mz = _Z_RE.search(tag)
    mq = _QUAL_260429_RE.search(tag)
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
        "source":                 "260429",
    }


def parse_tag_ext(tag: str) -> "dict | None":
    """Parse 260429_EXT tags; keeps only trigger+LVDS+ignoreDAQConfig models."""
    if "_260429_EXT_" not in tag:
        return None
    if "_noTrigger" in tag or "_noLVDS" in tag or "_ignoreTriggerConfig" in tag:
        return None
    mc = _CONT_RE.search(tag)
    mz = _Z_RE.search(tag)
    mq = _QUAL_EXT_RE.search(tag)
    if not (mc and mz and mq):
        return None
    return {
        "tag":                    tag,
        "if_contamination":       _cont_to_float(mc.group(1)),
        "z_threshold":            int(mz.group(1)),
        "quality":                mq.group(1),
        "use_trigger":            True,
        "use_lvds":               True,
        "include_trigger_config": True,
        "source":                 "260429_EXT",
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


def find_catalogue(repo_dir: Path) -> "Path | None":
    for meta_path in (repo_dir / "models").glob("*/training_metadata.json"):
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

def _collect_dir(reports_dir: Path, parse_fn, catalogue: dict, cat_quality: str) -> list:
    results = []
    skipped = 0
    for tag_dir in sorted(reports_dir.iterdir()):
        if not tag_dir.is_dir():
            continue
        params = parse_fn(tag_dir.name)
        if params is None:
            continue
        metrics = load_metrics(tag_dir, catalogue, cat_quality)
        if metrics is None:
            skipped += 1
            continue
        results.append({**params, **metrics})
    if skipped:
        print(f"  Skipped {skipped} model(s) from {reports_dir.name} — "
              "framework_good_runs.json missing or unreadable.", file=sys.stderr)
    return results


def collect(rep_260429: Path, rep_ext: Path, catalogue: dict, cat_quality: str) -> list:
    rows = _collect_dir(rep_260429, parse_tag_260429, catalogue, cat_quality)
    rows += _collect_dir(rep_ext,     parse_tag_ext,     catalogue, cat_quality)
    print(f"  Loaded {len(rows)} model(s) total.")
    return rows


# ── Plotting helpers ──────────────────────────────────────────────────────────

def _setup_axes(axes, metric_cols, y_axis_unit, x_ticks):
    for col_idx, (y_key, col_title) in enumerate(metric_cols):
        ax = axes[col_idx]
        ax.set_title(col_title, fontsize=10)
        ax.set_xlabel("if_contamination", fontsize=9)
        if col_idx == 0:
            ax.set_ylabel(f"subrun level  ({y_axis_unit})", fontsize=9)
        ax.set_xscale("log")
        ax.set_xticks(x_ticks)
        ax.set_xticklabels([str(c) for c in x_ticks],
                           fontsize=9, rotation=0, ha="center")
        ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        if y_axis_unit == "%":
            ax.yaxis.set_major_locator(MultipleLocator(20))
            ax.yaxis.set_minor_locator(MultipleLocator(10))
            ax.grid(True, which="major", alpha=0.3)
            ax.yaxis.grid(True, which="minor", alpha=0.15)
            ax.set_ylim(0, 100)
        else:
            ax.grid(True, alpha=0.3)


# ── Figure: z = 7σ pages (pages 1 and 2) ─────────────────────────────────────

def _make_figure_z7(rows: list,
                    include_trigger_config: bool,
                    cat_quality: str,
                    metric_cols: list,
                    y_axis_unit: str) -> plt.Figure:
    tc_label  = "with triggerConfig" if include_trigger_config else "ignoring triggerConfig"
    x_ticks   = CONTS_Z7_ALL if include_trigger_config else CONTS_Z7_NOTC
    ext_note  = " (EXT adds trigger+LVDS points at 0.001, 0.002)" if include_trigger_config else ""

    subset = [r for r in rows
              if r["z_threshold"] == 7
              and r["include_trigger_config"] == include_trigger_config]

    fig, axes = plt.subplots(
        1, 3,
        figsize=(20, 5),
        gridspec_kw={"width_ratios": [1, 1, 2]},
        constrained_layout=True,
    )
    gt_label = "OR(Loose ∨ Medium ∨ Tight)" if cat_quality == "OR" else f"{cat_quality} goodRunsList"
    fig.suptitle(
        f"applyToRuns 260429 + EXT  (z = 7σ)  |  ground truth: {gt_label}"
        f"  |  {tc_label}{ext_note}",
        fontsize=11, fontweight="bold",
    )

    _setup_axes(axes, metric_cols, y_axis_unit, x_ticks)

    for col_idx, (y_key, _) in enumerate(metric_cols):
        ax = axes[col_idx]
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

    for (use_trigger, use_lvds), (var_label, colour) in VARIANT_META.items():
        for qual, (qual_label, linestyle) in QUALITY_STYLE.items():
            for r in subset:
                if r["use_trigger"] != use_trigger or r["use_lvds"] != use_lvds or r["quality"] != qual:
                    continue
                rr = r.get("run_ok_rates")
                if not rr:
                    continue
                xs = sorted(rr.keys())
                ys = [rr[x] for x in xs]
                ax_run.plot(xs, ys, color=colour, linestyle=linestyle,
                            linewidth=1.2, alpha=0.6)

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


# ── Figure: z = 8σ page (page 3) ─────────────────────────────────────────────

def _make_figure_z8(rows: list,
                    cat_quality: str,
                    metric_cols: list,
                    y_axis_unit: str) -> plt.Figure:
    subset = [r for r in rows if r["z_threshold"] == 8]

    fig, axes = plt.subplots(
        1, 3,
        figsize=(20, 5),
        gridspec_kw={"width_ratios": [1, 1, 2]},
        constrained_layout=True,
    )
    gt_label = "OR(Loose ∨ Medium ∨ Tight)" if cat_quality == "OR" else f"{cat_quality} goodRunsList"
    fig.suptitle(
        f"applyToRuns 260429 EXT  (z = 8σ, trigger+LVDS, ignoreDAQConfig)  |  "
        f"ground truth: {gt_label}",
        fontsize=11, fontweight="bold",
    )

    _setup_axes(axes, metric_cols, y_axis_unit, CONTS_Z8)

    for col_idx, (y_key, _) in enumerate(metric_cols):
        ax = axes[col_idx]
        for qual, (colour, linestyle) in QUALITY_META.items():
            pts = sorted(
                [r for r in subset
                 if r["quality"] == qual and r.get(y_key) is not None],
                key=lambda r: r["if_contamination"],
            )
            if not pts:
                continue
            xs = [p["if_contamination"] for p in pts]
            ys = [p[y_key]              for p in pts]
            ax.plot(xs, ys, color=colour, linestyle=linestyle,
                    linewidth=1.6, marker="o", markersize=5,
                    label=f"trained {qual}")

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

    for qual, (colour, linestyle) in QUALITY_META.items():
        for r in subset:
            if r["quality"] != qual:
                continue
            rr = r.get("run_ok_rates")
            if not rr:
                continue
            xs = sorted(rr.keys())
            ys = [rr[x] for x in xs]
            ax_run.plot(xs, ys, color=colour, linestyle=linestyle,
                        linewidth=1.2, alpha=0.6)

    handles = [
        mlines.Line2D([], [], color=colour, linestyle=ls, label=f"trained {ql}")
        for ql, (colour, ls) in QUALITY_META.items()
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=3,
        fontsize=8,
        framealpha=0.9,
        bbox_to_anchor=(0.5, -0.06),
    )
    return fig


# ── PDF output ────────────────────────────────────────────────────────────────

def make_pdf(rows: list,
             cat_quality: str,
             metric_cols: list,
             y_axis_unit: str,
             out_path: Path) -> None:
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(out_path) as pdf:
        # page 1: z=7, with triggerConfig (combined range)
        fig = _make_figure_z7(rows, True,  cat_quality, metric_cols, y_axis_unit)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        # page 2: z=7, ignoring triggerConfig (main sweep only)
        fig = _make_figure_z7(rows, False, cat_quality, metric_cols, y_axis_unit)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        # page 3: z=8, EXT only
        fig = _make_figure_z8(rows, cat_quality, metric_cols, y_axis_unit)
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

    rep_260429 = _REPO_DIR / "reports" / "applyToRuns_260429"
    rep_ext    = _REPO_DIR / "reports" / "applyToRuns_260429_EXT"
    out_dir    = _SCRIPT_DIR / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    for rep in [rep_260429, rep_ext]:
        if not rep.exists():
            print(f"ERROR: reports dir '{rep}' not found.", file=sys.stderr)
            sys.exit(1)

    cat_path = Path(args.catalogue) if args.catalogue else find_catalogue(_REPO_DIR)
    if cat_path is None or not cat_path.exists():
        print("ERROR: goodRunsListSlab.json not found. Pass --catalogue <path>.",
              file=sys.stderr)
        sys.exit(1)
    print(f"Loading catalogue: {cat_path} ...")
    catalogue = load_catalogue(cat_path)
    print(f"  {len(catalogue):,} (run, subrun) entries.")

    for quality in QUALITIES:
        print(f"\n── Catalogue quality: {quality} ──")
        print(f"Scanning {rep_260429.name}/ and {rep_ext.name}/ ...")
        rows = collect(rep_260429, rep_ext, catalogue, quality)
        if not rows:
            print("  No completed models found — skipping.")
            continue

        counts_name = f"applyToRuns_260429_ALL_on{quality}_counts.pdf"
        print(f"Generating {counts_name} ...")
        make_pdf(rows, quality, METRIC_COLS_COUNTS, "#", out_dir / counts_name)

        rel_name = f"applyToRuns_260429_ALL_on{quality}_rel.pdf"
        print(f"Generating {rel_name} ...")
        make_pdf(rows, quality, METRIC_COLS_REL, "%", out_dir / rel_name)

    print("\n── OR of all qualities ──")
    print(f"Scanning {rep_260429.name}/ and {rep_ext.name}/ ...")
    rows = collect(rep_260429, rep_ext, catalogue, "OR")
    if rows:
        print("Generating applyToRuns_260429_ALL_onOrOfAllQualities_counts.pdf ...")
        make_pdf(rows, "OR", METRIC_COLS_COUNTS, "#",
                 out_dir / "applyToRuns_260429_ALL_onOrOfAllQualities_counts.pdf")
        print("Generating applyToRuns_260429_ALL_onOrOfAllQualities_rel.pdf ...")
        make_pdf(rows, "OR", METRIC_COLS_REL, "%",
                 out_dir / "applyToRuns_260429_ALL_onOrOfAllQualities_rel.pdf")

    print("\nDone.")


if __name__ == "__main__":
    main()
