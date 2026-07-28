#!/usr/bin/env python3
"""Supplement run-2014 diagnosis with channel-level alert-driver attribution."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO = Path("/afs/cern.ch/user/p/pengy/autoDQM")
IF_DIR = REPO / "isolation_forest"
TAG = (
    "juan_reproduction_digi_z8_if0001_train20_seed42"
    "_noTrigger_noLVDS_ignoreTriggerConfig"
)
LOG = IF_DIR / "logs" / f"{TAG}.csv"
STEP1 = (
    IF_DIR
    / "analysis"
    / "juan_bad_run_diagnosis"
    / "step1_classification"
    / "subrun_classification.csv"
)
OUT = (
    IF_DIR
    / "analysis"
    / "juan_bad_run_diagnosis"
    / "run2014"
)


def fail(message: str) -> "None":
    raise RuntimeError(f"SANITY CHECK FAILED: {message}")


def as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    normalized = series.astype(str).str.strip().str.lower()
    if not normalized.isin(["true", "false"]).all():
        fail("invalid boolean values")
    return normalized.eq("true")


def main() -> None:
    channel_output = OUT / "run2014_alert_driver_channel_summary.csv"
    feature_output = OUT / "run2014_extreme_feature_summary.csv"
    plot_output = OUT / "run2014_extreme_driver_channels.png"
    for path in [channel_output, feature_output, plot_output]:
        if path.exists():
            fail(f"refusing to overwrite {path}")

    timeline = pd.read_csv(STEP1).query("run == 2014").copy()
    if (
        len(timeline) != 361
        or int(timeline["strict_status"].eq("ALERT").sum()) != 71
    ):
        fail("Step-1 run-2014 counts do not match 361/71")
    for column in ["persistent_alert", "bulk_alert", "extreme_alert"]:
        timeline[column] = as_bool(timeline[column])

    log = pd.read_csv(LOG)
    log = log[log["filename"].isin(timeline["filename"])].copy()
    log["anomalous"] = as_bool(log["anomalous"])
    joined = log.merge(
        timeline[
            [
                "filename",
                "strict_status",
                "persistent_alert",
                "bulk_alert",
                "extreme_alert",
            ]
        ],
        on="filename",
        how="left",
        validate="many_to_one",
    )
    alert_anomalous = joined[
        joined["anomalous"] & joined["strict_status"].eq("ALERT")
    ].copy()

    persistent_occurrences: dict[int, int] = {}
    for value in timeline.loc[
        timeline["persistent_alert"], "persistent_channels"
    ].fillna(""):
        for channel in str(value).split(";"):
            if channel.strip():
                key = int(channel)
                persistent_occurrences[key] = (
                    persistent_occurrences.get(key, 0) + 1
                )

    rows = []
    for channel in sorted(log["channel"].unique()):
        channel_alert = alert_anomalous[
            alert_anomalous["channel"] == channel
        ]
        extreme_rows = channel_alert[channel_alert["max_z"] >= 15]
        rows.append(
            {
                "channel": channel,
                "n_ALERT_subruns_anomalous": int(
                    channel_alert["filename"].nunique()
                ),
                "n_extreme_ALERT_subruns_triggered": int(
                    extreme_rows["filename"].nunique()
                ),
                "n_persistent_ALERT_subruns_as_persistent": int(
                    persistent_occurrences.get(int(channel), 0)
                ),
                "n_bulk_ALERT_subruns_participating": int(
                    channel_alert.loc[
                        channel_alert["bulk_alert"], "filename"
                    ].nunique()
                ),
                "n_bulk_only_ALERT_subruns_participating": int(
                    channel_alert.loc[
                        channel_alert["bulk_alert"]
                        & ~channel_alert["extreme_alert"]
                        & ~channel_alert["persistent_alert"],
                        "filename",
                    ].nunique()
                ),
                "maximum_max_z_in_ALERT_subruns": float(
                    channel_alert["max_z"].max()
                )
                if not channel_alert.empty
                else np.nan,
                "extreme_methods": ";".join(
                    sorted(extreme_rows["method"].dropna().unique())
                ),
            }
        )
    driver_df = pd.DataFrame(rows).sort_values(
        [
            "n_extreme_ALERT_subruns_triggered",
            "n_persistent_ALERT_subruns_as_persistent",
            "n_bulk_only_ALERT_subruns_participating",
            "n_ALERT_subruns_anomalous",
            "channel",
        ],
        ascending=[False, False, False, False, True],
    )
    driver_df.insert(0, "alert_driver_rank", range(1, len(driver_df) + 1))

    extreme_rows = alert_anomalous[alert_anomalous["max_z"] >= 15].copy()
    if extreme_rows["filename"].nunique() != 48:
        fail(
            "extreme-row attribution does not cover exactly 48 extreme ALERTs"
        )
    feature_records = []
    for row in extreme_rows.itertuples(index=False):
        raw = (
            ""
            if pd.isna(row.triggered_features)
            else str(row.triggered_features)
        )
        features = [item.strip() for item in raw.split(";") if item.strip()]
        if not features:
            features = ["<none>"]
        for feature in dict.fromkeys(features):
            feature_records.append(
                {
                    "triggered_feature": feature,
                    "channel": row.channel,
                    "filename": row.filename,
                    "method": row.method,
                }
            )
    feature_long = pd.DataFrame(feature_records)
    feature_df = (
        feature_long.groupby("triggered_feature")
        .agg(
            n_extreme_channel_rows=("filename", "count"),
            n_unique_extreme_ALERT_subruns=("filename", "nunique"),
            n_unique_channels=("channel", "nunique"),
            channels=("channel", lambda values: ";".join(
                str(value) for value in sorted(set(values))
            )),
            methods=("method", lambda values: ";".join(
                sorted(set(values.dropna()))
            )),
        )
        .reset_index()
        .sort_values(
            ["n_extreme_channel_rows", "n_unique_extreme_ALERT_subruns"],
            ascending=False,
        )
    )

    driver_df.to_csv(channel_output, index=False)
    feature_df.to_csv(feature_output, index=False)

    active = driver_df[
        driver_df["n_extreme_ALERT_subruns_triggered"] > 0
    ].sort_values(
        ["n_extreme_ALERT_subruns_triggered", "maximum_max_z_in_ALERT_subruns"]
    )
    plt.figure(figsize=(12, 7))
    bars = plt.barh(
        active["channel"].astype(str).to_numpy(),
        active["n_extreme_ALERT_subruns_triggered"].to_numpy(),
        color="#c44e52",
    )
    plt.bar_label(bars, fmt="%d", padding=3)
    plt.xlabel("Extreme ALERT subruns triggered (max_z ≥ 15)")
    plt.ylabel("Channel")
    plt.title("Run 2014 channels directly triggering the extreme-z condition")
    plt.savefig(plot_output, dpi=180, bbox_inches="tight")
    plt.close()

    print("Alert-driver attribution complete.")
    print("\nTop driver channels:")
    print(driver_df.head(25).to_string(index=False))
    print("\nExtreme features:")
    print(feature_df.to_string(index=False))


if __name__ == "__main__":
    main()
