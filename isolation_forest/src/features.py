"""
Per-channel feature extraction from a Digitizer CSV file.

A file is in long format: each row is one (event, channel) pair.
This module aggregates all events in a file into one feature vector per channel.

Scalability: reads one file at a time, no global state.
"""

import numpy as np
import pandas as pd

# Numeric columns present in every Digitizer CSV
METRIC_COLS = [
    "sideband_mean", "sideband_rms", "nPulses",
    "pulseHeight_max", "pulseHeight_min",
    "pulseArea_max", "pulseArea_min",
    "pulseDuriation_max", "pulseDuriation_min",
    "TDC", "TDCRollovers",
]

AGG_FUNCS = ["mean", "std", "median"]


def feature_columns() -> list:
    """Ordered list of feature column names produced by extract_features()."""
    cols = [f"{m}_{s}" for m in METRIC_COLS for s in AGG_FUNCS]
    cols += ["occupancy", "frac_dead"]
    return cols


def extract_features(filepath: str) -> pd.DataFrame:
    """
    Read a Digitizer CSV and return a per-channel feature DataFrame.

    Each row in the output represents one channel. Columns are aggregated
    statistics of all events in the file for that channel.

    Extra columns added beyond raw metric aggregations:
      - occupancy : fraction of total events in which this channel appeared
      - frac_dead : fraction of those appearances where nPulses == 0
    """
    df = pd.read_csv(filepath)

    n_events = df["event_id"].nunique()

    # Aggregate per channel — mean / std / median of each metric
    agg = df.groupby("channel")[METRIC_COLS].agg(AGG_FUNCS)
    agg.columns = [f"{m}_{s}" for m, s in agg.columns]

    # Channel occupancy: how often it fires relative to total events
    channel_event_counts = df.groupby("channel")["event_id"].nunique()
    agg["occupancy"] = channel_event_counts / n_events

    # Dead-channel indicator: fraction of appearances with zero pulses
    dead_counts = (
        df[df["nPulses"] == 0]
        .groupby("channel")["event_id"]
        .nunique()
    )
    agg["frac_dead"] = (dead_counts / channel_event_counts).fillna(0.0)

    # std is NaN when a channel appears only once — replace with 0
    agg = agg.fillna(0.0)

    # Ensure column order matches feature_columns()
    return agg[feature_columns()]
