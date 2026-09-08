"""Compact detector/DAQ context builders for the contextual Novel Test.

Only detector telemetry, frozen campaign bookkeeping, and MilliDAQ configuration
files are read here.  No eLog, human diagnosis, or benchmark ground truth is an
input to this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.features import _N_SIGNAL_LVDS_PINS, _read_triggerboard
from src.run_config import parse_daq_thresholds, parse_trigger_config


TRIGGER_VARIABLES = (
    "triggerBoard.trigger",
    "triggerBoard.prescale",
    "triggerBoard.trigger_mask",
    "triggerBoard.dead_time",
    "triggerBoard.coincidence_time",
    "triggerBoard.nLayerThreshold",
    "triggerBoard.nHitThreshold",
    "triggerBoard.zero_bias",
)
DAQ_VARIABLES = ("channel.triggerThreshold",)
MAX_SECTION_CHARS = 3500


@dataclass(frozen=True)
class ContextBundle:
    trigger_summary: str
    lvds_summary: str
    daq_config_summary: str
    availability: dict[str, bool]
    source_paths: dict[str, list[str]]
    source_types: dict[str, str]


def _fmt(value: float) -> str:
    if not np.isfinite(value):
        return "unavailable"
    magnitude = abs(float(value))
    if magnitude >= 10000 or (0 < magnitude < 0.001):
        return f"{value:.3g}"
    return f"{value:.4g}"


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").dropna()


def _ordered_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if "subrunnum" not in frame.columns:
        return frame
    result = frame.copy()
    result["subrunnum"] = pd.to_numeric(result["subrunnum"], errors="coerce")
    return result.dropna(subset=["subrunnum"]).sort_values("subrunnum")


def _series_line(frame: pd.DataFrame, column: str, label: str) -> tuple[str, dict[str, Any]]:
    if column not in frame.columns:
        return f"- {label}: unavailable", {"available": False}
    ordered = _ordered_frame(frame)
    values = pd.to_numeric(ordered[column], errors="coerce")
    valid = values.dropna()
    if valid.empty:
        return f"- {label}: unavailable", {"available": False}
    stats: dict[str, Any] = {
        "available": True,
        "median": float(valid.median()),
        "min": float(valid.min()),
        "max": float(valid.max()),
    }
    line = (
        f"- {label}: median {_fmt(stats['median'])}, range "
        f"{_fmt(stats['min'])} to {_fmt(stats['max'])}."
    )
    if len(valid) >= 2:
        aligned = ordered.loc[valid.index]
        array = valid.to_numpy(dtype=float)
        scale = max(abs(float(np.median(array))), 1e-12)
        relative_steps = np.abs(np.diff(array)) / np.maximum(np.abs(array[:-1]), scale * 0.05)
        step_index = int(np.argmax(relative_steps))
        step_ratio = float(relative_steps[step_index])
        transition_subrun = int(aligned.iloc[step_index + 1]["subrunnum"])
        stats.update(
            largest_relative_step=step_ratio,
            transition_subrun=transition_subrun,
        )
        spread = float((np.nanpercentile(array, 95) - np.nanpercentile(array, 5)) / scale)
        if step_ratio >= 0.5:
            behavior = f"large transition near subrun {transition_subrun}"
        elif spread >= 1.0:
            behavior = "strongly variable/intermittent"
        elif spread >= 0.25:
            behavior = "moderately variable"
        else:
            behavior = "stable/persistent"
        stats["behavior"] = behavior
        line += f" Temporal behavior: {behavior}"
        if step_ratio >= 0.2:
            line += f" (largest adjacent relative change {_fmt(step_ratio)})."
        else:
            line += "."
    return line, stats


def _subrun_coverage(frame: pd.DataFrame) -> str:
    if frame.empty or "subrunnum" not in frame.columns:
        return "unavailable"
    subruns = _numeric(frame["subrunnum"])
    if subruns.empty:
        return "unavailable"
    return f"{len(subruns)} rows spanning subruns {int(subruns.min())}-{int(subruns.max())}"


def _bounded(lines: list[str]) -> str:
    text = "\n".join(lines)
    if len(text) > MAX_SECTION_CHARS:
        return text[: MAX_SECTION_CHARS - 32].rstrip() + "\n- Summary truncated safely."
    return text


def build_trigger_summary(
    frame: pd.DataFrame | None,
    trigger_config: dict[str, float] | None = None,
) -> str:
    if frame is None or frame.empty:
        return "Trigger context: unavailable"
    frame = _ordered_frame(frame)
    lines = [f"- Coverage: {_subrun_coverage(frame)}."]
    total_line, _ = _series_line(frame, "triggerRate_tot", "Total trigger rate")
    count_line, _ = _series_line(frame, "triggerCounts_tot", "Total trigger counts")
    lines.extend([total_line, count_line])

    bit_rows: list[tuple[int, float, float, float]] = []
    available_bit_medians: list[tuple[int, float]] = []
    for bit in range(1, 17):
        column = f"triggerRate_bit{bit}"
        if column not in frame.columns:
            continue
        values = _numeric(frame[column])
        if values.empty:
            continue
        median = float(values.median())
        available_bit_medians.append((bit, median))
        if float(values.max()) <= 0:
            continue
        scale = max(abs(median), 1e-12)
        variability = float((values.quantile(0.95) - values.quantile(0.05)) / scale)
        nonzero_fraction = float((values > 0).mean())
        bit_rows.append((bit, median, variability, nonzero_fraction))
    bit_rows.sort(key=lambda item: item[1], reverse=True)
    if available_bit_medians:
        lines.append(
            "- Per-bit recorded rate medians: "
            + ", ".join(f"bit{bit}={_fmt(median)}" for bit, median in available_bit_medians)
            + "."
        )
    else:
        lines.append("- Per-bit recorded rates: unavailable.")
    if bit_rows:
        dominant = ", ".join(
            f"bit{bit} median={_fmt(median)}" for bit, median, _, _ in bit_rows[:6]
        )
        lines.append(f"- Dominant nonzero trigger bits: {dominant}.")
        abnormal = [row for row in bit_rows if row[2] >= 1.0 or row[3] < 0.8]
        if abnormal:
            lines.append(
                "- Variable/intermittent trigger bits: "
                + ", ".join(
                    f"bit{bit} variability={_fmt(var)}, nonzero_fraction={_fmt(frac)}"
                    for bit, _, var, frac in abnormal[:6]
                )
                + "."
            )
        else:
            lines.append("- Variable/intermittent trigger bits: none detected by compact summary.")
    else:
        lines.append("- Dominant/abnormal trigger bits: no nonzero bit-rate telemetry.")

    if trigger_config:
        normalized: list[str] = []
        for bit, median, _, _ in bit_rows:
            enabled = trigger_config.get(f"cfg_trigger_bit{bit - 1}", 1.0) != 0.0
            prescale = trigger_config.get(f"cfg_prescale_bit{bit - 1}")
            if enabled and prescale is not None and np.isfinite(prescale) and prescale > 0:
                normalized.append(
                    f"bit{bit} recorded={_fmt(median)}, prescale={_fmt(prescale)}, "
                    f"physical~{_fmt(median / prescale)}"
                )
        if normalized:
            lines.append("- Prescale interpretation (median rates): " + "; ".join(normalized[:6]) + ".")
        else:
            lines.append("- Prescale-normalized interpretation: unavailable.")
    else:
        lines.append("- Prescale-normalized interpretation: unavailable.")
    lines.append(
        "- Digitizer-vs-trigger-board rate consistency: unavailable; no compact processed "
        "digitizer-rate telemetry was used."
    )
    return _bounded(lines)


def _pin_channel_mapping(pin: int) -> str:
    return f"pin{pin}->channels {2 * pin}/{2 * pin + 1}"


def build_lvds_summary(frame: pd.DataFrame | None) -> str:
    if frame is None or frame.empty:
        return "LVDS context: unavailable"
    frame = _ordered_frame(frame)
    lines = [f"- Coverage: {_subrun_coverage(frame)}."]
    total_column = "total" if "total" in frame.columns else "LVDStotal"
    total_line, _ = _series_line(frame, total_column, "Total LVDS counts")
    lines.append(total_line)

    pin_columns = [
        f"LVDSpin{pin}" for pin in range(_N_SIGNAL_LVDS_PINS) if f"LVDSpin{pin}" in frame.columns
    ]
    if not pin_columns:
        lines.append("- LVDS pin counts: unavailable.")
        return _bounded(lines)
    pins = frame[pin_columns].apply(pd.to_numeric, errors="coerce")
    row_medians = pins.where(pins > 0).median(axis=1)
    pin_medians = [
        (int(column.removeprefix("LVDSpin")), float(_numeric(pins[column]).median()))
        for column in pin_columns
        if not _numeric(pins[column]).empty
    ]
    if pin_medians:
        lines.append(
            "- Signal-pin median counts: "
            + ", ".join(f"pin{pin}={_fmt(value)}" for pin, value in pin_medians)
            + "."
        )
    persistent_zero: list[int] = []
    persistent_missing: list[int] = []
    persistent_low: list[int] = []
    persistent_high: list[int] = []
    transition_pins: list[tuple[int, float, int]] = []
    for pin, column in enumerate(pin_columns):
        values = pins[column]
        present = values.dropna()
        if float(values.isna().mean()) >= 0.5:
            persistent_missing.append(pin)
        if not present.empty and float((present == 0).mean()) >= 0.8:
            persistent_zero.append(pin)
        valid_scale = row_medians.notna() & values.notna()
        if valid_scale.any():
            ratios = values[valid_scale] / row_medians[valid_scale]
            if float((ratios <= 0.1).mean()) >= 0.8:
                persistent_low.append(pin)
            if float((ratios >= 3.0).mean()) >= 0.8:
                persistent_high.append(pin)
        ordered_values = values.dropna()
        if len(ordered_values) >= 2:
            array = ordered_values.to_numpy(dtype=float)
            scale = max(abs(float(np.median(array))), 1.0)
            steps = np.abs(np.diff(array)) / np.maximum(np.abs(array[:-1]), scale * 0.05)
            idx = int(np.argmax(steps))
            if float(steps[idx]) >= 2.0:
                subrun = int(frame.loc[ordered_values.index[idx + 1], "subrunnum"])
                transition_pins.append((pin, float(steps[idx]), subrun))

    def mapped(values: list[int]) -> str:
        return ", ".join(_pin_channel_mapping(pin) for pin in values[:8]) or "none"

    lines.append(f"- Persistent zero signal pins: {mapped(persistent_zero)}.")
    lines.append(f"- Persistent missing signal pins: {mapped(persistent_missing)}.")
    lines.append(f"- Persistently abnormally low signal pins: {mapped(persistent_low)}.")
    lines.append(f"- Persistently abnormally high signal pins: {mapped(persistent_high)}.")
    if transition_pins:
        transition_pins.sort(key=lambda item: item[1], reverse=True)
        lines.append(
            "- Strongest pin transitions: "
            + ", ".join(
                f"{_pin_channel_mapping(pin)} near subrun {subrun} (relative change {_fmt(step)})"
                for pin, step, subrun in transition_pins[:6]
            )
            + "."
        )
    else:
        lines.append("- Strong pin-level temporal transitions: none detected by compact summary.")
    lines.append(
        f"- Mapping basis: repository mapping for {_N_SIGNAL_LVDS_PINS} signal pins; "
        "non-signal LVDS columns are omitted from abnormal-pin classification."
    )
    return _bounded(lines)


def build_daq_config_summary(
    trigger_config: dict[str, float] | None,
    daq_thresholds: dict[int, float] | None,
) -> str:
    if not trigger_config and not daq_thresholds:
        return "DAQ/config context: unavailable"
    lines: list[str] = []
    if trigger_config:
        enabled = [bit + 1 for bit in range(16) if trigger_config.get(f"cfg_trigger_bit{bit}") == 1.0]
        disabled = [bit + 1 for bit in range(16) if trigger_config.get(f"cfg_trigger_bit{bit}") == 0.0]
        lines.append(f"- Enabled trigger paths: {enabled if enabled else 'none reported'}.")
        lines.append(f"- Disabled trigger paths: {disabled if disabled else 'none reported'}.")
        prescales = [
            (bit + 1, trigger_config[f"cfg_prescale_bit{bit}"])
            for bit in range(16)
            if f"cfg_prescale_bit{bit}" in trigger_config
        ]
        if prescales:
            lines.append(
                "- Prescales by trigger path: "
                + ", ".join(f"bit{bit}={_fmt(value)}" for bit, value in prescales)
                + "."
            )
        masked = [pin for pin in range(64) if trigger_config.get(f"cfg_mask_ch{pin}") == 0.0]
        unmasked = [pin for pin in range(64) if trigger_config.get(f"cfg_mask_ch{pin}") == 1.0]
        if masked or unmasked:
            lines.append(f"- Trigger mask: {len(unmasked)} unmasked, {len(masked)} masked physical pins.")
            lines.append("- Masked physical pins: " + (", ".join(map(str, masked)) or "none") + ".")
        scalar_names = (
            ("cfg_dead_time", "dead_time"),
            ("cfg_coincidence_time", "coincidence_time"),
            ("cfg_nLayerThreshold", "nLayerThreshold"),
            ("cfg_nHitThreshold", "nHitThreshold"),
            ("cfg_zero_bias", "zero_bias"),
        )
        scalar_text = [
            f"{label}={_fmt(trigger_config[key])}"
            for key, label in scalar_names
            if key in trigger_config
        ]
        if scalar_text:
            lines.append("- Trigger configuration fields: " + ", ".join(scalar_text) + ".")
    else:
        lines.append("- Trigger configuration: unavailable.")

    if daq_thresholds:
        values = np.asarray(list(daq_thresholds.values()), dtype=float)
        values = values[np.isfinite(values)]
        if values.size:
            lines.append(
                f"- DAQ trigger thresholds: {values.size} channels, median {_fmt(float(np.median(values)))}, "
                f"range {_fmt(float(values.min()))} to {_fmt(float(values.max()))}, "
                f"{len(np.unique(values))} unique values."
            )
        else:
            lines.append("- DAQ trigger thresholds: unavailable.")
    else:
        lines.append("- DAQ trigger thresholds: unavailable.")
    lines.extend(
        [
            "- Within-run configuration changes: unavailable; only the static per-run configuration snapshot is parsed.",
            "- Board matching, synchronization, queue occupancy, and DAQ-state telemetry: unavailable.",
        ]
    )
    return _bounded(lines)


def _first_digitizer_path(input_paths_file: Path) -> Path | None:
    if not input_paths_file.is_file():
        return None
    for line in input_paths_file.read_text(encoding="utf-8", errors="replace").splitlines():
        candidate = line.strip()
        if candidate:
            return Path(candidate)
    return None


def build_context_bundle(manifest: dict[str, Any], run: int, repo_root: Path) -> ContextBundle:
    context = manifest.get("context_sources", {})
    campaign = Path(manifest["frozen_campaign"])
    if not campaign.is_absolute():
        campaign = repo_root / campaign
    input_pattern = context.get("input_paths_pattern", "runs/run{run}/input_paths.txt")
    input_paths_file = campaign / input_pattern.format(run=run)
    digitizer = _first_digitizer_path(input_paths_file)
    telemetry_dir = digitizer.parent if digitizer else None
    trigger_path = telemetry_dir / f"TriggerBoard_run{run}.csv" if telemetry_dir else None
    lvds_path = telemetry_dir / f"TriggerBoardSlab_run{run}_LVDSCounts.csv" if telemetry_dir else None
    configs_dir = Path(context.get("run_configs_dir", ""))
    thresholds_path = Path(context.get("thresholds_json_path", ""))

    trigger_frame = (
        _read_triggerboard(trigger_path)
        if trigger_path is not None and trigger_path.is_file()
        else None
    )
    lvds_frame = (
        _read_triggerboard(lvds_path) if lvds_path is not None and lvds_path.is_file() else None
    )
    trigger_config = parse_trigger_config(run, str(configs_dir), TRIGGER_VARIABLES)
    daq_thresholds = parse_daq_thresholds(
        run, str(configs_dir), str(thresholds_path), DAQ_VARIABLES
    )

    trigger_summary = build_trigger_summary(trigger_frame, trigger_config)
    lvds_summary = build_lvds_summary(lvds_frame)
    daq_summary = build_daq_config_summary(trigger_config, daq_thresholds)
    source_paths = {
        "trigger": [str(trigger_path)] if trigger_path is not None and trigger_path.is_file() else [],
        "lvds": [str(lvds_path)] if lvds_path is not None and lvds_path.is_file() else [],
        "daq_config": [
            str(path)
            for path in (
                configs_dir / f"Run{run}TriggerDefault.py",
                configs_dir / f"Run{run}DAQDefault.py",
                thresholds_path,
            )
            if path.is_file()
        ],
    }
    return ContextBundle(
        trigger_summary=trigger_summary,
        lvds_summary=lvds_summary,
        daq_config_summary=daq_summary,
        availability={
            "trigger": not trigger_summary.endswith("unavailable"),
            "lvds": not lvds_summary.endswith("unavailable"),
            "daq_config": not daq_summary.endswith("unavailable"),
        },
        source_paths=source_paths,
        source_types={
            "trigger": "TriggerBoard detector telemetry CSV",
            "lvds": "LVDS detector telemetry CSV",
            "daq_config": "MilliDAQ run configuration parsed by existing repository parser",
        },
    )
