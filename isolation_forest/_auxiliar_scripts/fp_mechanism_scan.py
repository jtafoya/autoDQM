#!/usr/bin/env python3
"""
fp_mechanism_scan.py — decompose a known-good apply log's false positives by
alert mechanism and rescan the decision-layer parameters OFFLINE (no re-apply).

Everything here works because the apply log stores per-channel max_z and
if_score, and subrun alert status is REPLAYED from those columns at evaluate
time (src/plot._compute_persistence_status).  On a log whose subruns are all
known-good (e.g. the frozen seed42/frac40 manifest), FP rate = alerts / total.

Four analyses:

  1. Baseline replay + exclusive mechanism decomposition
     (persistent / bulk / extreme combinations, global and for the worst runs).

  2. Mechanism-A attribution (low-sigma landmines; see sigma_census.py):
       V1 "extreme defused"  — rows whose triggered features are ALL landmines
                               cannot fire the extreme rule (persistence/bulk
                               unchanged).  Isolates the sigma-explosion FPs.
       V2 "fully suppressed" — V1 + z-only landmine rows lose their anomalous
                               flag entirely (IF-flagged rows are kept).
                               Approximates a variance-floor retrain.

  3. Decision-layer parameter grid: single_file_alert_max_z x
     single_file_alert_n_channels, and alert_consecutive_n x
     file_alert_n_channels — each point is one replay over the same log.

  4. Optional z_threshold rescan (--z-rescan "8,10,12"): RAISING the channel
     z-cut offline via anomalous' = (max_z >= z') for z-only rows (IF rows
     keep their flag).  Lowering it below the apply-time value is impossible
     offline (sub-threshold per-feature z's are not logged).

Usage (from isolation_forest/):
    python3 _auxiliar_scripts/fp_mechanism_scan.py \
        --log-file  <combined apply log .csv> \
        --reference models/<tag>/reference.npz \
        [--z-extreme 15] [--bulk-n 5] [--consec 5] [--persist-n 2] \
        [--z-rescan 8,10,12] [--out-csv grid.csv]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Make src/ (pipeline) and this dir (sigma_census) importable regardless of cwd.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE))

from src.plot import _compute_persistence_status  # noqa: E402
from sigma_census import load_reference           # noqa: E402

_SPECIAL_TRIGGERS = {"missing_channel", "new_channel", ""}


def load_log(path: str) -> pd.DataFrame:
    """Load an apply log with the same dtype hardening as src/evaluate.py."""
    df = pd.read_csv(path, low_memory=False)
    df["anomalous"] = (df["anomalous"]
                       .map({True: True, False: False, "True": True, "False": False,
                             "true": True, "false": False})
                       .fillna(False).astype(bool))
    df["max_z"] = pd.to_numeric(df["max_z"], errors="coerce")
    df["if_score"] = pd.to_numeric(df["if_score"], errors="coerce")
    df["triggered_features"] = df["triggered_features"].fillna("")
    df["method"] = df["method"].fillna("")
    return df


def landmine_lookup(reference: str, z_extreme: float) -> set:
    """Set of (channel_str, feature) cells with sigma <= 1/z_extreme."""
    channels, counts, means, sigmas, feats = load_reference(reference)
    mines = set()
    thr = 1.0 / z_extreme
    for i, ch in enumerate(channels):
        for j, ft in enumerate(feats):
            s = sigmas[i, j]
            if np.isfinite(s) and s <= thr:
                mines.add((ch, ft))
    return mines


def replay(df: pd.DataFrame, persist_n: int, consec: int,
           bulk_n: int, z_extreme: float) -> pd.DataFrame:
    return _compute_persistence_status(
        df,
        file_alert_n_channels=persist_n,
        alert_consecutive_n=consec,
        single_file_alert_n_channels=bulk_n,
        single_file_alert_max_z=z_extreme,
    )


def alert_stats(status_df: pd.DataFrame, label: str) -> dict:
    n = len(status_df)
    counts = status_df.status.value_counts()
    alerts = int(counts.get("alert", 0))
    row = {"variant": label, "total": n,
           "ok": int(counts.get("ok", 0)), "warn": int(counts.get("warn", 0)),
           "pend": int(counts.get("pend", 0)), "alert": alerts,
           "fp_rate_%": round(100.0 * alerts / n, 3) if n else float("nan")}
    print(f"  {label:<38} alert={alerts:>5}  ({row['fp_rate_%']:.2f}%)"
          f"   ok={row['ok']}  warn={row['warn']}  pend={row['pend']}")
    return row


def row_is_all_landmine(row, mines: set) -> bool:
    """True if every triggered feature of this anomalous row is a landmine cell."""
    feats = [f for f in row.triggered_features.split(";") if f not in _SPECIAL_TRIGGERS]
    if not feats:
        return False
    ch = str(row.channel)
    return all((ch, f) in mines for f in feats)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--log-file", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--z-extreme", type=float, default=15.0)
    ap.add_argument("--bulk-n", type=int, default=5)
    ap.add_argument("--consec", type=int, default=5)
    ap.add_argument("--persist-n", type=int, default=2)
    ap.add_argument("--z-rescan", default="",
                    help="comma list of z_threshold values (>= apply-time value)")
    ap.add_argument("--out-csv", default="", help="write all variant rows here")
    args = ap.parse_args()

    print(f"log       : {args.log_file}")
    df = load_log(args.log_file)
    n_files = df.filename.nunique()
    print(f"rows      : {len(df):,}   subruns: {n_files:,}")
    mines = landmine_lookup(args.reference, args.z_extreme)
    print(f"landmines : {len(mines)} (channel,feature) cells with sigma <= 1/{args.z_extreme:g}\n")

    results = []

    # ── 1. Baseline + mechanism decomposition ────────────────────────────────
    print("── 1. Baseline replay ──────────────────────────────────────────")
    base = replay(df, args.persist_n, args.consec, args.bulk_n, args.z_extreme)
    results.append(alert_stats(base, "baseline"))

    anom = df[df.anomalous]
    file_max_z = anom.groupby("filename").max_z.max()
    n_anom = anom.groupby("filename").channel.nunique()
    base_idx = base.set_index("filename")
    alerted = base_idx[base_idx.status == "alert"]
    is_ext = alerted.index.map(lambda f: file_max_z.get(f, 0.0) >= args.z_extreme)
    is_blk = alerted.index.map(lambda f: n_anom.get(f, 0) >= args.bulk_n)
    is_per = (alerted.n_persistent >= args.persist_n).to_numpy()
    combo = pd.Series(
        ["+".join(k for k, v in
                  (("persistent", p), ("bulk", b), ("extreme", e)) if v) or "none"
         for p, b, e in zip(is_per, is_blk, is_ext)],
        index=alerted.index, name="mechanism")
    print("\nExclusive mechanism combinations among baseline alerts:")
    print(combo.value_counts().to_string())
    runs = alerted.assign(mech=combo).groupby("run")
    worst = runs.size().sort_values(ascending=False).head(8)
    print("\nAlerts by run (top 8):")
    for r, n in worst.items():
        mechs = runs.get_group(r).mech.value_counts().to_dict()
        print(f"  run {int(r)}: {n} alerts  {mechs}")

    # ── 2. Mechanism-A variants ──────────────────────────────────────────────
    print("\n── 2. Low-sigma (Mechanism A) variants ─────────────────────────")
    lm_mask = pd.Series(False, index=df.index)
    cand = df[df.anomalous & df.triggered_features.ne("")]
    lm_mask.loc[cand.index] = cand.apply(row_is_all_landmine, axis=1, args=(mines,))
    n_lm = int(lm_mask.sum())
    print(f"anomalous rows whose triggers are ALL landmine cells: {n_lm:,} "
          f"of {int(df.anomalous.sum()):,}")
    feat_hits = (df.loc[lm_mask, "triggered_features"].str.split(";").explode()
                 .value_counts().head(10))
    print("their triggered features (top 10):")
    print(feat_hits.to_string())

    v1 = df.copy()  # defuse extreme: landmine rows cannot reach z_extreme
    v1.loc[lm_mask, "max_z"] = np.minimum(
        v1.loc[lm_mask, "max_z"], args.z_extreme - 1e-9)
    results.append(alert_stats(
        replay(v1, args.persist_n, args.consec, args.bulk_n, args.z_extreme),
        "V1 extreme-defused (landmines)"))

    v2 = v1.copy()  # variance-floor approximation: z-only landmine rows unflagged
    v2.loc[lm_mask & df.method.eq("statistical"), "anomalous"] = False
    results.append(alert_stats(
        replay(v2, args.persist_n, args.consec, args.bulk_n, args.z_extreme),
        "V2 fully-suppressed (z-only landmines)"))

    # ── 3. Decision-layer parameter grid ─────────────────────────────────────
    print("\n── 3. Single-file rules scan (persistence fixed at baseline) ───")
    for z_ext in (0.0, 12.0, 15.0, 20.0, 30.0):
        for blk in (0, 5, 8):
            lbl = f"extreme={z_ext:g} bulk={blk}"
            results.append(alert_stats(
                replay(df, args.persist_n, args.consec, blk, z_ext), lbl))

    print("\n── 3b. Persistence scan (single-file rules fixed at baseline) ──")
    for consec in (3, 5, 7):
        for pn in (2, 3):
            lbl = f"consec={consec} persist_n={pn}"
            results.append(alert_stats(
                replay(df, pn, consec, args.bulk_n, args.z_extreme), lbl))

    # ── 4. Optional z_threshold rescan (raising only) ────────────────────────
    if args.z_rescan:
        print("\n── 4. z_threshold rescan (z-only rows re-cut on max_z) ─────────")
        for z in [float(x) for x in args.z_rescan.split(",")]:
            vz = df.copy()
            zonly = vz.method.eq("statistical")
            vz.loc[zonly & (vz.max_z < z), "anomalous"] = False
            results.append(alert_stats(
                replay(vz, args.persist_n, args.consec, args.bulk_n,
                       args.z_extreme), f"z_threshold={z:g}"))

    if args.out_csv:
        pd.DataFrame(results).to_csv(args.out_csv, index=False)
        print(f"\nAll variants -> {args.out_csv}")


if __name__ == "__main__":
    main()
