"""
Per-channel feature extraction from a Digitizer CSV file, optionally enriched
with trigger rate and LVDS count information from matching TriggerBoard CSVs.

A Digitizer file is in long format: each row is one (event, channel) pair.
This module aggregates all events into one feature vector per channel.

Two pseudo-channels are appended to the returned DataFrame when the
corresponding data sources are available:

  "trigger_rate" — one row holding all TriggerBoard rate / count features.
                    Digitizer and LVDS columns are NaN for this row.
  "trigger_lvds_total"    — one row holding the run-level LVDS total count.
                    Digitizer and trigger columns are NaN for this row.

Per-channel LVDS pin counts (LVDSpin) remain as a regular channel feature:
  ch 0 & 1 → LVDSpin0, ch 2 & 3 → LVDSpin1, etc.

Scalability: reads one file at a time, no global state.
"""

from __future__ import annotations

import fnmatch
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

_DIGI_COLS = [f"{m}_{s}" for m in METRIC_COLS for s in AGG_FUNCS] + ["occupancy", "frac_dead"]

# ── Per-channel LVDS feature ─────────────────────────────────────────────────

# LVDSpin: pin = channel // 2  (ch0,ch1 share pin0; ch2,ch3 share pin1; etc.)
_LVDS_PIN_COL = ["LVDSpin"]

# ── Pseudo-channel feature groups ────────────────────────────────────────────

# "trigger_rate" pseudo-channel — one row per file, independent of channels
TRIGGER_COLS = [f"triggerRate_bit{i}" for i in range(1, 14)] + [
    "triggerRate_tot",
    "triggerCounts_tot",
]

# "trigger_lvds_total" pseudo-channel — run-level LVDS sum, independent of channels
LVDS_TOTAL_COL = ["LVDStotal"]

# Index labels for pseudo-channel rows
PSEUDO_TRIGGER = "trigger_rate"
PSEUDO_LVDS    = "trigger_lvds_total"


# ── Public API ───────────────────────────────────────────────────────────────

def feature_columns(
    use_trigger: bool = True,
    use_lvds: bool = True,
    ignore_features: tuple = (),
) -> list:
    """
    Ordered list of all feature column names shared by both real channels and
    pseudo-channels. Columns irrelevant to a given row are NaN in the DataFrame.

    ignore_features : sequence of glob patterns (e.g. "TDCRollovers_*") whose
        matching columns are excluded from the returned list.
    """
    cols = list(_DIGI_COLS)
    if use_lvds:
        cols += _LVDS_PIN_COL
    if use_trigger:
        cols += TRIGGER_COLS
    if use_lvds:
        cols += LVDS_TOTAL_COL
    if ignore_features:
        cols = [
            c for c in cols
            if not any(fnmatch.fnmatch(c, pat) for pat in ignore_features)
        ]
    return cols


def extract_features(
    filepath: str,
    use_trigger: bool = True,
    use_lvds: bool = True,
    ignore_features: tuple = (),
) -> pd.DataFrame:
    """
    Read a Digitizer CSV and return a combined feature DataFrame.

    The index is mixed: integer channel IDs for real digitizer channels, then
    string labels for pseudo-channels appended at the end.

    Real channel rows
    -----------------
      {metric}_{mean|std|median}  — aggregated Digitizer metrics (33 features)
      occupancy                   — fraction of events where this channel fired
      frac_dead                   — fraction of appearances with nPulses == 0
      LVDSpin (if use_lvds)       — LVDS count for pin = channel // 2

    Pseudo-channel rows
    -------------------
      "trigger_rate" (if use_trigger):
          triggerRate_bit{1-13}, triggerRate_tot, triggerCounts_tot
          All other columns are NaN.

      "trigger_lvds_total" (if use_lvds):
          LVDStotal — sum of all LVDS pin counts for this subrun.
          All other columns are NaN.

    TriggerBoard / LVDS pseudo-channel rows have NaN values (not absent rows)
    when the matching file is not found — the reference and detector treat
    all-NaN pseudo-channels as no-data rather than anomalies.
    """
    all_cols = feature_columns(use_trigger=use_trigger, use_lvds=use_lvds,
                               ignore_features=ignore_features)
    df = pd.read_csv(filepath)

    if df.empty:
        return pd.DataFrame(columns=all_cols)

    n_events = df["event_id"].nunique()

    # ── Digitizer aggregations (real channels) ────────────────────────────────
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

    # ── Per-channel LVDS pin feature ──────────────────────────────────────────
    lvds_row = _load_lvds_row(filepath) if use_lvds else None

    if use_lvds:
        if lvds_row is not None:
            agg["LVDSpin"] = agg.index.map(
                lambda ch: lvds_row.get(f"LVDSpin{int(ch) // 2}", np.nan)
            )
        else:
            agg["LVDSpin"] = np.nan

    # Pad real channel rows with NaN for pseudo-channel-only columns
    for col in all_cols:
        if col not in agg.columns:
            agg[col] = np.nan

    frames = [agg[all_cols]]

    # ── "trigger_rate" pseudo-channel ────────────────────────────────────────
    if use_trigger:
        tb_row = _load_triggerboard_row(filepath)
        tb_vals = {col: np.nan for col in all_cols}
        if tb_row is not None:
            for col in TRIGGER_COLS:
                tb_vals[col] = tb_row.get(col, np.nan)
        frames.append(pd.DataFrame([tb_vals], index=[PSEUDO_TRIGGER]))

    # ── "trigger_lvds_total" pseudo-channel ───────────────────────────────────────────
    if use_lvds:
        lt_vals = {col: np.nan for col in all_cols}
        if lvds_row is not None:
            lt_vals["LVDStotal"] = lvds_row.get("LVDStotal", np.nan)
        frames.append(pd.DataFrame([lt_vals], index=[PSEUDO_LVDS]))

    result = pd.concat(frames)
    result.index.name = "channel"
    return result[all_cols]


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


# ── LVDS helpers ─────────────────────────────────────────────────────────────

def _find_lvds(digitizer_path: str) -> Optional[Path]:
    """
    Locate the LVDS counts CSV that corresponds to a Digitizer file.

    Naming convention:
      Digitizer_run2068_subrun1.csv  →  TriggerBoardSlab_run2068_LVDSCounts.csv
    in the same directory.
    """
    m = _DIGI_RE.search(Path(digitizer_path).name)
    if m is None:
        return None
    run = m.group(1)
    candidate = Path(digitizer_path).parent / f"TriggerBoardSlab_run{run}_LVDSCounts.csv"
    return candidate if candidate.exists() else None


def _load_lvds_row(digitizer_path: str) -> Optional[dict]:
    """
    Return a dict with keys LVDSpin0…LVDSpin49 and LVDStotal for the subrun
    matching the given Digitizer file. Returns None if the LVDSCounts file
    is absent or the subrun entry is missing.
    """
    m = _DIGI_RE.search(Path(digitizer_path).name)
    if m is None:
        return None

    subrun = int(m.group(2))
    lvds_path = _find_lvds(digitizer_path)
    if lvds_path is None:
        return None

    lvds = _read_triggerboard(lvds_path)
    if lvds.empty or "subrunnum" not in lvds.columns:
        return None

    row = lvds[lvds["subrunnum"] == subrun]
    if row.empty:
        return None

    result = {}
    for i in range(50):
        col = f"LVDSpin{i}"
        result[col] = float(row.iloc[0][col]) if col in row.columns else np.nan
    result["LVDStotal"] = float(row.iloc[0]["total"]) if "total" in row.columns else np.nan
    return result
