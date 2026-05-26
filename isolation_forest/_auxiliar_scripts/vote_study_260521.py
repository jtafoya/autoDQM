#!/usr/bin/env python3
"""
Voting ensemble study for the 260521 applyToRuns sweep.

Each subrun is passed to a panel of N models. The ensemble classifies
the subrun as ok if at least k out of N models vote ok (threshold vote).
Only subruns scored by ALL models in the panel are counted (intersection).

Metrics computed per (panel, k):
  • FP rate   — % of known-good subruns classified as alert
  • Cov rate  — % of all subruns classified as ok (coverage)

Two output PDFs:
  plots/vote_study_260521_all.pdf      — panels drawn from all 480 models
  plots/vote_study_260521_consec1.pdf  — panels drawn from n_consec=1 models only (96)

Each PDF contains one page per panel family (3-panel figure: FP vs k,
Cov vs k, FP vs Cov tradeoff) plus profile pages for selected panels.

Usage (from _auxiliar_scripts/):
    python vote_study_260521.py
    python vote_study_260521.py --good-run-list ../data/good_run_list_TRAINING.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from itertools import groupby, combinations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
from matplotlib.ticker import MultipleLocator, NullLocator, MaxNLocator
from matplotlib.backends.backend_pdf import PdfPages

# ── Constants ─────────────────────────────────────────────────────────────────

CONTAMINATIONS = [0.001, 0.005, 0.01, 0.05]
Z_THRESHOLDS   = [6, 7, 8]
CONSEC_VALUES  = [1, 2, 3, 4, 5]

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_DIR   = _SCRIPT_DIR.parent

# ── Tag parsing ───────────────────────────────────────────────────────────────

_CONT_RE   = re.compile(r"ifContamination_([0-9p]+)")
_Z_RE      = re.compile(r"zThreshold_(\d+)sigma")
_CONSEC_RE = re.compile(r"alertConsec_(\d+)")


def _cont_to_float(s: str) -> float:
    return float(s.replace("p", "."))


def parse_tag(tag: str) -> "dict | None":
    if "260521" not in tag:
        return None
    mc, mz, mn = _CONT_RE.search(tag), _Z_RE.search(tag), _CONSEC_RE.search(tag)
    if not (mc and mz and mn):
        return None
    return {
        "tag":                    tag,
        "if_contamination":       _cont_to_float(mc.group(1)),
        "z_threshold":            int(mz.group(1)),
        "alert_consecutive_n":         int(mn.group(1)),
        "use_trigger":            "_noTrigger"           not in tag,
        "use_lvds":               "_noLVDS"              not in tag,
        "include_trigger_config": "_ignoreTriggerConfig" not in tag,
    }


def short_label(p: dict) -> str:
    """Compact human-readable label for one model's parameters."""
    feat = {
        (True,  True):  "trig+LVDS",
        (True,  False): "trig",
        (False, True):  "LVDS",
        (False, False): "digi",
    }[(p["use_trigger"], p["use_lvds"])]
    tc  = "wTC"  if p["include_trigger_config"] else "noTC"
    return (f"z={p['z_threshold']}σ c={p['if_contamination']} "
            f"n_consec={p['alert_consecutive_n']} {feat} {tc}")


# ── Training run list ─────────────────────────────────────────────────────────

_RUN_RE = re.compile(r"Digitizer_run(\d+)")


def load_training_runs(path: Path) -> set[int]:
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
    blocks = []
    for _, g in groupby(enumerate(sorted(runs)), lambda t: t[1] - t[0]):
        group = [v for _, v in g]
        blocks.append((group[0], group[-1]))
    return blocks


# ── Per-subrun data loading ───────────────────────────────────────────────────

def load_subrun_data(reports_dir: Path) -> "tuple[list[str], dict[str, dict]]":
    """
    Load per-subrun ok/alert data for all available 260521 models.

    Returns:
        tags     — list of model tags that loaded successfully
        data     — dict: tag → {(run, subrun): ok (1) or alert (0)}
    """
    tags: list[str] = []
    data: dict      = {}
    skipped = 0
    for tag_dir in sorted(reports_dir.iterdir()):
        if not tag_dir.is_dir():
            continue
        if parse_tag(tag_dir.name) is None:
            continue
        fw = tag_dir / "framework_good_runs.json"
        if not fw.exists():
            skipped += 1
            continue
        try:
            with open(fw) as f:
                rows = json.load(f)["data"]
            # row: [run, subrun, loose, medium, tight, ?, label]
            d = {(int(r[0]), int(r[1])): int(r[4]) for r in rows}
            if d:
                tags.append(tag_dir.name)
                data[tag_dir.name] = d
        except (json.JSONDecodeError, OSError, IndexError, KeyError):
            skipped += 1
    print(f"  Loaded {len(tags)} model(s); {skipped} missing/incomplete.")
    return tags, data


def build_matrix(tags: list[str], data: dict) -> "tuple[list, np.ndarray, np.ndarray]":
    """
    Build a dense (n_subruns × n_models) matrix for fast panel computation.

    Returns:
        subrun_ids  — list of (run, subrun) tuples (row order)
        ok_mat      — uint8 (n_subruns × n_models): 1=ok, 0=alert
        scored_mat  — uint8 (n_subruns × n_models): 1=this model scored this subrun
    """
    all_ids = sorted({sid for t in tags for sid in data[t].keys()})
    id_idx  = {sid: i for i, sid in enumerate(all_ids)}
    n_s, n_m = len(all_ids), len(tags)

    ok_mat     = np.zeros((n_s, n_m), dtype=np.uint8)
    scored_mat = np.zeros((n_s, n_m), dtype=np.uint8)

    for j, t in enumerate(tags):
        for sid, ok in data[t].items():
            i = id_idx[sid]
            ok_mat[i, j]     = ok
            scored_mat[i, j] = 1

    return all_ids, ok_mat, scored_mat


# ── Panel voting ──────────────────────────────────────────────────────────────

def panel_indices(tags: list[str], panel_tags: list[str]) -> np.ndarray:
    tag_idx = {t: i for i, t in enumerate(tags)}
    return np.array([tag_idx[t] for t in panel_tags if t in tag_idx], dtype=int)


def vote_metrics(
    subrun_ids:  list,
    ok_mat:      np.ndarray,
    scored_mat:  np.ndarray,
    col_ids:     np.ndarray,
    k:           int,
    kg_runs:     set[int],
) -> "dict | None":
    """
    Compute ensemble metrics for a given panel (col_ids) and threshold k.

    k = minimum number of bad-vote alerts required to classify a subrun as bad.
      k=1   → bad if ANY model alerts          (OR  gate, most sensitive)
      k=N   → bad only if ALL models alert     (AND gate, least sensitive)

    Only subruns scored by ALL panel models are counted (intersection).
    Returns None if the intersection is empty.
    """
    n = len(col_ids)
    s_sub = scored_mat[:, col_ids]           # (n_subruns, n_panel)
    full  = s_sub.sum(axis=1) == n           # subruns scored by all panel models
    if full.sum() == 0:
        return None

    ok_sub     = ok_mat[full][:, col_ids]    # (n_intersect, n_panel)
    bad_votes  = n - ok_sub.sum(axis=1)      # number of models voting bad/alert
    is_ok      = bad_votes < k               # ok unless at least k models agree it's bad

    # known-good mask
    ids_full = [subrun_ids[i] for i in np.where(full)[0]]
    kg_mask  = np.array([run in kg_runs for run, _ in ids_full], dtype=bool)

    fp_rate  = float((~is_ok[kg_mask]).sum() / kg_mask.sum() * 100) if kg_mask.sum() else float("nan")
    cov_rate = float(is_ok.sum() / len(is_ok) * 100)

    # per-run ok rate
    run_ok: dict[int, list] = defaultdict(lambda: [0, 0])
    for idx, (run, _) in enumerate(ids_full):
        run_ok[run][1] += 1
        if is_ok[idx]:
            run_ok[run][0] += 1
    run_ok_rates = {r: 100 * v[0] / v[1] for r, v in run_ok.items() if v[1]}

    return {
        "k": k, "n": n, "n_subruns": int(full.sum()),
        "fp_rate": fp_rate, "cov_rate": cov_rate,
        "run_ok_rates": run_ok_rates,
    }


def sweep_k(
    subrun_ids, ok_mat, scored_mat, col_ids, kg_runs
) -> list[dict]:
    n = len(col_ids)
    results = []
    for k in range(1, n + 1):
        m = vote_metrics(subrun_ids, ok_mat, scored_mat, col_ids, k, kg_runs)
        if m:
            results.append(m)
    return results


# ── Panel family definitions ──────────────────────────────────────────────────

def _build_panels_consec1(params: dict, one, combinations) -> list[dict]:
    """
    Panel families for the consec1 study (n_consec=1 fixed throughout).
    Explores z-threshold, feature variants, TC, and contamination.
    """
    families = []

    feat_variants = [
        ("digi",      dict(use_trigger=False, use_lvds=False)),
        ("trig",      dict(use_trigger=True,  use_lvds=False)),
        ("LVDS",      dict(use_trigger=False, use_lvds=True)),
        ("trig+LVDS", dict(use_trigger=True,  use_lvds=True)),
    ]

    # ── 1: z-threshold diversity ──────────────────────────────────────────────
    base = dict(if_contamination=0.001, alert_consecutive_n=1,
                use_trigger=True, use_lvds=True, include_trigger_config=True)
    panels = []
    for z in Z_THRESHOLDS:
        t = one(**base, z_threshold=z)
        if t: panels.append((f"z={z}σ alone", [t]))
    for z1, z2 in combinations(Z_THRESHOLDS, 2):
        t1, t2 = one(**base, z_threshold=z1), one(**base, z_threshold=z2)
        if t1 and t2: panels.append((f"z={z1}σ + z={z2}σ", [t1, t2]))
    ts = [one(**base, z_threshold=z) for z in Z_THRESHOLDS]
    if all(ts): panels.append(("z=6+7+8σ", ts))
    families.append({"name": "Z-threshold diversity\n(c=0.001, n_consec=1, trig+LVDS, withTC)", "panels": panels})

    # ── 2: feature-variant diversity — scan all z ────────────────────────────
    panels = []
    for z in Z_THRESHOLDS:
        base_f = dict(if_contamination=0.001, alert_consecutive_n=1,
                      z_threshold=z, include_trigger_config=True)
        feat_tags = {nm: one(**base_f, **kw) for nm, kw in feat_variants}
        for nm, t in feat_tags.items():
            if t: panels.append((f"{nm} @ z={z}σ", [t]))
        for (n1, t1), (n2, t2) in combinations(feat_tags.items(), 2):
            if t1 and t2: panels.append((f"z={z}σ: {n1}+{n2}", [t1, t2]))
        valid = [t for t in feat_tags.values() if t]
        if len(valid) == 4: panels.append((f"z={z}σ: all 4 variants", valid))
    families.append({"name": "Feature-variant diversity — all z\n(c=0.001, n_consec=1, withTC)", "panels": panels})

    # ── 3: TriggerConfig × feature-variant — scan all z ─────────────────────
    panels = []
    for z in Z_THRESHOLDS:
        base_tc = dict(if_contamination=0.001, alert_consecutive_n=1, z_threshold=z)
        for feat_name, feat_kw in feat_variants:
            twc = one(**base_tc, include_trigger_config=True,  **feat_kw)
            tnc = one(**base_tc, include_trigger_config=False, **feat_kw)
            if twc: panels.append((f"{feat_name}/z={z}σ wTC",     [twc]))
            if tnc: panels.append((f"{feat_name}/z={z}σ noTC",    [tnc]))
            if twc and tnc: panels.append((f"{feat_name}/z={z}σ wTC+noTC", [twc, tnc]))
    families.append({"name": "TriggerConfig × feature-variant — all z\n(c=0.001, n_consec=1)", "panels": panels})

    # ── 4: contamination diversity — scan all z ───────────────────────────────
    panels = []
    for z in Z_THRESHOLDS:
        base_c = dict(alert_consecutive_n=1, z_threshold=z,
                      use_trigger=True, use_lvds=True, include_trigger_config=True)
        for c in CONTAMINATIONS:
            t = one(**base_c, if_contamination=c)
            if t: panels.append((f"c={c} @ z={z}σ", [t]))
        for c1, c2 in combinations(CONTAMINATIONS, 2):
            t1 = one(**base_c, if_contamination=c1)
            t2 = one(**base_c, if_contamination=c2)
            if t1 and t2: panels.append((f"z={z}σ: c={c1}+{c2}", [t1, t2]))
        tc_all = [one(**base_c, if_contamination=c) for c in CONTAMINATIONS]
        if all(tc_all): panels.append((f"z={z}σ: all 4 c", tc_all))
    families.append({"name": "Contamination diversity — all z\n(n_consec=1, trig+LVDS, withTC)", "panels": panels})

    # ── 6: low-z + high-z × complementary features ───────────────────────────
    base_x = dict(if_contamination=0.001, alert_consecutive_n=1,
                  include_trigger_config=True)
    panels = [
        ("z6_digi + z8_trig+LVDS",
         [one(**base_x, z_threshold=6, use_trigger=False, use_lvds=False),
          one(**base_x, z_threshold=8, use_trigger=True,  use_lvds=True)]),
        ("z6_trig+LVDS + z8_digi",
         [one(**base_x, z_threshold=6, use_trigger=True,  use_lvds=True),
          one(**base_x, z_threshold=8, use_trigger=False, use_lvds=False)]),
        ("z6_trig + z8_LVDS",
         [one(**base_x, z_threshold=6, use_trigger=True,  use_lvds=False),
          one(**base_x, z_threshold=8, use_trigger=False, use_lvds=True)]),
        ("z6_LVDS + z8_trig",
         [one(**base_x, z_threshold=6, use_trigger=False, use_lvds=True),
          one(**base_x, z_threshold=8, use_trigger=True,  use_lvds=False)]),
        ("z6_digi + z6_trig+LVDS + z8_digi + z8_trig+LVDS",
         [one(**base_x, z_threshold=6, use_trigger=False, use_lvds=False),
          one(**base_x, z_threshold=6, use_trigger=True,  use_lvds=True),
          one(**base_x, z_threshold=8, use_trigger=False, use_lvds=False),
          one(**base_x, z_threshold=8, use_trigger=True,  use_lvds=True)]),
    ]
    panels = [(lbl, [t for t in ts if t]) for lbl, ts in panels
              if all(t for t in ts)]
    families.append({"name": "Low-z + high-z × feature complementarity\n(c=0.001, n_consec=1, withTC)", "panels": panels})

    # ── 7: TC × z cross ──────────────────────────────────────────────────────
    base_tz = dict(if_contamination=0.001, alert_consecutive_n=1,
                   use_trigger=True, use_lvds=True)
    panels = []
    for z in Z_THRESHOLDS:
        twc = one(**base_tz, z_threshold=z, include_trigger_config=True)
        tnc = one(**base_tz, z_threshold=z, include_trigger_config=False)
        if twc and tnc: panels.append((f"z={z}σ withTC+noTC", [twc, tnc]))
    for z1, z2 in [(6, 8), (6, 7)]:
        for tc1, tc2 in [(True, False), (False, True)]:
            t1 = one(**base_tz, z_threshold=z1, include_trigger_config=tc1)
            t2 = one(**base_tz, z_threshold=z2, include_trigger_config=tc2)
            s1, s2 = "wTC" if tc1 else "noTC", "wTC" if tc2 else "noTC"
            if t1 and t2: panels.append((f"z={z1}σ-{s1} + z={z2}σ-{s2}", [t1, t2]))
    families.append({"name": "TC-setting × z-threshold cross\n(c=0.001, n_consec=1, trig+LVDS)", "panels": panels})

    # ── 8: contamination × z cross ───────────────────────────────────────────
    base_cz = dict(alert_consecutive_n=1,
                   use_trigger=True, use_lvds=True, include_trigger_config=True)
    panels = []
    for z in Z_THRESHOLDS:
        tlo = one(**base_cz, z_threshold=z, if_contamination=0.001)
        thi = one(**base_cz, z_threshold=z, if_contamination=0.05)
        if tlo and thi: panels.append((f"z={z}σ: c=0.001+c=0.05", [tlo, thi]))
    for z1, z2, c1, c2 in [(6, 8, 0.001, 0.05), (6, 8, 0.05, 0.001),
                            (6, 8, 0.005, 0.01)]:
        t1 = one(**base_cz, z_threshold=z1, if_contamination=c1)
        t2 = one(**base_cz, z_threshold=z2, if_contamination=c2)
        if t1 and t2: panels.append((f"z={z1}σ-c={c1} + z={z2}σ-c={c2}", [t1, t2]))
    families.append({"name": "Contamination × z-threshold cross\n(n_consec=1, trig+LVDS, withTC)", "panels": panels})

    # ── 9: maximum diversity ─────────────────────────────────────────────────
    base_md = dict(alert_consecutive_n=1)
    combos = [
        ("z6-c0.001-trig+LVDS-wTC + z8-c0.05-digi-noTC",
         [one(**base_md, z_threshold=6, if_contamination=0.001,
              use_trigger=True,  use_lvds=True,  include_trigger_config=True),
          one(**base_md, z_threshold=8, if_contamination=0.05,
              use_trigger=False, use_lvds=False, include_trigger_config=False)]),
        ("z6-c0.001-digi-wTC + z8-c0.05-trig+LVDS-noTC",
         [one(**base_md, z_threshold=6, if_contamination=0.001,
              use_trigger=False, use_lvds=False, include_trigger_config=True),
          one(**base_md, z_threshold=8, if_contamination=0.05,
              use_trigger=True,  use_lvds=True,  include_trigger_config=False)]),
        ("4-model: z6/8 × c-lo/hi × trig+LVDS × wTC",
         [one(**base_md, z_threshold=z, if_contamination=c,
              use_trigger=True, use_lvds=True, include_trigger_config=True)
          for z in [6, 8] for c in [0.001, 0.05]]),
        ("4-model: z6/8 × digi/trig+LVDS × c=0.001 × wTC",
         [one(**base_md, z_threshold=z, if_contamination=0.001,
              use_trigger=ut, use_lvds=ul, include_trigger_config=True)
          for z in [6, 8] for ut, ul in [(False, False), (True, True)]]),
        ("6-model: all z × trig+LVDS × wTC/noTC × c=0.001",
         [one(**base_md, z_threshold=z, if_contamination=0.001,
              use_trigger=True, use_lvds=True, include_trigger_config=tc)
          for z in Z_THRESHOLDS for tc in [True, False]]),
    ]
    panels = [(lbl, ts) for lbl, ts in combos if all(ts)]
    families.append({"name": "Maximum diversity panels\n(n_consec=1, various)", "panels": panels})

    # ── 10: explicit 3-model panels ───────────────────────────────────────────
    base_3 = dict(alert_consecutive_n=1)
    combos_3 = []

    # z=6+7+8 for each feature variant
    for feat_name, feat_kw in feat_variants:
        ts = [one(**base_3, z_threshold=z, if_contamination=0.001,
                  include_trigger_config=True, **feat_kw)
              for z in Z_THRESHOLDS]
        if all(ts):
            combos_3.append((f"z=6+7+8σ, {feat_name}, wTC", ts))

    # feature diversity — 3 out of 4 variants at z=6
    feat_triples = [
        ("digi+trig+trig+LVDS",  [(False,False), (True,False), (True,True)]),
        ("digi+LVDS+trig+LVDS",  [(False,False), (False,True), (True,True)]),
    ]
    for lbl_f, feat_set in feat_triples:
        ts = [one(**base_3, z_threshold=6, if_contamination=0.001,
                  include_trigger_config=True, use_trigger=ut, use_lvds=ul)
              for ut, ul in feat_set]
        if all(ts):
            combos_3.append((f"{lbl_f} (z=6σ, wTC)", ts))

    # z × feature cross: trig+LVDS@z=6 + digi@z=7 + trig+LVDS@z=8
    ts = [one(**base_3, if_contamination=0.001, include_trigger_config=True,
              z_threshold=6, use_trigger=True,  use_lvds=True),
          one(**base_3, if_contamination=0.001, include_trigger_config=True,
              z_threshold=7, use_trigger=False, use_lvds=False),
          one(**base_3, if_contamination=0.001, include_trigger_config=True,
              z_threshold=8, use_trigger=True,  use_lvds=True)]
    if all(ts):
        combos_3.append(("z=6/trig+LVDS + z=7/digi + z=8/trig+LVDS (wTC)", ts))

    # z × TC cross: z=6/wTC + z=7/noTC + z=8/wTC
    ts = [one(**base_3, if_contamination=0.001, use_trigger=True, use_lvds=True,
              z_threshold=6, include_trigger_config=True),
          one(**base_3, if_contamination=0.001, use_trigger=True, use_lvds=True,
              z_threshold=7, include_trigger_config=False),
          one(**base_3, if_contamination=0.001, use_trigger=True, use_lvds=True,
              z_threshold=8, include_trigger_config=True)]
    if all(ts):
        combos_3.append(("z=6/wTC + z=7/noTC + z=8/wTC (trig+LVDS)", ts))

    # contamination × z: c=0.001@z=6 + c=0.01@z=7 + c=0.05@z=8
    ts = [one(**base_3, use_trigger=True, use_lvds=True, include_trigger_config=True,
              z_threshold=z, if_contamination=c)
          for z, c in [(6, 0.001), (7, 0.01), (8, 0.05)]]
    if all(ts):
        combos_3.append(("c=0.001@z=6 + c=0.01@z=7 + c=0.05@z=8 (trig+LVDS, wTC)", ts))

    panels = [(lbl, ts) for lbl, ts in combos_3]
    families.append({"name": "3-model ensemble panels\n(n_consec=1, various)", "panels": panels})

    return families


def _build_panels_all_n(params: dict, one, combinations) -> list[dict]:
    """
    Panel families for the all-n study.
    Focuses on the n dimension and its interactions — complementary to consec1 PDF.
    """
    families = []

    feat_variants = [
        ("digi",      dict(use_trigger=False, use_lvds=False)),
        ("trig",      dict(use_trigger=True,  use_lvds=False)),
        ("LVDS",      dict(use_trigger=False, use_lvds=True)),
        ("trig+LVDS", dict(use_trigger=True,  use_lvds=True)),
    ]

    # ── 1: consecutive_n diversity — scan all z ──────────────────────────────
    panels = []
    for z in Z_THRESHOLDS:
        base = dict(if_contamination=0.001, z_threshold=z,
                    use_trigger=True, use_lvds=True, include_trigger_config=True)
        for n in CONSEC_VALUES:
            t = one(**base, alert_consecutive_n=n)
            if t: panels.append((f"n_consec={n} @ z={z}σ", [t]))
        for n1, n2 in combinations(CONSEC_VALUES, 2):
            t1 = one(**base, alert_consecutive_n=n1)
            t2 = one(**base, alert_consecutive_n=n2)
            if t1 and t2: panels.append((f"z={z}σ: n={n1}+n={n2}", [t1, t2]))
        cn_all = [one(**base, alert_consecutive_n=n) for n in CONSEC_VALUES]
        if all(cn_all): panels.append((f"z={z}σ: all n=1..5", cn_all))
    families.append({"name": "consecutive_n diversity — all z\n(c=0.001, trig+LVDS, withTC)", "panels": panels})

    # ── 2: n × z cross ───────────────────────────────────────────────────────
    base_nz = dict(if_contamination=0.001,
                   use_trigger=True, use_lvds=True, include_trigger_config=True)
    panels = []
    for n in CONSEC_VALUES:
        for z in Z_THRESHOLDS:
            t = one(**base_nz, alert_consecutive_n=n, z_threshold=z)
            if t: panels.append((f"n_consec={n}, z={z}σ alone", [t]))
    for n1, n2 in [(1, 3), (1, 5), (2, 4)]:
        for z1, z2 in [(6, 8), (6, 7)]:
            t1 = one(**base_nz, alert_consecutive_n=n1, z_threshold=z1)
            t2 = one(**base_nz, alert_consecutive_n=n2, z_threshold=z2)
            if t1 and t2: panels.append((f"n_consec={n1}-z={z1}σ + n_consec={n2}-z={z2}σ", [t1, t2]))
            # also same z, different n
            t3 = one(**base_nz, alert_consecutive_n=n1, z_threshold=z1)
            t4 = one(**base_nz, alert_consecutive_n=n2, z_threshold=z1)
            if t3 and t4: panels.append((f"n_consec={n1}+n_consec={n2} @ z={z1}σ", [t3, t4]))
    families.append({"name": "consecutive_n × z-threshold cross\n(c=0.001, trig+LVDS, withTC)", "panels": panels})

    # ── 3: n × feature-variant — scan all z ──────────────────────────────────
    panels = []
    for z in Z_THRESHOLDS:
        base_nf = dict(if_contamination=0.001, z_threshold=z, include_trigger_config=True)
        for n in [1, 3, 5]:
            for feat_name, feat_kw in feat_variants:
                t = one(**base_nf, alert_consecutive_n=n, **feat_kw)
                if t: panels.append((f"n={n}/{feat_name} @ z={z}σ", [t]))
        for (feat1, kw1), (feat2, kw2) in combinations(feat_variants, 2):
            t1 = one(**base_nf, alert_consecutive_n=1, **kw1)
            t2 = one(**base_nf, alert_consecutive_n=3, **kw2)
            if t1 and t2: panels.append((f"z={z}σ: n=1/{feat1}+n=3/{feat2}", [t1, t2]))
            t1 = one(**base_nf, alert_consecutive_n=3, **kw1)
            t2 = one(**base_nf, alert_consecutive_n=1, **kw2)
            if t1 and t2: panels.append((f"z={z}σ: n=3/{feat1}+n=1/{feat2}", [t1, t2]))
    families.append({"name": "consecutive_n × feature-variant — all z\n(c=0.001, withTC)", "panels": panels})

    # ── 4: n × TriggerConfig — scan all z ────────────────────────────────────
    panels = []
    for z in Z_THRESHOLDS:
        base_ntc = dict(if_contamination=0.001, z_threshold=z,
                        use_trigger=True, use_lvds=True)
        for n in CONSEC_VALUES:
            twc = one(**base_ntc, alert_consecutive_n=n, include_trigger_config=True)
            tnc = one(**base_ntc, alert_consecutive_n=n, include_trigger_config=False)
            if twc and tnc: panels.append((f"z={z}σ n={n}: wTC+noTC", [twc, tnc]))
        for n1, n2 in [(1, 3), (1, 5)]:
            t1wc = one(**base_ntc, alert_consecutive_n=n1, include_trigger_config=True)
            t2nc = one(**base_ntc, alert_consecutive_n=n2, include_trigger_config=False)
            if t1wc and t2nc: panels.append((f"z={z}σ: n={n1}/wTC+n={n2}/noTC", [t1wc, t2nc]))
            t1nc = one(**base_ntc, alert_consecutive_n=n1, include_trigger_config=False)
            t2wc = one(**base_ntc, alert_consecutive_n=n2, include_trigger_config=True)
            if t1nc and t2wc: panels.append((f"z={z}σ: n={n1}/noTC+n={n2}/wTC", [t1nc, t2wc]))
    families.append({"name": "consecutive_n × TriggerConfig — all z\n(c=0.001, trig+LVDS)", "panels": panels})

    # ── 5: n × contamination — scan all z ────────────────────────────────────
    panels = []
    for z in Z_THRESHOLDS:
        base_nc = dict(z_threshold=z, use_trigger=True, use_lvds=True,
                       include_trigger_config=True)
        for n in CONSEC_VALUES:
            for c in CONTAMINATIONS:
                t = one(**base_nc, alert_consecutive_n=n, if_contamination=c)
                if t: panels.append((f"n={n}/c={c} @ z={z}σ", [t]))
        for n1, n2 in [(1, 3), (1, 5)]:
            for c1, c2 in [(0.001, 0.05), (0.005, 0.01)]:
                t1 = one(**base_nc, alert_consecutive_n=n1, if_contamination=c1)
                t2 = one(**base_nc, alert_consecutive_n=n2, if_contamination=c2)
                if t1 and t2: panels.append((f"z={z}σ: n={n1}/c={c1}+n={n2}/c={c2}", [t1, t2]))
    families.append({"name": "consecutive_n × contamination — all z\n(trig+LVDS, withTC)", "panels": panels})

    # ── 6: n_consec=1 vs n_consec=3 vs n_consec=5 across all z values ─────────────────────────────
    # Shows how the z/n interaction shapes the FP–coverage tradeoff
    base_nzs = dict(if_contamination=0.001, use_trigger=True,
                    use_lvds=True, include_trigger_config=True)
    panels = []
    for z in Z_THRESHOLDS:
        for n in [1, 3, 5]:
            t = one(**base_nzs, z_threshold=z, alert_consecutive_n=n)
            if t: panels.append((f"z={z}σ, n_consec={n}", [t]))
        # mix n_consec=1 (sensitive) + n_consec=5 (strict) at same z
        t1, t5 = (one(**base_nzs, z_threshold=z, alert_consecutive_n=1),
                  one(**base_nzs, z_threshold=z, alert_consecutive_n=5))
        if t1 and t5: panels.append((f"z={z}σ: n_consec=1+n_consec=5", [t1, t5]))
    families.append({"name": "n_consec=1/3/5 across all z-thresholds\n(c=0.001, trig+LVDS, withTC)", "panels": panels})

    # ── 7: maximum diversity including n ─────────────────────────────────────
    combos = [
        ("n_consec=1-z=6-digi-wTC + n_consec=5-z=8-trig+LVDS-noTC",
         [one(alert_consecutive_n=1, z_threshold=6, if_contamination=0.001,
              use_trigger=False, use_lvds=False, include_trigger_config=True),
          one(alert_consecutive_n=5, z_threshold=8, if_contamination=0.001,
              use_trigger=True,  use_lvds=True,  include_trigger_config=False)]),
        ("n_consec=1-z=6-trig+LVDS-wTC + n_consec=5-z=8-digi-wTC",
         [one(alert_consecutive_n=1, z_threshold=6, if_contamination=0.001,
              use_trigger=True, use_lvds=True, include_trigger_config=True),
          one(alert_consecutive_n=5, z_threshold=8, if_contamination=0.001,
              use_trigger=False, use_lvds=False, include_trigger_config=True)]),
        ("4-model: n_consec=1/3 × z=6/8 × trig+LVDS × wTC",
         [one(alert_consecutive_n=n, z_threshold=z, if_contamination=0.001,
              use_trigger=True, use_lvds=True, include_trigger_config=True)
          for n in [1, 3] for z in [6, 8]]),
        ("4-model: n_consec=1/5 × z=6/8 × trig+LVDS × wTC",
         [one(alert_consecutive_n=n, z_threshold=z, if_contamination=0.001,
              use_trigger=True, use_lvds=True, include_trigger_config=True)
          for n in [1, 5] for z in [6, 8]]),
        ("6-model: n_consec=1/3/5 × z=6/8 × trig+LVDS × wTC",
         [one(alert_consecutive_n=n, z_threshold=z, if_contamination=0.001,
              use_trigger=True, use_lvds=True, include_trigger_config=True)
          for n in [1, 3, 5] for z in [6, 8]]),
        ("4-model: n_consec=1/3 × feat:digi/trig+LVDS × z=6 × wTC",
         [one(alert_consecutive_n=n, z_threshold=6, if_contamination=0.001,
              use_trigger=ut, use_lvds=ul, include_trigger_config=True)
          for n in [1, 3] for ut, ul in [(False, False), (True, True)]]),
    ]
    panels = [(lbl, ts) for lbl, ts in combos if all(ts)]
    families.append({"name": "Maximum diversity including n\n(c=0.001, various)", "panels": panels})

    # ── 8: explicit 3-model panels exploring n ────────────────────────────────
    base_3n = dict(if_contamination=0.001, use_trigger=True,
                   use_lvds=True, include_trigger_config=True)
    combos_3n = []

    # n=1+3+5 at each z
    for z in Z_THRESHOLDS:
        ts = [one(**base_3n, z_threshold=z, alert_consecutive_n=n) for n in [1, 3, 5]]
        if all(ts):
            combos_3n.append((f"n=1+3+5 @ z={z}σ (trig+LVDS, wTC)", ts))

    # n=1+2+3 at each z
    for z in Z_THRESHOLDS:
        ts = [one(**base_3n, z_threshold=z, alert_consecutive_n=n) for n in [1, 2, 3]]
        if all(ts):
            combos_3n.append((f"n=1+2+3 @ z={z}σ (trig+LVDS, wTC)", ts))

    # n × z cross: n=1@z=6 + n=3@z=7 + n=5@z=8
    ts = [one(**base_3n, alert_consecutive_n=1, z_threshold=6),
          one(**base_3n, alert_consecutive_n=3, z_threshold=7),
          one(**base_3n, alert_consecutive_n=5, z_threshold=8)]
    if all(ts):
        combos_3n.append(("n=1/z=6 + n=3/z=7 + n=5/z=8 (trig+LVDS, wTC)", ts))

    # n × z × feature: n=1/trig+LVDS@z=6 + n=3/digi@z=6 + n=5/trig+LVDS@z=8
    ts = [one(alert_consecutive_n=1, z_threshold=6, if_contamination=0.001,
              use_trigger=True,  use_lvds=True,  include_trigger_config=True),
          one(alert_consecutive_n=3, z_threshold=6, if_contamination=0.001,
              use_trigger=False, use_lvds=False, include_trigger_config=True),
          one(alert_consecutive_n=5, z_threshold=8, if_contamination=0.001,
              use_trigger=True,  use_lvds=True,  include_trigger_config=True)]
    if all(ts):
        combos_3n.append(("n=1/trig+LVDS@z=6 + n=3/digi@z=6 + n=5/trig+LVDS@z=8 (wTC)", ts))

    panels = [(lbl, ts) for lbl, ts in combos_3n]
    families.append({"name": "3-model ensemble panels (n variation)\n(c=0.001, various)", "panels": panels})

    return families


def build_panels(all_tags: list[str], consec1_only: bool) -> list[dict]:
    """
    Dispatch to the appropriate panel-family builder.
      consec1_only=True  → n_consec=1 fixed, study z/features/TC/contamination
      consec1_only=False → study the n dimension and its interactions
    """
    params = {t: parse_tag(t) for t in all_tags}
    params = {t: p for t, p in params.items() if p is not None}

    def select(**kwargs) -> list[str]:
        result = []
        for t, p in params.items():
            if consec1_only and p["alert_consecutive_n"] != 1:
                continue
            if all(p.get(k) == v for k, v in kwargs.items()):
                result.append(t)
        return result

    def one(**kwargs) -> "str | None":
        found = select(**kwargs)
        return found[0] if found else None

    if consec1_only:
        return _build_panels_consec1(params, one, combinations)
    else:
        return _build_panels_all_n(params, one, combinations)


# ── Plotting ──────────────────────────────────────────────────────────────────

# 10 colours for panels within a family
_COLOURS = [plt.cm.tab10(i) for i in range(10)]


def _make_family_figure(
    family_name:  str,
    panels:       list,          # [(label, [tags]), ...]
    all_tags:     list[str],
    subrun_ids:   list,
    ok_mat:       np.ndarray,
    scored_mat:   np.ndarray,
    kg_runs:      set[int],
) -> "plt.Figure | None":
    """
    3-panel figure per family:
      left   — FP rate vs k
      middle — Coverage rate vs k
      right  — FP vs Coverage tradeoff (parametric in k)
    """
    valid_panels = []
    for lbl, tags in panels:
        col_ids = panel_indices(all_tags, tags)
        if len(col_ids) < len(tags):
            continue   # some models not loaded
        sweep = sweep_k(subrun_ids, ok_mat, scored_mat, col_ids, kg_runs)
        if sweep:
            valid_panels.append((lbl, col_ids, sweep))

    if not valid_panels:
        return None

    fig, axes = plt.subplots(1, 3, figsize=(18, 5), constrained_layout=True)
    fig.suptitle(family_name, fontsize=11, fontweight="bold")

    ax_fp, ax_cov, ax_tradeoff = axes

    ax_fp.set_title("FP rate vs alert threshold k", fontsize=9)
    ax_fp.set_xlabel("k  (# bad-vote alerts needed to classify as bad)", fontsize=9)
    ax_fp.set_ylabel("FP rate  (% known-good → alert)", fontsize=9)
    ax_fp.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax_fp.yaxis.set_minor_locator(MultipleLocator(5))
    ax_fp.grid(True, which="major", alpha=0.3)

    ax_cov.set_title("Coverage vs alert threshold k", fontsize=9)
    ax_cov.set_xlabel("k  (# bad-vote alerts needed to classify as bad)", fontsize=9)
    ax_cov.set_ylabel("Coverage  (% subruns → ok)", fontsize=9)
    ax_cov.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax_cov.set_ylim(0, 100)
    ax_cov.yaxis.set_major_locator(MultipleLocator(20))
    ax_cov.yaxis.set_minor_locator(MultipleLocator(10))
    ax_cov.grid(True, which="major", alpha=0.3)

    ax_tradeoff.set_title("FP rate vs Coverage  (k as parameter)", fontsize=9)
    ax_tradeoff.set_xlabel("Coverage  (% subruns → ok)", fontsize=9)
    ax_tradeoff.set_ylabel("FP rate  (% known-good → alert)", fontsize=9)
    ax_tradeoff.grid(True, which="major", alpha=0.3)

    for idx, (lbl, col_ids, sweep) in enumerate(valid_panels):
        colour = _COLOURS[idx % len(_COLOURS)]
        ks       = [s["k"]        for s in sweep]
        fp_vals  = [s["fp_rate"]  for s in sweep]
        cov_vals = [s["cov_rate"] for s in sweep]
        n        = sweep[0]["n"]
        n_sub    = sweep[0]["n_subruns"]
        full_lbl = f"{lbl}  [N={n}, {n_sub} subruns]"

        ax_fp.plot(ks, fp_vals,  color=colour, marker="o", markersize=5,
                   linewidth=1.5, label=full_lbl)
        ax_cov.plot(ks, cov_vals, color=colour, marker="o", markersize=5,
                    linewidth=1.5, label=full_lbl)
        ax_tradeoff.plot(cov_vals, fp_vals, color=colour, marker="o",
                         markersize=5, linewidth=1.5, label=full_lbl)
        # annotate k values on tradeoff plot
        for s in sweep:
            ax_tradeoff.annotate(f"k={s['k']}", (s["cov_rate"], s["fp_rate"]),
                                 fontsize=6, color=colour,
                                 xytext=(3, 3), textcoords="offset points")

    for ax in [ax_fp, ax_cov, ax_tradeoff]:
        ax.legend(fontsize=7, framealpha=0.9, loc="best")

    return fig


def _make_profile_figure(
    title:       str,
    panels:      list,           # [(label, [tags]), ...]
    k_fracs:     list[float],    # e.g. [0.5, 1.0] — k/N values to plot
    all_tags:    list[str],
    subrun_ids:  list,
    ok_mat:      np.ndarray,
    scored_mat:  np.ndarray,
    kg_runs:     set[int],
    training_runs: "set[int] | None" = None,
) -> "plt.Figure | None":
    """Per-run ok-rate profile for selected panels at one or more k/N values."""
    from collections import defaultdict

    # One column per k_frac value
    n_cols  = len(k_fracs)
    fig, axes = plt.subplots(1, n_cols, figsize=(10 * n_cols, 5),
                             constrained_layout=True, squeeze=False)
    fig.suptitle(title, fontsize=11, fontweight="bold")

    has_data = False
    for col, kf in enumerate(k_fracs):
        ax = axes[0, col]
        ax.set_title(f"k/N = {kf:.2g}  (majority-like threshold)", fontsize=9)
        ax.set_xlabel("run number", fontsize=9)
        ax.set_ylabel("% ok subruns", fontsize=9)
        ax.set_ylim(0, 100)
        ax.yaxis.set_major_locator(MultipleLocator(20))
        ax.yaxis.set_minor_locator(MultipleLocator(10))
        ax.grid(True, which="major", alpha=0.3)
        ax.yaxis.grid(True, which="minor", alpha=0.15)

        if training_runs:
            for start, end in _consecutive_blocks(training_runs):
                ax.axvspan(start - 0.5, end + 0.5, color="lightgray",
                           alpha=0.35, linewidth=0, zorder=0)

        for idx, (lbl, tags) in enumerate(panels):
            col_ids = panel_indices(all_tags, tags)
            if len(col_ids) < len(tags):
                continue
            n = len(col_ids)
            k = max(1, round(kf * n))
            m = vote_metrics(subrun_ids, ok_mat, scored_mat, col_ids, k, kg_runs)
            if m is None:
                continue
            rr = m["run_ok_rates"]
            xs = sorted(rr.keys())
            ys = [rr[x] for x in xs]
            fp = m["fp_rate"]
            full_lbl = f"{lbl}  [k={k}/{n}, FP={fp:.1f}%]"
            ax.plot(xs, ys, color=_COLOURS[idx % len(_COLOURS)],
                    linewidth=1.4, alpha=0.85, label=full_lbl)
            has_data = True

        ax.legend(fontsize=7.5, loc="lower left", framealpha=0.9)

    if not has_data:
        plt.close(fig)
        return None
    return fig


# ── Top-N summary pages ───────────────────────────────────────────────────────

def _make_topN_figure(
    all_tags:    list[str],
    subrun_ids:  list,
    ok_mat:      np.ndarray,
    scored_mat:  np.ndarray,
    kg_runs:     set[int],
    training_runs: "set[int] | None",
    top_n:       int = 5,
    k_frac:      float = 0.5,
) -> "plt.Figure | None":
    """
    Summary figure: for each single model, compute FP and coverage at k=1,
    then show the top_n models with lowest FP as per-run profiles.
    """
    single_metrics = []
    for j, t in enumerate(all_tags):
        col_ids = np.array([j], dtype=int)
        m = vote_metrics(subrun_ids, ok_mat, scored_mat, col_ids, 1, kg_runs)
        if m and not np.isnan(m["fp_rate"]):
            single_metrics.append((t, m))
    if not single_metrics:
        return None

    ranked = sorted(single_metrics, key=lambda x: x[1]["fp_rate"])[:top_n]

    fig, ax = plt.subplots(figsize=(16, 6), constrained_layout=True)
    fig.suptitle(
        f"Top {top_n} single models — lowest FP rate  (k/N = {k_frac:.2g})",
        fontsize=12, fontweight="bold",
    )
    ax.set_xlabel("run number", fontsize=9)
    ax.set_ylabel("% ok subruns", fontsize=9)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_locator(MultipleLocator(20))
    ax.yaxis.set_minor_locator(MultipleLocator(10))
    ax.grid(True, which="major", alpha=0.3)
    ax.yaxis.grid(True, which="minor", alpha=0.15)

    if training_runs:
        for start, end in _consecutive_blocks(training_runs):
            ax.axvspan(start - 0.5, end + 0.5, color="lightgray",
                       alpha=0.35, linewidth=0, zorder=0)

    for i, (t, m) in enumerate(ranked):
        p   = parse_tag(t)
        lbl = f"{short_label(p)}  [FP={m['fp_rate']:.2f}%]"
        rr  = m["run_ok_rates"]
        xs  = sorted(rr.keys())
        ys  = [rr[x] for x in xs]
        ax.plot(xs, ys, color=_COLOURS[i % len(_COLOURS)],
                linewidth=1.4, alpha=0.85, label=lbl)

    ax.legend(fontsize=7.5, loc="lower left", framealpha=0.9)
    return fig


# ── Combinatorial search ──────────────────────────────────────────────────────

def _individual_fp_cov(
    ok_mat:     np.ndarray,
    scored_mat: np.ndarray,
    kg_mask:    np.ndarray,
) -> "tuple[np.ndarray, np.ndarray]":
    """Return per-model FP (%) and coverage (%) arrays, shape (n_models,)."""
    n_subruns, n_models = ok_mat.shape
    bad_sc  = ((1 - ok_mat) & scored_mat).astype(np.uint8)
    kg_u8   = kg_mask.astype(np.uint8)
    fp_arr  = np.full(n_models, np.nan)
    cov_arr = np.zeros(n_models)
    for j in range(n_models):
        s = scored_mat[:, j].astype(bool)
        if not s.any():
            continue
        bad = bad_sc[:, j].astype(bool)
        kg_s = kg_mask & s
        if kg_s.any():
            fp_arr[j] = bad[kg_s].sum() / kg_s.sum() * 100
        cov_arr[j] = (s.sum() - bad.sum()) / s.sum() * 100
    return fp_arr, cov_arr


def search_top_panels(
    ok_mat:          np.ndarray,
    scored_mat:      np.ndarray,
    kg_mask:         np.ndarray,
    tags:            list[str],
    n_panel:         int,
    top_n:           int = 3,
    constrain_z6_z8: bool = False,
    max_candidates:  int = 100,
) -> "tuple[list, list]":
    """
    Search C(candidates, n_panel) combinations, scoring each at k=n_panel
    (AND gate: bad only if all N models agree).

    Returns:
        best_fp  — top_n combos as (fp, cov, [tags]), sorted by FP ascending
        best_cov — top_n combos as (fp, cov, [tags]), sorted by coverage descending
    """
    n_models = ok_mat.shape[1]
    bad_sc  = ((1 - ok_mat) & scored_mat).astype(np.uint8)
    sc_u8   = scored_mat.astype(np.uint8)
    kg_u8   = kg_mask.astype(np.uint8)

    fp_ind, cov_ind = _individual_fp_cov(ok_mat, scored_mat, kg_mask)

    params_d = {t: parse_tag(t) for t in tags}
    z6_set = {i for i, t in enumerate(tags) if params_d[t] and params_d[t]["z_threshold"] == 6}
    z8_set = {i for i, t in enumerate(tags) if params_d[t] and params_d[t]["z_threshold"] == 8}

    def _eval(combo):
        bad_kN    = bad_sc[:, combo[0]].copy()
        scored_all = sc_u8[:, combo[0]].copy()
        for c in combo[1:]:
            bad_kN    &= bad_sc[:, c]
            scored_all &= sc_u8[:, c]
        n_sc = int(scored_all.sum())
        if n_sc == 0:
            return None
        kg_in = scored_all & kg_u8
        n_kg  = int(kg_in.sum())
        if n_kg == 0:
            return None
        fp  = float((bad_kN & kg_u8).sum()) / n_kg * 100
        cov = (n_sc - int(bad_kN.sum())) / n_sc * 100
        return fp, cov

    def _select_candidates(sort_key, reverse=False):
        valid = [i for i in range(n_models) if not np.isnan(fp_ind[i])]
        cands = sorted(valid, key=sort_key, reverse=reverse)
        if constrain_z6_z8:
            # Ensure z6 and z8 are both represented among candidates
            z6_c = sorted([i for i in cands if i in z6_set], key=sort_key, reverse=reverse)
            z8_c = sorted([i for i in cands if i in z8_set], key=sort_key, reverse=reverse)
            rest = [i for i in cands if i not in z6_set and i not in z8_set]
            half = max_candidates // 2
            return list(dict.fromkeys(z6_c[:half] + z8_c[:half] + rest))[:max_candidates]
        return cands[:max_candidates]

    fp_cands  = _select_candidates(lambda i: fp_ind[i])
    cov_cands = _select_candidates(lambda i: -cov_ind[i])

    def _search(cands):
        fp_res, cov_res = [], []
        if constrain_z6_z8:
            combo_iter = (c for c in combinations(cands, n_panel)
                          if any(i in z6_set for i in c) and any(i in z8_set for i in c))
        else:
            combo_iter = combinations(cands, n_panel)
        for combo in combo_iter:
            r = _eval(combo)
            if r is None:
                continue
            fp, cov = r
            tc = [tags[i] for i in combo]
            fp_res.append((fp, cov, tc))
            cov_res.append((fp, cov, tc))
        fp_res.sort(key=lambda x: (x[0], -x[1]))
        cov_res.sort(key=lambda x: (-x[1], x[0]))
        return fp_res[:top_n], cov_res[:top_n]

    best_fp,  _         = _search(fp_cands)
    _,        best_cov  = _search(cov_cands)
    return best_fp, best_cov


def _make_search_figure(
    title:       str,
    results:     list,           # [(fp, cov, [tags]), ...]  top-3
    all_tags:    list[str],
    subrun_ids:  list,
    ok_mat:      np.ndarray,
    scored_mat:  np.ndarray,
    kg_runs:     set[int],
    n_panel:     int,
) -> "plt.Figure | None":
    """3-panel figure for top-N search results (FP vs k, coverage vs k, tradeoff)."""
    if not results:
        return None

    fig, axes = plt.subplots(1, 3, figsize=(18, 5), constrained_layout=True)
    fig.suptitle(title, fontsize=10, fontweight="bold")
    ax_fp, ax_cov, ax_tr = axes

    ax_fp.set_title(f"FP rate vs k  (N={n_panel})", fontsize=9)
    ax_fp.set_xlabel("k  (# bad-vote alerts needed to classify as bad)", fontsize=8)
    ax_fp.set_ylabel("FP rate  (% known-good → alert)", fontsize=9)
    ax_fp.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax_fp.grid(True, which="major", alpha=0.3)

    ax_cov.set_title(f"Coverage vs k  (N={n_panel})", fontsize=9)
    ax_cov.set_xlabel("k  (# bad-vote alerts needed to classify as bad)", fontsize=8)
    ax_cov.set_ylabel("Coverage  (% subruns → ok)", fontsize=9)
    ax_cov.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax_cov.set_ylim(0, 100)
    ax_cov.grid(True, which="major", alpha=0.3)

    ax_tr.set_title("FP-Coverage tradeoff  (k as parameter)", fontsize=9)
    ax_tr.set_xlabel("Coverage  (% subruns → ok)", fontsize=9)
    ax_tr.set_ylabel("FP rate  (% known-good → alert)", fontsize=9)
    ax_tr.grid(True, which="major", alpha=0.3)

    for rank, (fp_kN, cov_kN, tags_combo) in enumerate(results):
        col_ids = panel_indices(all_tags, tags_combo)
        if len(col_ids) < len(tags_combo):
            continue
        sweep = sweep_k(subrun_ids, ok_mat, scored_mat, col_ids, kg_runs)
        if not sweep:
            continue
        ks       = [s["k"]        for s in sweep]
        fp_vals  = [s["fp_rate"]  for s in sweep]
        cov_vals = [s["cov_rate"] for s in sweep]
        n_sub    = sweep[0]["n_subruns"]
        model_lines = "\n    ".join(short_label(parse_tag(t)) for t in tags_combo)
        lbl = (f"Rank {rank+1}  [FP={fp_kN:.1f}%, cov={cov_kN:.1f}%, {n_sub} subruns]\n"
               f"    {model_lines}")
        c = _COLOURS[rank]
        ax_fp.plot( ks, fp_vals,  color=c, marker="o", ms=5, lw=1.5, label=lbl)
        ax_cov.plot(ks, cov_vals, color=c, marker="o", ms=5, lw=1.5, label=lbl)
        ax_tr.plot( cov_vals, fp_vals, color=c, marker="o", ms=5, lw=1.5, label=lbl)
        for s in sweep:
            ax_tr.annotate(f"k={s['k']}", (s["cov_rate"], s["fp_rate"]),
                           fontsize=6, color=c, xytext=(3, 3), textcoords="offset points")

    for ax in [ax_fp, ax_cov, ax_tr]:
        ax.legend(fontsize=6.5, framealpha=0.9, loc="best")
    return fig


def _make_combined_search_figure(
    n_panel:    int,
    best_fp:    list,           # [(fp, cov, [tags]), ...]  top-3, ranked by FP
    best_cov:   list,           # [(fp, cov, [tags]), ...]  top-3, ranked by coverage
    all_tags:   list[str],
    subrun_ids: list,
    ok_mat:     np.ndarray,
    scored_mat: np.ndarray,
    kg_runs:    set[int],
) -> "plt.Figure | None":
    """2×2 summary page: rows = ranking objective, columns = FP-rate / Coverage."""
    if not best_fp and not best_cov:
        return None

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), constrained_layout=True)
    fig.suptitle(
        f"N={n_panel} ensemble — unconstrained  "
        f"(top row: best FP at k=N  |  bottom row: best coverage at k=N)",
        fontsize=10, fontweight="bold",
    )

    row_data = [
        (best_fp,  "ranked by lowest FP rate at k=N"),
        (best_cov, "ranked by highest coverage at k=N"),
    ]

    for row, (results, row_label) in enumerate(row_data):
        ax_fp  = axes[row, 0]
        ax_cov = axes[row, 1]

        ax_fp.set_title(f"FP rate vs k  (N={n_panel})  — {row_label}", fontsize=8)
        ax_fp.set_xlabel("k  (# bad-vote alerts needed to classify as bad)", fontsize=7)
        ax_fp.set_ylabel("FP rate  (% known-good → alert)", fontsize=8)
        ax_fp.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax_fp.grid(True, which="major", alpha=0.3)

        ax_cov.set_title(f"Coverage vs k  (N={n_panel})  — {row_label}", fontsize=8)
        ax_cov.set_xlabel("k  (# bad-vote alerts needed to classify as bad)", fontsize=7)
        ax_cov.set_ylabel("Coverage  (% subruns → ok)", fontsize=8)
        ax_cov.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax_cov.set_ylim(0, 100)
        ax_cov.grid(True, which="major", alpha=0.3)

        for rank, (fp_kN, cov_kN, tags_combo) in enumerate(results):
            col_ids = panel_indices(all_tags, tags_combo)
            if len(col_ids) < len(tags_combo):
                continue
            sweep = sweep_k(subrun_ids, ok_mat, scored_mat, col_ids, kg_runs)
            if not sweep:
                continue
            ks       = [s["k"]        for s in sweep]
            fp_vals  = [s["fp_rate"]  for s in sweep]
            cov_vals = [s["cov_rate"] for s in sweep]
            n_sub    = sweep[0]["n_subruns"]
            model_lines = "\n    ".join(short_label(parse_tag(t)) for t in tags_combo)
            lbl = (f"Rank {rank+1}  [FP={fp_kN:.1f}%, cov={cov_kN:.1f}%, {n_sub} subruns]\n"
                   f"    {model_lines}")
            c = _COLOURS[rank]
            ax_fp.plot( ks, fp_vals,  color=c, marker="o", ms=4, lw=1.5, label=lbl)
            ax_cov.plot(ks, cov_vals, color=c, marker="o", ms=4, lw=1.5, label=lbl)

        for ax in [ax_fp, ax_cov]:
            ax.legend(fontsize=6, framealpha=0.9, loc="best")

    return fig


# ── PDF generation ────────────────────────────────────────────────────────────

def make_study_pdf(
    all_tags:      list[str],
    subrun_ids:    list,
    ok_mat:        np.ndarray,
    scored_mat:    np.ndarray,
    kg_runs:       set[int],
    training_runs: "set[int] | None",
    consec1_only:  bool,
    out_path:      Path,
) -> None:
    study_tags = ([t for t in all_tags
                   if parse_tag(t) and parse_tag(t)["alert_consecutive_n"] == 1]
                  if consec1_only else all_tags)
    study_col_idx = panel_indices(all_tags, study_tags)
    ok_s     = ok_mat[:,     study_col_idx]
    scored_s = scored_mat[:, study_col_idx]
    kg_mask  = np.array([run in kg_runs for run, _ in subrun_ids], dtype=bool)

    with PdfPages(out_path) as pdf:
        # ── Page 1: top-5 single models ───────────────────────────────────────
        fig = _make_topN_figure(study_tags, subrun_ids, ok_s, scored_s,
                                kg_runs, training_runs, top_n=5)
        if fig:
            pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)

        # ── Pages 2–9: exhaustive search for N=2 and N=3 ─────────────────────
        unconstrained_cache: dict[int, tuple] = {}   # n_panel → (best_fp, best_cov)
        for n_panel in [2, 3]:
            for constrained, c_label in [
                (False, "unconstrained"),
                (True,  "constrained: must include z=6σ and z=8σ model"),
            ]:
                print(f"    Searching N={n_panel}, {c_label} ...", flush=True)
                best_fp, best_cov = search_top_panels(
                    ok_s, scored_s, kg_mask, study_tags,
                    n_panel=n_panel, top_n=3,
                    constrain_z6_z8=constrained,
                    max_candidates=min(len(study_tags), 100),
                )
                if not constrained:
                    unconstrained_cache[n_panel] = (best_fp, best_cov)
                for objective, results, obj_desc in [
                    ("Best FP",       best_fp,  "ranked by lowest FP rate"),
                    ("Best coverage", best_cov, "ranked by highest coverage"),
                ]:
                    title = (f"{objective} — N={n_panel}  [{c_label}]\n"
                             f"{obj_desc} at k=N  (AND gate: bad only if all N agree)")
                    fig = _make_search_figure(
                        title, results,
                        study_tags, subrun_ids, ok_s, scored_s, kg_runs, n_panel,
                    )
                    if fig:
                        pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)

        # ── Pages 10–11: 2×2 summary pages for N=2 and N=3 unconstrained ──────
        for n_panel in [2, 3]:
            if n_panel not in unconstrained_cache:
                continue
            best_fp, best_cov = unconstrained_cache[n_panel]
            fig = _make_combined_search_figure(
                n_panel, best_fp, best_cov,
                study_tags, subrun_ids, ok_s, scored_s, kg_runs,
            )
            if fig:
                pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)

    print(f"  Saved → {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--good-run-list", type=Path,
        default=_REPO_DIR.parent / "data" / "good_run_list_TRAINING.txt",
    )
    args = parser.parse_args()

    reports_dir = _REPO_DIR / "reports" / "applyToRuns_260521"
    out_dir     = _SCRIPT_DIR / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading training runs from {args.good_run_list} ...")
    training_runs = load_training_runs(args.good_run_list)
    kg_runs       = training_runs
    print(f"  {len(kg_runs)} known-good run(s).")

    print(f"\nLoading per-subrun data from {reports_dir}/ ...")
    tags, data = load_subrun_data(reports_dir)
    if not tags:
        print("No data found — exiting."); return

    print(f"\nBuilding vote matrix ({len(tags)} models) ...")
    subrun_ids, ok_mat, scored_mat = build_matrix(tags, data)
    print(f"  Matrix shape: {ok_mat.shape}  ({ok_mat.nbytes // 1024} KB)")

    for consec1_only, suffix in [(False, "all"), (True, "consec1")]:
        n_models = (sum(1 for t in tags
                        if parse_tag(t) and parse_tag(t)["alert_consecutive_n"] == 1)
                    if consec1_only else len(tags))
        print(f"\nGenerating vote_study_260521_{suffix}.pdf  ({n_models} candidate models) ...")
        make_study_pdf(
            tags, subrun_ids, ok_mat, scored_mat,
            kg_runs, training_runs,
            consec1_only=consec1_only,
            out_path=out_dir / f"vote_study_260521_{suffix}.pdf",
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
