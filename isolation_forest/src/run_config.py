"""
Parse per-run MilliDAQ configuration files and extract features for the
isolation-forest pipeline.

Two config files exist per run under run_configs_dir:
  Run{N}TriggerDefault.py  — trigger board settings (active trigger bits,
                              prescales, channel mask, timing parameters)
  Run{N}DAQDefault.py      — digitizer settings, referencing thresholds.json
                              for per-channel trigger thresholds

The config files are Python scripts that import custom classes (TriggerBoard,
Demonstrator) and cannot be executed or imported directly.  Values are
extracted by regex-scanning for uncommented active assignments.

Supported trigger variables (includeConfigVariables_Trigger):
  triggerBoard.trigger          → cfg_trigger_bit{0..15}    (16 bool features)
  triggerBoard.prescale         → cfg_prescale_bit{0..15}   (16 float features)
                                  cfg_prescale_bit{N-1} = prescale for trigger type N
                                  (array is reversed: last element = type 1 prescale)
  triggerBoard.trigger_mask     → cfg_mask_ch{0..63}        (64 bool features)
  triggerBoard.dead_time        → cfg_dead_time              (scalar)
  triggerBoard.coincidence_time → cfg_coincidence_time       (scalar)
  triggerBoard.nLayerThreshold  → cfg_nLayerThreshold        (scalar)
  triggerBoard.nHitThreshold    → cfg_nHitThreshold          (scalar)
  triggerBoard.zero_bias        → cfg_zero_bias              (scalar)

Supported DAQ variables (includeConfigVariables_DAQ):
  channel.triggerThreshold      → cfg_daq_threshold          (per real channel)

The flat channel index used for thresholds is  digitizer * 16 + channel
(range 0..95 for 6 digitizers × 16 channels each).  Older runs without
per-channel thresholds fall back to a uniform value parsed from the DAQ file.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Optional

# ── Variable → feature name mapping ──────────────────────────────────────────

_SCALAR_TRIGGER_VARS: dict[str, str] = {
    "triggerBoard.dead_time":        "cfg_dead_time",
    "triggerBoard.coincidence_time": "cfg_coincidence_time",
    "triggerBoard.nLayerThreshold":  "cfg_nLayerThreshold",
    "triggerBoard.nHitThreshold":    "cfg_nHitThreshold",
    "triggerBoard.zero_bias":        "cfg_zero_bias",
}

DAQ_THRESHOLD_VAR = "channel.triggerThreshold"
DAQ_THRESHOLD_COL = "cfg_daq_threshold"


def trigger_config_feature_names(variables: "list | tuple") -> list[str]:
    """Ordered feature column names produced by the given trigger variables."""
    cols: list[str] = []
    for var in variables:
        if var == "triggerBoard.trigger":
            cols += [f"cfg_trigger_bit{i}" for i in range(16)]
        elif var == "triggerBoard.prescale":
            cols += [f"cfg_prescale_bit{i}" for i in range(16)]
        elif var == "triggerBoard.trigger_mask":
            cols += [f"cfg_mask_ch{c}" for c in range(64)]
        elif var in _SCALAR_TRIGGER_VARS:
            cols.append(_SCALAR_TRIGGER_VARS[var])
    return cols


def daq_config_feature_names(variables: "list | tuple") -> list[str]:
    """Per-channel DAQ feature column names for the given variables."""
    return [DAQ_THRESHOLD_COL] if DAQ_THRESHOLD_VAR in variables else []


# ── Regex-based Python config parser ─────────────────────────────────────────

def _read_active_assignment(text: str, attr: str) -> Optional[str]:
    """
    Return the RHS of the last uncommented ``attr = <value>`` assignment in
    text, or None.  Lines whose first non-whitespace character is ``#`` are
    treated as fully commented.  Inline comments after the value are stripped.
    """
    pattern = re.compile(
        r"^[ \t]*" + re.escape(attr) + r"[ \t]*=[ \t]*([^#\n]+?)[ \t]*(?:#[^\n]*)?$",
        re.MULTILINE,
    )
    result: Optional[str] = None
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = pattern.match(line)
        if m:
            result = m.group(1).strip()
    return result


def _eval_literal(s: str):
    """Safely evaluate a Python literal (int, float, list, hex 0x…, binary 0b…)."""
    try:
        return ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return None


# ── Trigger config ─────────────────────────────────────────────────────────────

def parse_trigger_config(
    run: int,
    configs_dir: str,
    variables: "list | tuple",
) -> Optional[dict[str, float]]:
    """
    Parse Run{run}TriggerDefault.py and return a flat {feature: value} dict.
    Returns None if the file does not exist or no variables could be extracted.

    Bit conventions
    ---------------
    triggerBoard.trigger  — integer, read right-to-left.  Bit 0 (rightmost) =
        trigger type 1, bit 1 = trigger type 2, …  Stored as cfg_trigger_bit{i}
        where i = trigger_type - 1.  (bits >> i) & 1 == 0 means type i+1 is off.

    triggerBoard.prescale — list ordered from the highest bit (index 0) to the
        lowest (last index, = trigger type 1).  recorded_rate = prescale * real_rate,
        so physics rate = recorded_rate / prescale.  The list is reversed before
        storage so cfg_prescale_bit{N-1} = prescale for trigger type N (matching
        cfg_trigger_bit{N-1}).  Up to 16 elements are processed.

    triggerBoard.trigger_mask — 8-byte list covering LVDS channels 0..63.
        Bit k of byte b controls channel b*8+k (1 = unmasked/active, 0 = masked).
    """
    path = Path(configs_dir) / f"Run{run}TriggerDefault.py"
    if not path.exists():
        return None

    text = path.read_text(errors="replace")
    result: dict[str, float] = {}

    for var in variables:
        rhs = _read_active_assignment(text, var)
        if rhs is None:
            continue
        val = _eval_literal(rhs)
        if val is None:
            continue

        if var == "triggerBoard.trigger":
            bits = int(val)
            for i in range(16):
                result[f"cfg_trigger_bit{i}"] = float((bits >> i) & 1)

        elif var == "triggerBoard.prescale":
            # The array is ordered from the highest trigger bit (index 0) down to
            # the lowest (last index), so it is reversed relative to the trigger
            # word bit ordering.  Reversing here makes cfg_prescale_bit{N-1} the
            # prescale for trigger type N, consistent with cfg_trigger_bit{N-1}.
            prescale_list = list(val)[:16]
            for i, p in enumerate(reversed(prescale_list)):
                result[f"cfg_prescale_bit{i}"] = float(p)

        elif var == "triggerBoard.trigger_mask":
            for byte_idx, byte_val in enumerate(list(val)[:8]):
                byte_int = int(byte_val)
                for bit_idx in range(8):
                    ch = byte_idx * 8 + bit_idx
                    result[f"cfg_mask_ch{ch}"] = float((byte_int >> bit_idx) & 1)

        elif var in _SCALAR_TRIGGER_VARS:
            result[_SCALAR_TRIGGER_VARS[var]] = float(val)

    return result or None


# ── DAQ config ────────────────────────────────────────────────────────────────

def parse_daq_thresholds(
    run: int,
    configs_dir: str,
    thresholds_json_path: str,
    variables: "list | tuple",
) -> Optional[dict[int, float]]:
    """
    Return a dict {flat_channel_index: threshold_V} for run ``run``.

    flat_channel_index = digitizer * 16 + channel  (0..95).

    Resolution order:
      1. thresholds.json (per-channel values; used by newer runs).
      2. Flat ``channel.triggerThreshold = <scalar>`` in the DAQ config file
         (older runs that did not reference thresholds.json).

    Returns None when DAQ_THRESHOLD_VAR is not in ``variables`` or no threshold
    information could be found.
    """
    if DAQ_THRESHOLD_VAR not in variables:
        return None

    json_path = Path(thresholds_json_path)
    if json_path.exists():
        with open(json_path) as fh:
            raw = json.load(fh)
        thresholds: dict[int, float] = {
            int(digi_str) * 16 + int(ch_str): float(val)
            for digi_str, channels in raw.items()
            for ch_str, val in channels.items()
        }
        if thresholds:
            return thresholds

    daq_path = Path(configs_dir) / f"Run{run}DAQDefault.py"
    if not daq_path.exists():
        return None
    text = daq_path.read_text(errors="replace")
    rhs = _read_active_assignment(text, "channel.triggerThreshold")
    if rhs is None:
        return None
    val = _eval_literal(rhs)
    if not isinstance(val, (int, float)):
        return None
    flat = float(val)
    return {digi * 16 + ch: flat for digi in range(6) for ch in range(16)}
