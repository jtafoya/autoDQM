#!/usr/bin/env python3
"""
sigma_census.py — census of low-variance (channel, feature) cells in a
trained reference (Mechanism A of the FP post-mortem, brpeng 2026.07.27).

The reference floors std at 1e-6 as a division-by-zero guard
(src/reference.py get_stats), NOT as a statistical floor: a feature that was
constant across all training subruns gets sigma = 1e-6, so any deviation at
apply time produces an astronomically large z and fires the extreme alert
(single_file_alert_max_z).  This script maps every such landmine BEFORE any
retraining, directly from reference.npz:

  constant cell        raw sigma < 1e-6           (constant in training)
  extreme landmine     sigma <= 1/z_extreme       (a UNIT jump gives z >= z_extreme;
                                                   meaningful for integer features
                                                   like nPulses_median)
  flag landmine        sigma <= 1/z_flag          (a unit jump crosses z_threshold
                                                   and marks the channel anomalous)

Usage:
    python3 _auxiliar_scripts/sigma_census.py \
        --reference models/<tag>/reference.npz \
        [--z-extreme 15] [--z-flag 8] [--out-csv sigma_census.csv]

Outputs a per-feature summary to stdout and (optionally) the full cell-level
table to CSV for use by fp_mechanism_scan.py.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd


def load_reference(path: str):
    """Return (channels, counts, means, sigmas) with the population sigma
    used by ReferenceModel.get_stats (sqrt(M2/count); NaN for count <= 1)."""
    data = np.load(path, allow_pickle=True)
    channels = [str(c) for c in data["channels"]]
    counts = np.asarray(data["counts"], dtype=float)
    means = np.asarray(data["means"], dtype=float)
    m2s = np.asarray(data["M2s"], dtype=float)
    feat_cols = [str(f) for f in data["feat_cols"]]
    with np.errstate(invalid="ignore", divide="ignore"):
        sigmas = np.sqrt(m2s / counts[:, None])
    sigmas[counts <= 1, :] = np.nan  # single-sample channels: std unestimable
    return channels, counts, means, sigmas, feat_cols


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--reference", required=True, help="path to reference.npz")
    ap.add_argument("--z-extreme", type=float, default=15.0,
                    help="extreme-alert z (single_file_alert_max_z)")
    ap.add_argument("--z-flag", type=float, default=8.0,
                    help="channel-flag z (z_threshold)")
    ap.add_argument("--out-csv", default="",
                    help="write the full cell-level table here")
    args = ap.parse_args()

    channels, counts, means, sigmas, feats = load_reference(args.reference)
    n_ch, n_ft = sigmas.shape

    cells = pd.DataFrame({
        "channel": np.repeat(channels, n_ft),
        "count":   np.repeat(counts, n_ft).astype(int),
        "feature": np.tile(feats, n_ch),
        "mean":    means.ravel(),
        "sigma":   sigmas.ravel(),
    })
    cells["constant"]         = cells.sigma < 1e-6
    cells["extreme_landmine"] = cells.sigma <= 1.0 / args.z_extreme
    cells["flag_landmine"]    = cells.sigma <= 1.0 / args.z_flag

    valid = cells.dropna(subset=["sigma"])
    print(f"reference : {args.reference}")
    print(f"cells     : {len(valid):,} (channels={n_ch}, features={n_ft}; "
          f"{cells.sigma.isna().sum()} unestimable dropped)")
    print(f"constant (sigma<1e-6)            : {int(valid.constant.sum()):,}")
    print(f"extreme landmines (sigma<=1/{args.z_extreme:g}) : {int(valid.extreme_landmine.sum()):,}")
    print(f"flag landmines    (sigma<=1/{args.z_flag:g})  : {int(valid.flag_landmine.sum()):,}")

    per_feat = (valid.groupby("feature")[["constant", "extreme_landmine", "flag_landmine"]]
                .sum().astype(int)
                .sort_values("extreme_landmine", ascending=False))
    per_feat = per_feat[per_feat.extreme_landmine > 0]
    print("\nPer-feature landmine counts (channels affected, of "
          f"{n_ch} channels; only features with extreme landmines):")
    print(per_feat.to_string())

    worst = (valid[valid.extreme_landmine]
             .groupby("channel")["feature"].count()
             .sort_values(ascending=False).head(15))
    print("\nChannels with most extreme landmines:")
    print(worst.to_string())

    if args.out_csv:
        cells.to_csv(args.out_csv, index=False)
        print(f"\nFull cell table -> {args.out_csv}")


if __name__ == "__main__":
    main()
