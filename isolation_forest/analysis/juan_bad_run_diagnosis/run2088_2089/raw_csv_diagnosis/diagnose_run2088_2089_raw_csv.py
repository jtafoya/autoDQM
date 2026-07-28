#!/usr/bin/env python3
"""Focused raw Digitizer CSV diagnosis for selected run-2088/2089 cases."""

from __future__ import annotations

import json
import math
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
BASE = (
    IF_DIR
    / "analysis"
    / "juan_bad_run_diagnosis"
    / "run2088_2089"
)
OUT = BASE / "raw_csv_diagnosis"
PLOTS = OUT / "plots"
TIMELINE = BASE / "run2088_2089_subrun_timeline.csv"
REPRESENTATIVES = BASE / "run2088_2089_representative_subruns.csv"
LOG = IF_DIR / "logs" / f"{TAG}.csv"
PATH_CACHE = IF_DIR / "logs" / f"{TAG}_paths.txt"
MODEL_DIR = IF_DIR / "models" / TAG
RUNS = [2088, 2089]
Z_THRESHOLD = 8.0
FIXED_NPULSE_TARGETS = [
    {
        "case": "typical_2088",
        "run": 2088,
        "subrun": 321,
        "channel": 43,
        "role": "typical nPulses_median extreme",
    },
    {
        "case": "sub324_context_ch19",
        "run": 2089,
        "subrun": 324,
        "channel": 19,
        "role": "same-file anomalous channel; authoritative trigger is not nPulses",
    },
    {
        "case": "typical_2089",
        "run": 2089,
        "subrun": 324,
        "channel": 26,
        "role": "typical nPulses_median extreme",
    },
]
MILLION_TARGETS = [
    {
        "case": "million_2088",
        "run": 2088,
        "subrun": 396,
        "channel": 69,
    },
    {
        "case": "million_2089",
        "run": 2089,
        "subrun": 270,
        "channel": 23,
    },
]
BULK_CONTEXT = [(2088, 508), (2089, 922), (2089, 659)]


def fail(message: str) -> "None":
    raise RuntimeError(f"SANITY CHECK FAILED: {message}")


def as_bool(series: pd.Series, name: str) -> pd.Series:
    if series.dtype == bool:
        return series
    values = series.astype(str).str.strip().str.lower()
    if not values.isin(["true", "false"]).all():
        fail(f"{name} contains non-boolean values")
    return values.eq("true")


def text(value: object) -> str:
    return "" if pd.isna(value) else str(value)


def split_features(value: object) -> list[str]:
    if pd.isna(value) or not str(value).strip():
        return []
    return list(
        dict.fromkeys(
            item.strip() for item in str(value).split(";") if item.strip()
        )
    )


def safe_output(path: Path) -> Path:
    if path != OUT and OUT not in path.parents:
        fail(f"attempted output outside raw_csv_diagnosis: {path}")
    return path


def savefig(path: Path) -> None:
    safe_output(path)
    plt.savefig(path, dpi=190, bbox_inches="tight")
    plt.close()


def json_clean(value):
    if isinstance(value, dict):
        return {str(key): json_clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_clean(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return value


def canonical_features(filepath: str, reference) -> pd.DataFrame:
    from src.features import extract_features

    return extract_features(
        filepath,
        use_trigger=reference._use_trigger,
        use_lvds=reference._use_lvds,
        ignore_features=reference._ignore_features,
        include_trigger_config=reference._include_trigger_config,
        trigger_config_vars=reference._trigger_config_vars,
        include_daq_config=reference._include_daq_config,
        daq_config_vars=reference._daq_config_vars,
        run_configs_dir=reference._run_configs_dir,
        thresholds_json_path=reference._thresholds_json_path,
    )


def reference_arrays(
    reference, channel: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    state = reference._state[channel]
    mean = state["mean"].copy()
    if state["count"] > 1:
        raw_std = np.sqrt(state["M2"] / state["count"])
    else:
        raw_std = np.ones_like(mean)
    _, used_std = reference.get_stats(channel)
    return mean, raw_std, used_std


def nearest_ok_controls(
    timeline: pd.DataFrame,
    run: int,
    sequence_index: int,
) -> list[dict[str, object]]:
    run_timeline = timeline[timeline["run"] == run].sort_values(
        "sequence_index_within_run"
    ).reset_index(drop=True)
    if int(run_timeline.iloc[sequence_index]["sequence_index_within_run"]) != sequence_index:
        fail(f"run {run} timeline positional order mismatch")
    controls: list[dict[str, object]] = []
    for direction, positions in [
        ("previous_OK", range(sequence_index - 1, -1, -1)),
        ("next_OK", range(sequence_index + 1, len(run_timeline))),
    ]:
        for position in positions:
            row = run_timeline.iloc[position]
            if row["strict_status"] == "OK":
                controls.append(
                    {
                        "comparison_role": direction,
                        "run": int(row["run"]),
                        "subrun": int(row["subrun"]),
                        "filename": str(row["filename"]),
                        "sequence_index_within_run": int(
                            row["sequence_index_within_run"]
                        ),
                        "strict_status": str(row["strict_status"]),
                    }
                )
                break
    if len(controls) != 2:
        fail(f"could not find previous and next OK controls for run {run} index {sequence_index}")
    return controls


def numeric_summary(values: pd.Series) -> dict[str, object]:
    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric[np.isfinite(numeric)]
    if finite.empty:
        return {
            "count": 0,
            "nan_count": int(numeric.isna().sum()),
            "inf_count": int(np.isinf(numeric.fillna(0)).sum()),
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "median": None,
            "q25": None,
            "q75": None,
            "q90": None,
            "q95": None,
            "q99": None,
        }
    return {
        "count": int(len(finite)),
        "nan_count": int(numeric.isna().sum()),
        "inf_count": int(np.isinf(numeric.fillna(0)).sum()),
        "min": float(finite.min()),
        "max": float(finite.max()),
        "mean": float(finite.mean()),
        "std": float(finite.std(ddof=1)) if len(finite) > 1 else 0.0,
        "median": float(finite.median()),
        "q25": float(finite.quantile(0.25)),
        "q75": float(finite.quantile(0.75)),
        "q90": float(finite.quantile(0.90)),
        "q95": float(finite.quantile(0.95)),
        "q99": float(finite.quantile(0.99)),
    }


def npulse_event_summary(
    raw: pd.DataFrame,
    channel: int,
) -> tuple[dict[str, object], dict[str, int]]:
    channel_raw = raw[raw["channel"].astype(int) == channel]
    values = pd.to_numeric(channel_raw["nPulses"], errors="coerce")
    finite = values[np.isfinite(values)]
    summary = numeric_summary(values)
    total_file_events = int(raw["event_id"].nunique())
    target_events = int(channel_raw["event_id"].nunique())
    counts = {
        str(int(key) if float(key).is_integer() else float(key)): int(value)
        for key, value in finite.value_counts().sort_index().items()
    }
    summary.update(
        {
            "total_unique_events": total_file_events,
            "target_channel_rows": int(len(channel_raw)),
            "target_channel_event_count": target_events,
            "occupancy": target_events / total_file_events,
            "fraction_nPulses_eq_0": (
                float((finite == 0).mean()) if len(finite) else None
            ),
            "fraction_nPulses_eq_1": (
                float((finite == 1).mean()) if len(finite) else None
            ),
            "fraction_nPulses_ge_2": (
                float((finite >= 2).mean()) if len(finite) else None
            ),
            "value_counts_json": json.dumps(counts),
        }
    )
    return summary, counts


def sideband_event_summary(
    raw: pd.DataFrame,
    channel: int,
) -> dict[str, object]:
    channel_raw = raw[raw["channel"].astype(int) == channel]
    values = pd.to_numeric(channel_raw["sideband_rms"], errors="coerce")
    finite = values[np.isfinite(values)].sort_values()
    summary = numeric_summary(values)
    total_events = int(raw["event_id"].nunique())
    target_events = int(channel_raw["event_id"].nunique())
    if len(finite):
        top_n = max(1, int(math.ceil(0.01 * len(finite))))
        lower = finite.iloc[:-top_n] if len(finite) > top_n else finite.iloc[:0]
        positive_sum = float(finite.clip(lower=0).sum())
        top_sum = float(finite.iloc[-top_n:].clip(lower=0).sum())
        top_fraction = top_sum / positive_sum if positive_sum > 0 else None
        mean_without = float(lower.mean()) if len(lower) else None
    else:
        top_n = 0
        top_fraction = None
        mean_without = None
    summary.update(
        {
            "total_unique_events": total_events,
            "target_channel_rows": int(len(channel_raw)),
            "target_channel_event_count": target_events,
            "occupancy": target_events / total_events,
            "top_1pct_count": top_n,
            "top_1pct_fraction_of_positive_sum": top_fraction,
            "mean_excluding_top_1pct": mean_without,
        }
    )
    return summary


def main() -> None:
    sys.path.insert(0, str(IF_DIR))
    from src.features import METRIC_COLS
    from src.reference import ReferenceModel
    from src.run_list import parse_run_subrun

    required = [
        TIMELINE,
        REPRESENTATIVES,
        LOG,
        PATH_CACHE,
        MODEL_DIR / "reference.npz",
        MODEL_DIR / "config.yaml",
        MODEL_DIR / "training_metadata.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        fail(f"missing required inputs: {missing}")
    if OUT.exists():
        unexpected = [
            path
            for path in OUT.rglob("*")
            if path.is_file()
            and path.name != "diagnose_run2088_2089_raw_csv.py"
        ]
        if unexpected:
            fail(f"output directory is not new/empty: {unexpected}")
    OUT.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(exist_ok=True)
    production_before = {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in required
    }

    timeline = pd.read_csv(TIMELINE).sort_values(
        ["run", "sequence_index_within_run"]
    ).reset_index(drop=True)
    for column in ["persistent_alert", "bulk_alert", "extreme_alert"]:
        timeline[column] = as_bool(timeline[column], column)
    if (
        len(timeline[timeline["run"] == 2088]) != 203
        or len(timeline[timeline["run"] == 2089]) != 369
        or set(timeline["run"]) != {2088, 2089}
    ):
        fail("authoritative timeline is not exactly runs 2088/2089")

    paths = [
        path
        for path in PATH_CACHE.read_text().splitlines()
        if parse_run_subrun(path)[0] in RUNS
    ]
    path_by_name = {Path(path).name: path for path in paths}
    for run in RUNS:
        ordered = timeline[timeline["run"] == run]["filename"].tolist()
        cached = [
            Path(path).name
            for path in paths
            if parse_run_subrun(path)[0] == run
        ]
        if cached != ordered:
            fail(f"run {run} path cache differs from timeline order")

    log = pd.read_csv(LOG)
    run_names = set(timeline["filename"])
    run_log = log[log["filename"].isin(run_names)].copy()
    del log
    run_log["anomalous"] = as_bool(run_log["anomalous"], "anomalous")
    if run_log.duplicated(["filename", "channel"]).any():
        fail("duplicate filename/channel rows in anomaly log")
    log_index = run_log.set_index(["filename", "channel"])

    reference = ReferenceModel.load(str(MODEL_DIR / "reference.npz"))
    active_features = list(reference._feat_cols)
    for required_feature in [
        "nPulses_median",
        "sideband_rms_mean",
        "occupancy",
        "frac_dead",
    ]:
        if required_feature not in active_features:
            fail(f"active model lacks {required_feature}")

    raw_cache: dict[str, pd.DataFrame] = {}
    feature_cache: dict[str, pd.DataFrame] = {}
    raw_stats_at_open: dict[str, tuple[int, int]] = {}

    def get_raw(filename: str) -> pd.DataFrame:
        if filename not in raw_cache:
            filepath = path_by_name.get(filename)
            if not filepath or not Path(filepath).is_file():
                fail(f"raw CSV missing: {filename}")
            raw_path = Path(filepath)
            raw_stats_at_open[str(raw_path)] = (
                raw_path.stat().st_size,
                raw_path.stat().st_mtime_ns,
            )
            raw_cache[filename] = pd.read_csv(filepath)
        return raw_cache[filename]

    def get_features(filename: str) -> pd.DataFrame:
        if filename not in feature_cache:
            feature_cache[filename] = canonical_features(
                path_by_name[filename], reference
            )
        return feature_cache[filename]

    def exact_feature(
        filename: str, channel: int, feature: str
    ) -> dict[str, object]:
        features = get_features(filename)
        if channel not in features.index:
            fail(f"channel {channel} absent from canonical features for {filename}")
        mean, raw_std, used_std = reference_arrays(reference, channel)
        idx = active_features.index(feature)
        observed = float(features.loc[channel, feature])
        z = (observed - mean[idx]) / used_std[idx]
        return {
            "feature": feature,
            "observed_value": observed,
            "reference_mean": float(mean[idx]),
            "reference_raw_std": float(raw_std[idx]),
            "reference_std_used": float(used_std[idx]),
            "std_floor_applied": bool(raw_std[idx] < 1e-6),
            "z_score": float(z),
            "abs_z": float(abs(z)),
        }

    def verify_log_reconstruction(filename: str, channel: int) -> None:
        row = log_index.loc[(filename, channel)]
        features = get_features(filename)
        observed = features.loc[
            channel, active_features
        ].to_numpy(dtype=float)
        mean, _, used_std = reference_arrays(reference, channel)
        z = (observed - mean) / used_std
        exact_max = float(np.nanmax(np.abs(z)))
        if round(exact_max, 2) != float(row["max_z"]):
            fail(
                f"max-z mismatch {filename} ch{channel}: "
                f"{exact_max} vs log {row['max_z']}"
            )
        for feature in split_features(row["triggered_features"]):
            idx = active_features.index(feature)
            if not abs(z[idx]) > Z_THRESHOLD:
                fail(
                    f"logged trigger {feature} does not exceed z threshold "
                    f"for {filename} ch{channel}"
                )

    def row_for(run: int, subrun: int) -> pd.Series:
        rows = timeline[
            (timeline["run"] == run) & (timeline["subrun"] == subrun)
        ]
        if len(rows) != 1:
            fail(f"expected one timeline row for run{subrun} subrun{subrun}")
        return rows.iloc[0]

    # Verify fixed targets and create target/control plans.
    typical_plan: list[dict[str, object]] = []
    for target in FIXED_NPULSE_TARGETS:
        timeline_row = row_for(target["run"], target["subrun"])
        filename = str(timeline_row["filename"])
        channel = int(target["channel"])
        if (filename, channel) not in log_index.index:
            fail(f"fixed target absent from log: {filename} ch{channel}")
        log_row = log_index.loc[(filename, channel)]
        verify_log_reconstruction(filename, channel)
        logged_features = split_features(log_row["triggered_features"])
        if target["case"] in ["typical_2088", "typical_2089"]:
            if "nPulses_median" not in logged_features:
                fail(f"{target['case']} is not an nPulses_median trigger")
        if target["case"] == "sub324_context_ch19" and (
            "nPulses_median" in logged_features
        ):
            fail("subrun324 ch19 unexpectedly is an nPulses_median trigger")
        target_record = {
            **target,
            "comparison_role": "target",
            "filename": filename,
            "sequence_index_within_run": int(
                timeline_row["sequence_index_within_run"]
            ),
            "strict_status": str(timeline_row["strict_status"]),
            "source_target_run": int(target["run"]),
            "source_target_subrun": int(target["subrun"]),
            "source_target_channel": channel,
        }
        typical_plan.append(target_record)
        for control in nearest_ok_controls(
            timeline,
            int(target["run"]),
            int(timeline_row["sequence_index_within_run"]),
        ):
            typical_plan.append(
                {
                    **target,
                    **control,
                    "source_target_run": int(target["run"]),
                    "source_target_subrun": int(target["subrun"]),
                    "source_target_channel": channel,
                }
            )

    typical_rows = []
    value_count_rows = []
    for plan in typical_plan:
        filename = str(plan["filename"])
        channel = int(plan["channel"])
        raw_summary, counts = npulse_event_summary(
            get_raw(filename), channel
        )
        reconstruction = exact_feature(
            filename, channel, "nPulses_median"
        )
        log_row = log_index.loc[(filename, channel)]
        logged_feature_details = [
            exact_feature(filename, channel, feature)
            for feature in split_features(log_row["triggered_features"])
        ]
        typical_rows.append(
            {
                **{
                    key: plan[key]
                    for key in [
                        "case",
                        "role",
                        "source_target_run",
                        "source_target_subrun",
                        "source_target_channel",
                        "comparison_role",
                        "run",
                        "subrun",
                        "filename",
                        "sequence_index_within_run",
                        "strict_status",
                    ]
                },
                "logged_anomalous": bool(log_row["anomalous"]),
                "logged_method": text(log_row["method"]),
                "logged_triggered_features": text(
                    log_row["triggered_features"]
                ),
                "logged_max_z": float(log_row["max_z"]),
                "channel": channel,
                "logged_trigger_feature_reconstruction_json": json.dumps(
                    json_clean(logged_feature_details)
                ),
                **reconstruction,
                **raw_summary,
            }
        )
        for value, count in counts.items():
            value_count_rows.append(
                {
                    "case": plan["case"],
                    "source_target_run": plan["source_target_run"],
                    "source_target_subrun": plan["source_target_subrun"],
                    "source_target_channel": plan["source_target_channel"],
                    "comparison_role": plan["comparison_role"],
                    "run": plan["run"],
                    "subrun": plan["subrun"],
                    "filename": filename,
                    "channel": channel,
                    "nPulses_value": value,
                    "count": count,
                    "fraction": count / raw_summary["count"],
                }
            )
    typical_df = pd.DataFrame(typical_rows)
    typical_df.to_csv(
        safe_output(OUT / "typical_extreme_npulses_summary.csv"),
        index=False,
    )
    pd.DataFrame(value_count_rows).to_csv(
        safe_output(OUT / "typical_extreme_npulses_value_counts.csv"),
        index=False,
    )

    # Million-z reconstructions and raw distributions.
    million_rows = []
    extreme_file_targets: dict[str, list[int]] = {}
    for target in MILLION_TARGETS:
        timeline_row = row_for(target["run"], target["subrun"])
        filename = str(timeline_row["filename"])
        channel = int(target["channel"])
        verify_log_reconstruction(filename, channel)
        log_row = log_index.loc[(filename, channel)]
        if "nPulses_median" not in split_features(
            log_row["triggered_features"]
        ):
            fail(f"million target is not nPulses_median: {filename} ch{channel}")
        reconstruction = exact_feature(
            filename, channel, "nPulses_median"
        )
        raw_summary, _ = npulse_event_summary(get_raw(filename), channel)
        million_rows.append(
            {
                **target,
                "filename": filename,
                "sequence_index_within_run": int(
                    timeline_row["sequence_index_within_run"]
                ),
                "strict_status": str(timeline_row["strict_status"]),
                "logged_method": text(log_row["method"]),
                "logged_triggered_features": text(
                    log_row["triggered_features"]
                ),
                "logged_max_z": float(log_row["max_z"]),
                **reconstruction,
                **raw_summary,
                "million_z_numerical_origin_confirmed": bool(
                    reconstruction["std_floor_applied"]
                    and abs(reconstruction["observed_value"] - reconstruction["reference_mean"])
                    >= 0.999
                    and reconstruction["abs_z"] >= 999999
                ),
            }
        )
        extreme_file_targets.setdefault(filename, []).append(channel)
    million_df = pd.DataFrame(million_rows)
    million_df.to_csv(
        safe_output(OUT / "million_z_reconstruction.csv"), index=False
    )

    # Add typical target files to the all-channel extreme-file analysis.
    for target in FIXED_NPULSE_TARGETS:
        timeline_row = row_for(target["run"], target["subrun"])
        filename = str(timeline_row["filename"])
        extreme_file_targets.setdefault(filename, []).append(
            int(target["channel"])
        )
    extreme_channel_rows = []
    extreme_file_metrics = {}
    for filename, target_channels in extreme_file_targets.items():
        raw = get_raw(filename)
        features = get_features(filename)
        timeline_row = timeline[timeline["filename"] == filename].iloc[0]
        n_events = int(raw["event_id"].nunique())
        z_values = {}
        for channel in range(96):
            if channel not in features.index:
                fail(f"channel {channel} absent from {filename}")
            channel_raw = raw[raw["channel"].astype(int) == channel]
            npulses = pd.to_numeric(
                channel_raw["nPulses"], errors="coerce"
            )
            mean, raw_std, used_std = reference_arrays(reference, channel)
            idx = active_features.index("nPulses_median")
            observed = float(features.loc[channel, "nPulses_median"])
            z_value = float((observed - mean[idx]) / used_std[idx])
            z_values[channel] = z_value
            extreme_channel_rows.append(
                {
                    "run": int(timeline_row["run"]),
                    "subrun": int(timeline_row["subrun"]),
                    "filename": filename,
                    "strict_status": str(timeline_row["strict_status"]),
                    "channel": channel,
                    "is_target_channel": channel in set(target_channels),
                    "nPulses_mean": float(npulses.mean()),
                    "nPulses_std": float(npulses.std(ddof=1)),
                    "nPulses_median": float(npulses.median()),
                    "occupancy": (
                        channel_raw["event_id"].nunique() / n_events
                    ),
                    "frac_dead": float((npulses == 0).mean()),
                    "reference_nPulses_median_mean": float(mean[idx]),
                    "reference_nPulses_median_raw_std": float(raw_std[idx]),
                    "reference_nPulses_median_std_used": float(used_std[idx]),
                    "z_nPulses_median": z_value,
                    "abs_z_over_8": abs(z_value) > 8,
                    "abs_z_over_15": abs(z_value) >= 15,
                }
            )
        over8 = [ch for ch, z in z_values.items() if abs(z) > 8]
        over15 = [ch for ch, z in z_values.items() if abs(z) >= 15]
        classification = (
            "single-channel"
            if len(over8) == 1
            else "small-local-group"
            if len(over8) <= 4
            else "broad"
        )
        extreme_file_metrics[filename] = {
            "n_channels_npulses_median_abs_z_over8": len(over8),
            "channels_npulses_median_abs_z_over8": over8,
            "n_channels_npulses_median_abs_z_over15": len(over15),
            "channels_npulses_median_abs_z_over15": over15,
            "npulses_locality_classification": classification,
        }
    extreme_channel_df = pd.DataFrame(extreme_channel_rows)
    extreme_channel_df.to_csv(
        safe_output(OUT / "extreme_file_channel_summary.csv"),
        index=False,
    )

    # Automatically select sideband cases from authoritative triggered rows.
    sideband_candidates = run_log[
        run_log["anomalous"]
        & run_log["triggered_features"]
        .fillna("")
        .map(lambda value: "sideband_rms_mean" in split_features(value))
    ].copy()
    sideband_candidates["run"] = sideband_candidates["filename"].map(
        timeline.set_index("filename")["run"]
    )
    selected_sideband = []
    run2089_candidates = sideband_candidates[
        sideband_candidates["run"] == 2089
    ].sort_values("max_z")
    if len(run2089_candidates) != 36:
        fail(
            f"expected 36 Run2089 sideband_rms_mean triggers, "
            f"found {len(run2089_candidates)}"
        )
    median_z = float(run2089_candidates["max_z"].median())
    typical_idx = (
        run2089_candidates["max_z"] - median_z
    ).abs().idxmin()
    typical_sideband = run2089_candidates.loc[typical_idx]
    large_sideband = run2089_candidates.sort_values(
        ["max_z", "filename", "channel"], ascending=[False, True, True]
    ).iloc[0]
    if typical_sideband["filename"] == large_sideband["filename"] and int(
        typical_sideband["channel"]
    ) == int(large_sideband["channel"]):
        fail("typical and large Run2089 sideband selections are identical")
    run2088_candidates = sideband_candidates[
        sideband_candidates["run"] == 2088
    ].sort_values(["max_z", "channel"], ascending=[False, True])
    if len(run2088_candidates) != 2:
        fail(
            f"expected 2 Run2088 sideband_rms_mean triggers, "
            f"found {len(run2088_candidates)}"
        )
    comparable_sideband = run2088_candidates.iloc[0]
    for selection_role, row in [
        ("run2089_typical", typical_sideband),
        ("run2089_large_z", large_sideband),
        ("run2088_comparable", comparable_sideband),
    ]:
        timeline_row = timeline[
            timeline["filename"] == row["filename"]
        ].iloc[0]
        selected_sideband.append(
            {
                "selection_role": selection_role,
                "run": int(timeline_row["run"]),
                "subrun": int(timeline_row["subrun"]),
                "filename": str(row["filename"]),
                "channel": int(row["channel"]),
                "sequence_index_within_run": int(
                    timeline_row["sequence_index_within_run"]
                ),
                "strict_status": str(timeline_row["strict_status"]),
                "logged_method": text(row["method"]),
                "logged_triggered_features": text(
                    row["triggered_features"]
                ),
                "logged_max_z": float(row["max_z"]),
                "logged_if_score": float(row["if_score"]),
            }
        )

    sideband_plan = []
    for target in selected_sideband:
        sideband_plan.append(
            {
                **target,
                "comparison_role": "target",
                "source_target_run": target["run"],
                "source_target_subrun": target["subrun"],
                "source_target_channel": target["channel"],
            }
        )
        for control in nearest_ok_controls(
            timeline,
            target["run"],
            target["sequence_index_within_run"],
        ):
            sideband_plan.append(
                {
                    **target,
                    **control,
                    "source_target_run": target["run"],
                    "source_target_subrun": target["subrun"],
                    "source_target_channel": target["channel"],
                }
            )

    sideband_raw_rows = []
    sideband_recon_rows = []
    sideband_file_metrics = {}
    for plan in sideband_plan:
        filename = str(plan["filename"])
        channel = int(plan["channel"])
        raw_summary = sideband_event_summary(get_raw(filename), channel)
        reconstruction = exact_feature(
            filename, channel, "sideband_rms_mean"
        )
        log_row = log_index.loc[(filename, channel)]
        sideband_raw_rows.append(
            {
                **{
                    key: plan[key]
                    for key in [
                        "selection_role",
                        "source_target_run",
                        "source_target_subrun",
                        "source_target_channel",
                        "comparison_role",
                        "run",
                        "subrun",
                        "filename",
                        "channel",
                        "sequence_index_within_run",
                        "strict_status",
                    ]
                },
                **raw_summary,
            }
        )
        if filename not in sideband_file_metrics:
            features = get_features(filename)
            z_by_channel = {}
            for candidate_channel in range(96):
                mean, _, used_std = reference_arrays(
                    reference, candidate_channel
                )
                idx = active_features.index("sideband_rms_mean")
                observed = float(
                    features.loc[candidate_channel, "sideband_rms_mean"]
                )
                z_by_channel[candidate_channel] = float(
                    (observed - mean[idx]) / used_std[idx]
                )
            over8 = [
                ch for ch, z in z_by_channel.items() if abs(z) > 8
            ]
            sideband_file_metrics[filename] = {
                "n_channels_sideband_rms_mean_abs_z_over8": len(over8),
                "channels_sideband_rms_mean_abs_z_over8": over8,
                "maximum_abs_sideband_rms_mean_z": max(
                    abs(z) for z in z_by_channel.values()
                ),
                "z_by_channel": z_by_channel,
            }
        locality = sideband_file_metrics[filename]
        sideband_recon_rows.append(
            {
                **{
                    key: plan[key]
                    for key in [
                        "selection_role",
                        "source_target_run",
                        "source_target_subrun",
                        "source_target_channel",
                        "comparison_role",
                        "run",
                        "subrun",
                        "filename",
                        "channel",
                        "strict_status",
                    ]
                },
                "logged_anomalous": bool(log_row["anomalous"]),
                "logged_method": text(log_row["method"]),
                "logged_triggered_features": text(
                    log_row["triggered_features"]
                ),
                "logged_max_z": float(log_row["max_z"]),
                **reconstruction,
                "n_channels_sideband_rms_mean_abs_z_over8": locality[
                    "n_channels_sideband_rms_mean_abs_z_over8"
                ],
                "channels_sideband_rms_mean_abs_z_over8": ";".join(
                    str(ch)
                    for ch in locality[
                        "channels_sideband_rms_mean_abs_z_over8"
                    ]
                ),
                "maximum_abs_sideband_rms_mean_z": locality[
                    "maximum_abs_sideband_rms_mean_z"
                ],
            }
        )
        if plan["comparison_role"] == "target":
            verify_log_reconstruction(filename, channel)
    sideband_raw_df = pd.DataFrame(sideband_raw_rows)
    sideband_recon_df = pd.DataFrame(sideband_recon_rows)
    sideband_raw_df.to_csv(
        safe_output(OUT / "sideband_rms_raw_summary.csv"), index=False
    )
    sideband_recon_df.to_csv(
        safe_output(OUT / "sideband_rms_feature_reconstruction.csv"),
        index=False,
    )

    # Lightweight bulk context uses log/timeline only; no raw CSV is opened.
    bulk_rows = []
    for run, subrun in BULK_CONTEXT:
        timeline_row = row_for(run, subrun)
        filename = str(timeline_row["filename"])
        anomalous_rows = run_log[
            (run_log["filename"] == filename) & run_log["anomalous"]
        ].copy()
        if len(anomalous_rows) != int(
            timeline_row["n_anomalous_channels"]
        ):
            fail(f"bulk context anomaly count mismatch for {filename}")
        methods = set(text(value) for value in anomalous_rows["method"])
        file_features = [
            feature
            for value in anomalous_rows["triggered_features"]
            for feature in split_features(value)
        ]
        n_npulse = sum(
            feature == "nPulses_median" for feature in file_features
        )
        if "isolation_forest" in methods and any(
            method in methods for method in ["statistical", "statistical+IF"]
        ):
            classification = "mixed IF + statistical anomalies"
        elif n_npulse >= 2:
            classification = "multiple nPulses/statistical patterns"
        else:
            classification = "heterogeneous statistical pattern"
        for row in anomalous_rows.itertuples(index=False):
            bulk_rows.append(
                {
                    "run": run,
                    "subrun": subrun,
                    "filename": filename,
                    "strict_status": str(timeline_row["strict_status"]),
                    "persistent_alert": bool(
                        timeline_row["persistent_alert"]
                    ),
                    "bulk_alert": bool(timeline_row["bulk_alert"]),
                    "extreme_alert": bool(
                        timeline_row["extreme_alert"]
                    ),
                    "n_anomalous_channels": int(
                        timeline_row["n_anomalous_channels"]
                    ),
                    "channel": int(row.channel),
                    "method": text(row.method),
                    "triggered_features": text(row.triggered_features),
                    "max_z": float(row.max_z),
                    "if_score": float(row.if_score),
                    "file_pattern_classification": classification,
                    "raw_csv_opened_for_bulk_context": False,
                }
            )
    pd.DataFrame(bulk_rows).to_csv(
        safe_output(OUT / "bulk_context_summary.csv"), index=False
    )

    # Integrity for every raw file actually opened.
    integrity_rows = []
    relevant_columns = [
        column
        for column in METRIC_COLS
        if column in next(iter(raw_cache.values())).columns
    ]
    target_channels_by_filename: dict[str, set[int]] = {}
    for plan in typical_plan + sideband_plan:
        target_channels_by_filename.setdefault(
            str(plan["filename"]), set()
        ).add(int(plan["channel"]))
    for target in MILLION_TARGETS:
        filename = str(row_for(target["run"], target["subrun"])["filename"])
        target_channels_by_filename.setdefault(filename, set()).add(
            int(target["channel"])
        )
    for filename, raw in raw_cache.items():
        filepath = Path(path_by_name[filename])
        numeric = raw[relevant_columns].apply(
            pd.to_numeric, errors="coerce"
        )
        target_channels = target_channels_by_filename.get(filename, set())
        present_channels = set(raw["channel"].astype(int).unique())
        integrity_rows.append(
            {
                "filename": filename,
                "filepath": str(filepath),
                "file_exists": filepath.is_file(),
                "file_readable": True,
                "file_size_bytes": filepath.stat().st_size,
                "row_count": int(len(raw)),
                "unique_event_count": int(raw["event_id"].nunique()),
                "unique_channel_count": int(raw["channel"].nunique()),
                "channel_ids_present": ";".join(
                    str(ch) for ch in sorted(present_channels)
                ),
                "target_channels": ";".join(
                    str(ch) for ch in sorted(target_channels)
                ),
                "missing_target_channels": ";".join(
                    str(ch)
                    for ch in sorted(target_channels - present_channels)
                ),
                "duplicate_event_channel_rows": int(
                    raw.duplicated(["event_id", "channel"], keep=False).sum()
                ),
                "nan_count_relevant_raw_columns": int(
                    numeric.isna().sum().sum()
                ),
                "inf_count_relevant_raw_columns": int(
                    np.isinf(numeric.to_numpy(dtype=float)).sum()
                ),
                "mean_channels_per_event": float(
                    raw.groupby("event_id")["channel"].nunique().mean()
                ),
                "min_channels_per_event": int(
                    raw.groupby("event_id")["channel"].nunique().min()
                ),
                "max_channels_per_event": int(
                    raw.groupby("event_id")["channel"].nunique().max()
                ),
                "empty_or_malformed": bool(
                    raw.empty
                    or not {"event_id", "channel"}.issubset(raw.columns)
                ),
            }
        )
    integrity_df = pd.DataFrame(integrity_rows)
    row_median = float(integrity_df["row_count"].median())
    event_median = float(integrity_df["unique_event_count"].median())
    integrity_df["row_count_ratio_to_opened_file_median"] = (
        integrity_df["row_count"] / row_median
    )
    integrity_df["event_count_ratio_to_opened_file_median"] = (
        integrity_df["unique_event_count"] / event_median
    )
    integrity_df["strongly_abnormal_coverage"] = (
        integrity_df["row_count_ratio_to_opened_file_median"] < 0.5
    ) | (
        integrity_df["event_count_ratio_to_opened_file_median"] < 0.5
    )
    integrity_df["integrity_issue"] = (
        ~integrity_df["file_exists"]
        | ~integrity_df["file_readable"]
        | integrity_df["empty_or_malformed"]
        | integrity_df["missing_target_channels"].fillna("").ne("")
        | integrity_df["duplicate_event_channel_rows"].gt(0)
        | integrity_df["nan_count_relevant_raw_columns"].gt(0)
        | integrity_df["inf_count_relevant_raw_columns"].gt(0)
        | integrity_df["unique_channel_count"].ne(96)
        | integrity_df["strongly_abnormal_coverage"]
    )
    integrity_df.to_csv(
        safe_output(OUT / "representative_file_integrity.csv"),
        index=False,
    )

    # Plots: typical target-vs-controls discrete nPulses distributions.
    for case, group in typical_df.groupby("case", sort=False):
        plt.figure(figsize=(9, 5.2))
        for row in group.itertuples(index=False):
            counts = json.loads(row.value_counts_json)
            x = np.array([float(value) for value in counts], dtype=float)
            y = np.array(list(counts.values()), dtype=float)
            y = y / y.sum()
            label = (
                f"{row.comparison_role}: run{row.run} sub{row.subrun} "
                f"(median={row.median:g})"
            )
            plt.plot(x, y, marker="o", linewidth=1.8, label=label)
        target = group[group["comparison_role"] == "target"].iloc[0]
        plt.xlabel("Raw event-level nPulses")
        plt.ylabel("Fraction of target-channel events")
        plt.title(
            f"{case}: ch{int(target.channel if 'channel' in target else target.source_target_channel)} "
            "nPulses target vs nearby OK controls"
        )
        plt.xticks(
            sorted(
                {
                    float(value)
                    for raw_counts in group["value_counts_json"]
                    for value in json.loads(raw_counts)
                }
            )
        )
        plt.legend(fontsize=8)
        savefig(PLOTS / f"{case}_npulses_target_vs_controls.png")

    for row in million_df.itertuples(index=False):
        counts = json.loads(row.value_counts_json)
        x = np.array([float(value) for value in counts], dtype=float)
        y = np.array(list(counts.values()), dtype=float)
        plt.figure(figsize=(8, 5))
        plt.bar(x, y, color="#c44e52")
        plt.xlabel("Raw event-level nPulses")
        plt.ylabel("Target-channel event count")
        plt.title(
            f"Run{row.run} sub{row.subrun} ch{row.channel}: "
            f"million-z raw nPulses (median={row.median:g})"
        )
        plt.xticks(x)
        savefig(
            PLOTS
            / f"run{row.run}_subrun{row.subrun}_ch{row.channel}_million_z_npulses.png"
        )

    for filename, group in extreme_channel_df.groupby("filename", sort=False):
        row = group.iloc[0]
        colors = [
            "#c44e52" if flag else "#4c72b0"
            for flag in group["is_target_channel"]
        ]
        plt.figure(figsize=(13, 5))
        plt.bar(
            group["channel"].to_numpy(),
            group["z_nPulses_median"].to_numpy(),
            color=colors,
        )
        plt.axhline(8, color="#222222", linestyle="--")
        plt.axhline(-8, color="#222222", linestyle="--")
        plt.axhline(15, color="#c44e52", linestyle=":")
        plt.axhline(-15, color="#c44e52", linestyle=":")
        plt.yscale("symlog", linthresh=8)
        plt.xlabel("Channel")
        plt.ylabel("z(nPulses_median), symlog")
        plt.title(
            f"Run{int(row['run'])} subrun{int(row['subrun'])}: "
            "all-channel nPulses_median z"
        )
        plt.xticks(range(0, 96, 4))
        savefig(
            PLOTS
            / f"run{int(row['run'])}_subrun{int(row['subrun'])}_all_channel_npulses_z.png"
        )

    for selection_role, group in sideband_raw_df.groupby(
        "selection_role", sort=False
    ):
        plt.figure(figsize=(9, 5.2))
        for row in group.itertuples(index=False):
            raw = get_raw(row.filename)
            values = pd.to_numeric(
                raw[raw["channel"].astype(int) == row.channel][
                    "sideband_rms"
                ],
                errors="coerce",
            )
            values = np.sort(values[np.isfinite(values)].to_numpy())
            y = np.arange(1, len(values) + 1) / len(values)
            plt.step(
                values,
                y,
                where="post",
                linewidth=1.6,
                label=(
                    f"{row.comparison_role}: run{row.run} sub{row.subrun} "
                    f"(mean={row.mean:.2f}, median={row.median:.2f})"
                ),
            )
        target = group[group["comparison_role"] == "target"].iloc[0]
        plt.xscale("log")
        plt.xlabel("Raw event-level sideband_rms (log scale)")
        plt.ylabel("Empirical cumulative fraction")
        plt.title(
            f"{selection_role}: ch{int(target['channel'])} "
            "sideband_rms target vs nearby OK controls"
        )
        plt.legend(fontsize=8)
        savefig(PLOTS / f"{selection_role}_sideband_rms_ecdf.png")

        target_filename = str(target["filename"])
        z_by_channel = sideband_file_metrics[target_filename][
            "z_by_channel"
        ]
        channels = np.array(sorted(z_by_channel), dtype=int)
        z = np.array([z_by_channel[ch] for ch in channels], dtype=float)
        plt.figure(figsize=(13, 5))
        plt.bar(
            channels,
            z,
            color=[
                "#c44e52"
                if ch == int(target["channel"])
                else "#4c72b0"
                for ch in channels
            ],
        )
        plt.axhline(8, color="#222222", linestyle="--")
        plt.axhline(-8, color="#222222", linestyle="--")
        plt.xlabel("Channel")
        plt.ylabel("z(sideband_rms_mean)")
        plt.title(
            f"Run{int(target['run'])} subrun{int(target['subrun'])}: "
            "all-channel sideband_rms_mean z"
        )
        plt.xticks(range(0, 96, 4))
        savefig(
            PLOTS
            / f"{selection_role}_all_channel_sideband_rms_mean_z.png"
        )

    metrics = {
        "active_feature_count": len(active_features),
        "fixed_case_correction": (
            "Run2089 subrun324 ch19 is not an nPulses_median trigger; "
            "it triggers pulseHeight_min_median and pulseArea_min_median. "
            "ch26 is the nPulses_median extreme in that file."
        ),
        "extreme_file_locality": extreme_file_metrics,
        "sideband_selected_targets": selected_sideband,
        "sideband_file_locality": {
            filename: {
                key: value
                for key, value in metrics_for_file.items()
                if key != "z_by_channel"
            }
            for filename, metrics_for_file in sideband_file_metrics.items()
            if filename in {
                target["filename"] for target in selected_sideband
            }
        },
        "raw_files_opened": sorted(raw_cache),
        "n_raw_files_opened": len(raw_cache),
        "n_integrity_issues": int(integrity_df["integrity_issue"].sum()),
        "bulk_context_raw_files_opened": 0,
        "root_files_read": 0,
        "detector_rerun": False,
        "production_inputs_unchanged": True,
    }
    raw_input_paths = [Path(path_by_name[name]) for name in raw_cache]
    production_after = {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in required
    }
    if production_after != production_before:
        fail("authoritative production input changed during diagnosis")
    raw_stats_after_finish = {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in raw_input_paths
    }
    if raw_stats_after_finish != raw_stats_at_open:
        fail("a raw CSV changed during diagnosis")
    with safe_output(OUT / "raw_csv_diagnostic_metrics.json").open(
        "w"
    ) as handle:
        json.dump(json_clean(metrics), handle, indent=2, allow_nan=False)

    print("Run2088/2089 focused raw CSV diagnosis complete.")
    print(json.dumps(json_clean(metrics), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
