"""
Per-channel feature extraction from a Digitizer CSV file, optionally enriched
with trigger rate information from the matching TriggerBoard CSV.

A Digitizer file is in long format: each row is one (event, channel) pair.
This module aggregates all events into one feature vector per channel.

TriggerBoard features are file-level constants (one value per subrun), appended
as additional columns to every channel row so the existing reference model and
detector can handle them without any architectural changes.

Scalability: reads one file at a time, no global state.
"""

from __future__ import annotations

import re
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

# ── Digitizer metrics ───────────────────────────────────────────────────────

METRIC_COLS = [
    "sideband_mean", "sideband_rms", "nPulses",
    "pulseHeight_max", "pulseHeight_min",
    "pulseArea_max", "pulseArea_min",
    "pulseDuriation_max", "pulseDuriation_min",
    "TDC", "TDCRollovers",
]

AGG_FUNCS = ["mean", "std", "median"]

# ── TriggerBoard features ────────────────────────────────────────────────────

# Per-bit rates (Hz) + global rate + global counts
TRIGGER_COLS = [f"triggerRate_bit{i}" for i in range(1, 14)] + [
    "triggerRate_tot",
    "triggerCounts_tot",
]


# ── Public API ───────────────────────────────────────────────────────────────

def feature_columns() -> list:
    """Ordered list of all feature column names produced by extract_features()."""
    cols  = [f"{m}_{s}" for m in METRIC_COLS for s in AGG_FUNCS]
    cols += ["occupancy", "frac_dead"]
    cols += TRIGGER_COLS
    return cols


def extract_features(filepath: str) -> pd.DataFrame:
    """
    Read a Digitizer CSV and return a per-channel feature DataFrame.

    Columns:
      {metric}_{mean|std|median}  — aggregated Digitizer metrics (33 features)
      occupancy                   — fraction of events where this channel fired
      frac_dead                   — fraction of appearances with nPulses == 0
      triggerRate_bit{1-13}       — per-bit trigger rate in Hz (from TriggerBoard)
      triggerRate_tot             — total trigger rate in Hz
      triggerCounts_tot           — total trigger count for this subrun

    TriggerBoard features are NaN if the matching TriggerBoard file is not found
    or the subrun entry is missing.
    """
    df = pd.read_csv(filepath)

    if df.empty:
        return pd.DataFrame(columns=feature_columns())

    n_events = df["event_id"].nunique()

    # ── Digitizer aggregations ────────────────────────────────────────────────
    agg = df.groupby("channel")[METRIC_COLS].agg(AGG_FUNCS)
    agg.columns = [f"{m}_{s}" for m, s in agg.columns]

    channel_event_counts = df.groupby("channel")["event_id"].nunique()
    agg["occupancy"] = channel_event_counts / n_events

    dead_counts = (
        df[df["nPulses"] == 0]
        .groupby("channel")["event_id"]
        .nunique()
    )
    agg["frac_dead"] = (dead_counts / channel_event_counts).fillna(0.0)

    agg = agg.fillna(0.0)

    # ── TriggerBoard features ─────────────────────────────────────────────────
    tb_row = _load_triggerboard_row(filepath)   # dict or None
    for col in TRIGGER_COLS:
        agg[col] = tb_row[col] if tb_row is not None else np.nan

    return agg[feature_columns()]


# ── TriggerBoard helpers ─────────────────────────────────────────────────────

_DIGI_RE = re.compile(r"Digitizer_run(\d+)_subrun(\d+)", re.IGNORECASE)


def _find_triggerboard(digitizer_path: str) -> Optional[Path]:
    """
    Locate the TriggerBoard CSV that corresponds to a Digitizer file.

    Naming convention:
      Digitizer_run2068_subrun1.csv  →  TriggerBoard_run2068.csv
    in the same directory.
    """
    m = _DIGI_RE.search(Path(digitizer_path).name)
    if m is None:
        return None
    run = m.group(1)
    candidate = Path(digitizer_path).parent / f"TriggerBoard_run{run}.csv"
    return candidate if candidate.exists() else None


def _read_triggerboard(path: Path) -> pd.DataFrame:
    """
    Parse a TriggerBoard CSV, skipping the repeated header lines.
    Returns a DataFrame with one row per subrun, numeric columns.
    """
    rows = []
    header = None
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith("subrunnum"):
                header = [c.strip() for c in line.split(",")]
            elif header is not None:
                vals = [v.strip() for v in line.split(",")]
                rows.append(dict(zip(header, vals)))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).apply(pd.to_numeric, errors="coerce")
    return df


def _load_triggerboard_row(digitizer_path: str) -> Optional[dict]:
    """
    Return a dict of TRIGGER_COLS values for the subrun matching the
    given Digitizer file. Returns None if the TriggerBoard file is absent
    or the subrun is not found.
    """
    m = _DIGI_RE.search(Path(digitizer_path).name)
    if m is None:
        return None

    subrun = int(m.group(2))
    tb_path = _find_triggerboard(digitizer_path)
    if tb_path is None:
        return None

    tb = _read_triggerboard(tb_path)
    if tb.empty or "subrunnum" not in tb.columns:
        return None

    row = tb[tb["subrunnum"] == subrun]
    if row.empty:
        return None

    result = {}
    for col in TRIGGER_COLS:
        result[col] = float(row.iloc[0][col]) if col in row.columns else np.nan
    return result
