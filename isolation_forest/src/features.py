"""
Per-channel feature extraction from a Digitizer CSV file, optionally enriched
with trigger rate and LVDS count information from matching TriggerBoard CSVs,
and with config-driven normalisations derived from MilliDAQ Python config files.

A Digitizer file is in long format: each row is one (event, channel) pair.
This module aggregates all events into one feature vector per channel.

Two pseudo-channels are appended when the corresponding data sources are available:

  "trigger_rate"       — TriggerBoard rate / count features per subrun.
  "trigger_lvds_total" — run-level LVDS total count.

Per-channel LVDS pin counts (LVDSpin) remain as a regular channel feature:
  ch 0 & 1 → LVDSpin0, ch 2 & 3 → LVDSpin1, etc.

Config-driven normalisations (applied when include_trigger_config=True)
-----------------------------------------------------------------------
Config variables are used only to transform existing observable features.
They are never added to the feature vector and are never scored.

  triggerBoard.prescale (if in trigger_config_vars):
      recorded_rate = prescale * real_rate, so the physics rate is recovered as
      triggerRate_bit{N} = recorded_rate / prescale[N-1].  The prescale list is
      stored reversed: cfg_prescale_bit{N-1} is the prescale for trigger type N
      (last element of the config array = prescale for type 1).  Runs with
      different prescale settings become directly comparable.  triggerRate_tot
      and triggerCounts_tot are left unnormalised (mixed trigger types, no single
      prescale applies).  Zero prescale produces NaN (type was off).

  triggerBoard.trigger (if in trigger_config_vars):
      The trigger word is read right-to-left: bit 0 (rightmost) = trigger type 1,
      bit 1 = trigger type 2, …  triggerRate_bit{N} is set to NaN for any trigger
      type N whose bit is 0 (disabled).  A zero rate from a disabled trigger is
      expected — it should not enter the reference statistics or anomaly score.
      Up to 16 trigger types (bits 0–15) are supported.

  triggerBoard.trigger_mask (if in trigger_config_vars):
      Each LVDS pin p maps to digitizer channels 2p and 2p+1.  When pin p is
      masked (bit = 0), all features for channels 2p and 2p+1 are set to NaN.
      Masked channels have no expected trigger activity; NaN features are
      transparently skipped by the Welford reference and produce NaN z-scores
      that do not contribute to anomaly detection.

Scalability: reads one file at a time, no global state.
"""

from __future__ import annotations

import fnmatch
import re
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

from .run_config import parse_trigger_config

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
TRIGGER_COLS = [f"triggerRate_bit{i}" for i in range(1, 17)] + [
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
    Ordered list of all feature column names shared by real channels and
    pseudo-channels.  Columns irrelevant to a given row are NaN in the DataFrame.

    Config normalisations (include_trigger_config, etc.) transform the *values*
    of these columns but never add new columns — the feature space is identical
    regardless of whether config-based normalisation is active.

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
    include_trigger_config: bool = False,
    trigger_config_vars: tuple = (),
    include_daq_config: bool = False,
    daq_config_vars: tuple = (),
    run_configs_dir: str = "",
    thresholds_json_path: str = "",
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
          LVDStotal — run-level sum of all LVDS pin counts.
          All other columns are NaN.

    Config-driven normalisations (when include_trigger_config=True)
    ---------------------------------------------------------------
    Config variables are used to transform observable features in-place.
    No new columns are added; the feature space is the same as without config.

      triggerBoard.prescale → prescale-normalised trigger rates (physics rate).
      triggerBoard.trigger  → NaN for disabled trigger types.
      triggerBoard.trigger_mask → NaN all features for channels whose LVDS pin
          is masked (pin p = channel // 2; masked pin → channels 2p, 2p+1).

    include_daq_config is accepted for API consistency and tag-suffix logic but
    currently applies no transformation (no analytical normalisation available
    for per-channel thresholds without the full pulse-height spectrum).

    Missing data sources (absent TriggerBoard file, absent config file) produce
    NaN values — treated as no-data, not as anomalies.
    """
    all_cols = feature_columns(
        use_trigger=use_trigger,
        use_lvds=use_lvds,
        ignore_features=ignore_features,
    )
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

    # ── Config-driven normalisations ──────────────────────────────────────────
    # Parse the trigger config once; derive all normalisation lookups from it.
    # When include_trigger_config=False, trig_cfg_feats stays None and every
    # downstream block is a no-op — behaviour is identical to the pre-config path.
    trig_cfg_feats = None
    if include_trigger_config and run_configs_dir:
        run_m = _DIGI_RE.search(Path(filepath).name)
        run_num = int(run_m.group(1)) if run_m else None
        if run_num is not None:
            trig_cfg_feats = parse_trigger_config(
                run_num, run_configs_dir, list(trigger_config_vars)
            )

    # Prescale lookup: triggerRate_bit{N} (1-indexed) → prescale[N-1].
    _prescales: "list | None" = None
    if trig_cfg_feats is not None and "triggerBoard.prescale" in trigger_config_vars:
        _prescales = [
            trig_cfg_feats.get(f"cfg_prescale_bit{i}", np.nan)
            for i in range(16)
        ]

    # Disabled trigger types: bit i of trigger word = 0 → trigger type i+1 inactive.
    # triggerRate_bit{N} for N in _disabled_triggers is set to NaN (expected zero rate
    # from an inactive trigger should not enter the reference or anomaly score).
    _disabled_triggers: set = set()
    if trig_cfg_feats is not None and "triggerBoard.trigger" in trigger_config_vars:
        for i in range(16):  # TRIGGER_COLS covers types 1..16 (bits 0..15)
            if trig_cfg_feats.get(f"cfg_trigger_bit{i}", 1.0) == 0.0:
                _disabled_triggers.add(i + 1)

    # LVDS trigger-mask: pin p = channel // 2; masked pin → NaN all features for
    # channels 2p and 2p+1.  Pins 0..47 cover digitizer channels 0..95.
    # Pins 48..63 map to non-digitizer components (panels, etc.) and are ignored.
    if trig_cfg_feats is not None and "triggerBoard.trigger_mask" in trigger_config_vars:
        masked_channels = [
            ch
            for p in range(48)
            if trig_cfg_feats.get(f"cfg_mask_ch{p}", 1.0) == 0.0
            for ch in (2 * p, 2 * p + 1)
            if ch in agg.index
        ]
        if masked_channels:
            agg.loc[masked_channels, :] = np.nan

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
                val = tb_row.get(col, np.nan)
                if col.startswith("triggerRate_bit"):
                    bit_num = int(col[len("triggerRate_bit"):])
                    # Disabled trigger → NaN (expected zero; not an anomaly).
                    if bit_num in _disabled_triggers:
                        val = np.nan
                    # Prescale-normalise: recorded = prescale * real, so real = recorded / prescale.
                    # cfg_prescale_bit{N-1} holds the prescale for trigger type N (list reversed at parse).
                    elif _prescales is not None:
                        p = _prescales[bit_num - 1] if bit_num <= len(_prescales) else np.nan
                        val = (val / p) if (not np.isnan(p) and p > 0) else np.nan
                tb_vals[col] = val
        frames.append(pd.DataFrame([tb_vals], index=[PSEUDO_TRIGGER]))

    # ── "trigger_lvds_total" pseudo-channel ───────────────────────────────────
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
