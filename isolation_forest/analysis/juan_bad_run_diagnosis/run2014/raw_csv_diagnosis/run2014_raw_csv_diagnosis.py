#!/usr/bin/env python3
"""Focused event-level Digitizer CSV diagnosis for selected run-2014 cases."""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

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
MODEL_DIR = IF_DIR / "models" / TAG
LOG = IF_DIR / "logs" / f"{TAG}.csv"
PATH_CACHE = IF_DIR / "logs" / f"{TAG}_paths.txt"
RUN2014_DIR = (
    IF_DIR / "analysis" / "juan_bad_run_diagnosis" / "run2014"
)
TIMELINE = RUN2014_DIR / "run2014_subrun_timeline.csv"
REPRESENTATIVES = RUN2014_DIR / "run2014_representative_subruns.csv"
OUT = RUN2014_DIR / "raw_csv_diagnosis"
PLOTS = OUT / "plots"
RUN = 2014
Z_THRESHOLD = 8.0

CASES = [
    {
        "case": "A",
        "subrun": 168,
        "target_channel": 4,
        "selection_reason": "largest max_z; test 1e-6 reference-sigma floor",
    },
    {
        "case": "B",
        "subrun": 902,
        "target_channel": 38,
        "selection_reason": "largest n_anomalous_channels representative; max_z 67.36",
    },
    {
        "case": "C",
        "subrun": 3,
        "target_channel": 66,
        "selection_reason": "first strict ALERT; max_z 21.11",
    },
    {
        "case": "D_WARN_ch3",
        "subrun": 605,
        "target_channel": 3,
        "selection_reason": "IF-only WARN comparison",
    },
    {
        "case": "D_WARN_ch82",
        "subrun": 605,
        "target_channel": 82,
        "selection_reason": "IF-only WARN comparison",
    },
    {
        "case": "D_OK_ch3",
        "subrun": 94,
        "target_channel": 3,
        "selection_reason": "nominal OK control for IF-only comparison",
    },
    {
        "case": "D_OK_ch82",
        "subrun": 94,
        "target_channel": 82,
        "selection_reason": "nominal OK control for IF-only comparison",
    },
]
EXTREME_CASES = [
    ("A", 168, 4),
    ("B", 902, 38),
    ("C", 3, 66),
]


def fail(message: str) -> "None":
    raise RuntimeError(f"SANITY CHECK FAILED: {message}")


def as_bool(series: pd.Series, name: str) -> pd.Series:
    if series.dtype == bool:
        return series
    normalized = series.astype(str).str.strip().str.lower()
    if not normalized.isin(["true", "false"]).all():
        fail(f"{name} has invalid boolean values")
    return normalized.eq("true")


def normalize_text(value: object) -> str:
    return "" if pd.isna(value) else str(value)


def safe_output(path: Path) -> Path:
    if OUT not in path.parents and path != OUT:
        fail(f"output attempted outside raw_csv_diagnosis: {path}")
    return path


def savefig(path: Path) -> None:
    safe_output(path)
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()


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


def reference_arrays(reference, channel: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    state = reference._state[channel]
    mean = state["mean"].copy()
    if state["count"] > 1:
        pre_floor_std = np.sqrt(state["M2"] / state["count"])
    else:
        pre_floor_std = np.ones_like(mean)
    _, used_std = reference.get_stats(channel)
    return mean, pre_floor_std, used_std


def file_window(
    timeline: pd.DataFrame, sequence_index: int
) -> tuple[list[str], list[str]]:
    names = timeline["filename"].tolist()
    previous = names[max(0, sequence_index - 2) : sequence_index]
    following = names[sequence_index + 1 : sequence_index + 3]
    return previous, following


def raw_metric_from_feature(
    feature: str, metric_cols: list[str]
) -> Optional[str]:
    for suffix in ("_mean", "_std", "_median"):
        if feature.endswith(suffix):
            candidate = feature[: -len(suffix)]
            if candidate in metric_cols:
                return candidate
    return None


def event_metric_summary(
    df: pd.DataFrame,
    channel: int,
    metric: str,
) -> dict[str, object]:
    channel_df = df[df["channel"] == channel]
    values = pd.to_numeric(channel_df[metric], errors="coerce")
    finite = values[np.isfinite(values)]
    n_file_events = int(df["event_id"].nunique())
    n_channel_events = int(channel_df["event_id"].nunique())
    result = {
        "file_unique_events": n_file_events,
        "target_channel_rows": int(len(channel_df)),
        "target_channel_unique_events": n_channel_events,
        "occupancy": n_channel_events / n_file_events if n_file_events else np.nan,
        "n_values": int(len(values)),
        "n_nan": int(values.isna().sum()),
        "n_inf": int(np.isinf(values).sum()),
        "min": float(finite.min()) if len(finite) else np.nan,
        "max": float(finite.max()) if len(finite) else np.nan,
        "mean": float(finite.mean()) if len(finite) else np.nan,
        "std": float(finite.std(ddof=1)) if len(finite) > 1 else 0.0,
        "median": float(finite.median()) if len(finite) else np.nan,
        "q25": float(finite.quantile(0.25)) if len(finite) else np.nan,
        "q75": float(finite.quantile(0.75)) if len(finite) else np.nan,
    }
    if metric == "nPulses":
        zero_count = int((finite == 0).sum())
        result["n_equal_zero"] = zero_count
        result["fraction_equal_zero"] = (
            zero_count / len(finite) if len(finite) else np.nan
        )
        counts = finite.value_counts().sort_index()
        result["value_counts_json"] = json.dumps(
            {str(value): int(count) for value, count in counts.items()}
        )
    return result


def plot_npulses(
    values: pd.Series,
    case: str,
    channel: int,
    subrun: int,
    role: str,
    status: str,
) -> None:
    finite = pd.to_numeric(values, errors="coerce")
    finite = finite[np.isfinite(finite)]
    counts = finite.value_counts().sort_index()
    plt.figure(figsize=(9, 5))
    plt.bar(
        counts.index.astype(str).to_numpy(),
        counts.to_numpy(),
        color="#4c72b0" if role != "target" else "#c44e52",
    )
    plt.xlabel("Raw event-level nPulses")
    plt.ylabel("Rows/events for target channel")
    plt.title(
        f"Case {case}: run2014 subrun{subrun} ch{channel} nPulses\n"
        f"{role}, strict status {status}"
    )
    plt.xticks(rotation=45)
    safe_role = role.replace(" ", "_")
    savefig(
        PLOTS
        / f"case_{case}_ch{channel}_{safe_role}_subrun{subrun}_npulses.png"
    )


def main() -> None:
    sys.path.insert(0, str(IF_DIR))
    from src.detector import AnomalyDetector
    from src.features import METRIC_COLS
    from src.reference import ReferenceModel
    from src.run_list import parse_run_subrun

    required = [
        MODEL_DIR / "reference.npz",
        MODEL_DIR / "detector.pkl",
        MODEL_DIR / "config.yaml",
        MODEL_DIR / "training_metadata.json",
        LOG,
        PATH_CACHE,
        TIMELINE,
        REPRESENTATIVES,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        fail(f"required inputs missing: {missing}")
    if OUT.exists():
        unexpected = [
            path
            for path in OUT.rglob("*")
            if path.is_file() and path.name != "run2014_raw_csv_diagnosis.py"
        ]
        if unexpected:
            fail(f"output directory is not new/empty: {unexpected}")

    production_stats_before = {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in required
    }

    reference = ReferenceModel.load(str(MODEL_DIR / "reference.npz"))
    detector = AnomalyDetector.load(
        str(MODEL_DIR / "detector.pkl"), reference
    )
    if detector.z_threshold != Z_THRESHOLD:
        fail(f"detector z threshold is {detector.z_threshold}, not 8")
    active_features = list(reference._feat_cols)
    expected_active = [
        feature
        for feature in active_features
        if not feature.startswith("TDC")
    ]
    if active_features != expected_active:
        fail("trained reference unexpectedly contains active TDC* features")

    timeline = pd.read_csv(TIMELINE).sort_values("sequence_index").reset_index(
        drop=True
    )
    if (
        len(timeline) != 361
        or timeline["sequence_index"].tolist() != list(range(361))
        or timeline["strict_status"].value_counts().to_dict()
        != {"OK": 213, "WARN": 77, "ALERT": 71}
    ):
        fail("authoritative run2014 timeline does not reproduce 361/213/77/71")
    status_by_name = timeline.set_index("filename")["strict_status"].to_dict()
    sequence_by_name = timeline.set_index("filename")["sequence_index"].to_dict()

    paths = [
        path
        for path in PATH_CACHE.read_text().splitlines()
        if parse_run_subrun(path)[0] == RUN
    ]
    if len(paths) != 361:
        fail(f"successful path cache has {len(paths)} run2014 paths")
    path_by_name = {Path(path).name: path for path in paths}
    if list(path_by_name) != timeline["filename"].tolist():
        fail("timeline order differs from successful path cache")

    log = pd.read_csv(LOG)
    log = log[log["filename"].isin(timeline["filename"])].copy()
    log["anomalous"] = as_bool(log["anomalous"], "anomalous")
    if log.duplicated(["filename", "channel"]).any():
        fail("duplicate filename/channel rows in run2014 anomaly log")
    log_index = log.set_index(["filename", "channel"])

    # Verify representative file identities before constructing the case manifest.
    rep = pd.read_csv(REPRESENTATIVES)
    expected_representative_subruns = {3, 94, 168, 605, 902}
    if set(rep["subrun"]) != expected_representative_subruns:
        fail(
            f"representative subruns {set(rep['subrun'])} "
            f"!= {expected_representative_subruns}"
        )

    case_manifest_rows: list[dict[str, object]] = []
    reconstruction_rows: list[dict[str, object]] = []
    detector_cache: dict[str, pd.DataFrame] = {}
    feature_cache: dict[str, pd.DataFrame] = {}

    for case in CASES:
        subrun = case["subrun"]
        channel = case["target_channel"]
        timeline_row = timeline[timeline["subrun"] == subrun]
        if len(timeline_row) != 1:
            fail(f"expected one timeline row for subrun {subrun}")
        timeline_row = timeline_row.iloc[0]
        filename = str(timeline_row["filename"])
        sequence_index = int(timeline_row["sequence_index"])
        previous, following = file_window(timeline, sequence_index)
        filepath = path_by_name[filename]
        if not Path(filepath).is_file():
            fail(f"case file is missing: {filepath}")

        if filename not in feature_cache:
            feature_cache[filename] = canonical_features(filepath, reference)
            detector_cache[filename] = detector.analyze_file(filepath)
        features = feature_cache[filename]
        result = detector_cache[filename]
        if channel not in features.index or channel not in result.index:
            fail(f"target channel {channel} absent from canonical result {filename}")

        log_row = log_index.loc[(filename, channel)]
        detector_row = result.loc[channel]
        observed = features.loc[channel, active_features].to_numpy(dtype=float)
        mean, pre_floor_std, used_std = reference_arrays(reference, channel)
        exact_z = (observed - mean) / used_std
        exact_max_z = float(np.nanmax(np.abs(exact_z)))
        triggered = [
            feature
            for feature, z_value in zip(active_features, exact_z)
            if abs(z_value) > Z_THRESHOLD
        ]

        if round(exact_max_z, 2) != float(detector_row["max_z"]):
            fail(
                f"exact max-z does not reproduce detector for {filename}/ch{channel}"
            )
        if float(detector_row["max_z"]) != float(log_row["max_z"]):
            fail(f"detector max-z does not match log for {filename}/ch{channel}")
        if normalize_text(detector_row["method"]) != normalize_text(
            log_row["method"]
        ):
            fail(f"detector method does not match log for {filename}/ch{channel}")
        if normalize_text(detector_row["triggered_features"]) != normalize_text(
            log_row["triggered_features"]
        ):
            fail(
                f"detector triggered features do not match log for "
                f"{filename}/ch{channel}"
            )
        if not np.isclose(
            float(detector_row["if_score"]),
            float(log_row["if_score"]),
            atol=5e-5,
            rtol=0,
        ):
            fail(f"detector IF score does not match log for {filename}/ch{channel}")

        case_manifest_rows.append(
            {
                "case": case["case"],
                "filepath": filepath,
                "filename": filename,
                "subrun": subrun,
                "sequence_index": sequence_index,
                "status": timeline_row["strict_status"],
                "target_channel": channel,
                "selection_reason": case["selection_reason"],
                "target_anomalous": bool(log_row["anomalous"]),
                "target_method": normalize_text(log_row["method"]),
                "target_triggered_features": normalize_text(
                    log_row["triggered_features"]
                ),
                "target_max_z_log": float(log_row["max_z"]),
                "target_if_score_log": float(log_row["if_score"]),
                "previous_processed_files": ";".join(previous),
                "next_processed_files": ";".join(following),
            }
        )

        for index, feature in enumerate(active_features):
            reconstruction_rows.append(
                {
                    "case": case["case"],
                    "filename": filename,
                    "subrun": subrun,
                    "status": timeline_row["strict_status"],
                    "target_channel": channel,
                    "feature": feature,
                    "observed_value": observed[index],
                    "reference_mean": mean[index],
                    "reference_std_pre_floor": pre_floor_std[index],
                    "reference_std_used": used_std[index],
                    "std_floor_applied": bool(pre_floor_std[index] < 1e-6),
                    "z_score": exact_z[index],
                    "abs_z": abs(exact_z[index]),
                    "triggered_by_z_threshold": abs(exact_z[index])
                    > Z_THRESHOLD,
                    "canonical_max_z_exact": exact_max_z,
                    "canonical_max_z_rounded": float(detector_row["max_z"]),
                    "canonical_method": normalize_text(detector_row["method"]),
                    "canonical_if_score": float(detector_row["if_score"]),
                }
            )

    case_manifest = pd.DataFrame(case_manifest_rows)
    reconstruction = pd.DataFrame(reconstruction_rows)

    # Explicitly validate the three extreme cases and the million-z hypothesis.
    expected_extreme = {
        ("A", 4): ("nPulses_median", 1_000_000.0),
        ("B", 38): ("nPulses_median", 67.36),
        ("C", 66): ("nPulses_median", 21.11),
    }
    million_floor_details: dict[str, object] = {}
    for (case_name, channel), (expected_feature, expected_rounded_z) in expected_extreme.items():
        group = reconstruction[
            (reconstruction["case"] == case_name)
            & (reconstruction["target_channel"] == channel)
        ]
        worst = group.sort_values("abs_z", ascending=False).iloc[0]
        if worst["feature"] != expected_feature:
            fail(
                f"case {case_name}/ch{channel} worst feature "
                f"{worst['feature']} != {expected_feature}"
            )
        if float(worst["canonical_max_z_rounded"]) != expected_rounded_z:
            fail(
                f"case {case_name}/ch{channel} max-z "
                f"{worst['canonical_max_z_rounded']} != {expected_rounded_z}"
            )
        if case_name == "A":
            if not bool(worst["std_floor_applied"]):
                fail("case A million-z feature did not use the 1e-6 std floor")
            reconstructed = (
                float(worst["observed_value"])
                - float(worst["reference_mean"])
            ) / float(worst["reference_std_used"])
            if not np.isclose(reconstructed, float(worst["z_score"])):
                fail("case A numerical z reconstruction is inconsistent")
            million_floor_details = {
                key: (
                    bool(worst[key])
                    if key == "std_floor_applied"
                    else str(worst[key])
                    if key == "feature"
                    else float(worst[key])
                )
                for key in [
                    "feature",
                    "observed_value",
                    "reference_mean",
                    "reference_std_pre_floor",
                    "reference_std_used",
                    "std_floor_applied",
                    "z_score",
                    "abs_z",
                ]
            }

    # All canonical reconstruction/log checks passed. New analysis-only output
    # may now be created under the dedicated directory.
    OUT.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    # Read raw files lazily and cache only this small selected set.
    raw_cache: dict[str, pd.DataFrame] = {}

    def raw_file(filename: str) -> pd.DataFrame:
        if filename not in raw_cache:
            filepath = path_by_name[filename]
            raw_cache[filename] = pd.read_csv(filepath)
        return raw_cache[filename]

    # Part 3: event-level nPulses for target, all ±2 neighbors, and 3 nearest OK controls.
    npulses_summary_rows: list[dict[str, object]] = []
    npulses_value_count_rows: list[dict[str, object]] = []
    plotted_contexts: set[tuple[str, str]] = set()
    extreme_contexts: dict[str, list[dict[str, object]]] = {}

    for case_name, target_subrun, channel in EXTREME_CASES:
        target_row = timeline[timeline["subrun"] == target_subrun].iloc[0]
        target_name = str(target_row["filename"])
        target_seq = int(target_row["sequence_index"])
        contexts: list[dict[str, object]] = [
            {
                "filename": target_name,
                "role": "target",
                "distance": 0,
            }
        ]
        for offset in [-2, -1, 1, 2]:
            index = target_seq + offset
            if 0 <= index < len(timeline):
                contexts.append(
                    {
                        "filename": str(timeline.iloc[index]["filename"]),
                        "role": (
                            f"previous_{abs(offset)}"
                            if offset < 0
                            else f"next_{offset}"
                        ),
                        "distance": offset,
                    }
                )
        existing_names = {context["filename"] for context in contexts}
        nearest_ok = (
            timeline[
                timeline["strict_status"].eq("OK")
                & ~timeline["filename"].isin(existing_names)
            ]
            .assign(
                _distance=lambda frame: (
                    frame["sequence_index"] - target_seq
                ).abs()
            )
            .sort_values(["_distance", "sequence_index"])
            .head(3)
        )
        for control_number, row in enumerate(nearest_ok.itertuples(), start=1):
            contexts.append(
                {
                    "filename": row.filename,
                    "role": f"nearby_OK_{control_number}",
                    "distance": int(row.sequence_index - target_seq),
                }
            )
        extreme_contexts[case_name] = contexts

        # Plot target + nearest previous/next + nearest distinct OK.
        plot_roles = {"target", "previous_1", "next_1", "nearby_OK_1"}
        for context in contexts:
            filename = str(context["filename"])
            df = raw_file(filename)
            subrun = int(parse_run_subrun(filename)[1])
            summary = event_metric_summary(df, channel, "nPulses")
            npulses_summary_rows.append(
                {
                    "case": case_name,
                    "target_subrun": target_subrun,
                    "target_channel": channel,
                    "comparison_filename": filename,
                    "comparison_subrun": subrun,
                    "comparison_sequence_index": int(
                        sequence_by_name[filename]
                    ),
                    "comparison_status": status_by_name[filename],
                    "comparison_role": context["role"],
                    "processed_sequence_offset": context["distance"],
                    **summary,
                }
            )
            channel_values = pd.to_numeric(
                df.loc[df["channel"] == channel, "nPulses"], errors="coerce"
            )
            value_counts = channel_values.value_counts().sort_index()
            for value, count in value_counts.items():
                npulses_value_count_rows.append(
                    {
                        "case": case_name,
                        "target_channel": channel,
                        "comparison_filename": filename,
                        "comparison_subrun": subrun,
                        "comparison_role": context["role"],
                        "nPulses_value": value,
                        "count": int(count),
                        "fraction": count / len(channel_values)
                        if len(channel_values)
                        else np.nan,
                    }
                )
            if (
                context["role"] in plot_roles
                and (case_name, filename) not in plotted_contexts
            ):
                plot_npulses(
                    channel_values,
                    case_name,
                    channel,
                    subrun,
                    str(context["role"]),
                    status_by_name[filename],
                )
                plotted_contexts.add((case_name, filename))

    npulses_summary = pd.DataFrame(npulses_summary_rows)
    npulses_value_counts = pd.DataFrame(npulses_value_count_rows)

    # Part 4: lightweight all-channel view for each target extreme file.
    extreme_channel_rows: list[dict[str, object]] = []
    for case_name, target_subrun, target_channel in EXTREME_CASES:
        filename = str(
            timeline[timeline["subrun"] == target_subrun].iloc[0]["filename"]
        )
        filepath = path_by_name[filename]
        features = feature_cache.get(filename)
        if features is None:
            features = canonical_features(filepath, reference)
            feature_cache[filename] = features
        z_frame = reference.z_score(features)
        real_channels = [
            channel for channel in features.index if isinstance(channel, int)
        ]
        for channel in real_channels:
            z_value = float(z_frame.loc[channel, "nPulses_median"])
            extreme_channel_rows.append(
                {
                    "case": case_name,
                    "filename": filename,
                    "subrun": target_subrun,
                    "target_channel": target_channel,
                    "channel": channel,
                    "nPulses_mean": float(
                        features.loc[channel, "nPulses_mean"]
                    ),
                    "nPulses_median": float(
                        features.loc[channel, "nPulses_median"]
                    ),
                    "nPulses_std": float(
                        features.loc[channel, "nPulses_std"]
                    ),
                    "occupancy": float(features.loc[channel, "occupancy"]),
                    "frac_dead": float(features.loc[channel, "frac_dead"]),
                    "z_nPulses_median": z_value,
                    "abs_z_nPulses_median": abs(z_value),
                    "above_z8": abs(z_value) > 8,
                    "above_z15": abs(z_value) >= 15,
                    "is_target_channel": channel == target_channel,
                }
            )
        case_frame = pd.DataFrame(
            [
                row
                for row in extreme_channel_rows
                if row["case"] == case_name
            ]
        ).sort_values("channel")
        colors = np.where(
            case_frame["is_target_channel"],
            "#c44e52",
            np.where(case_frame["above_z15"], "#dd8452", "#4c72b0"),
        )
        plt.figure(figsize=(15, 5))
        plt.bar(
            case_frame["channel"].astype(str).to_numpy(),
            case_frame["z_nPulses_median"].to_numpy(),
            color=colors,
        )
        plt.axhline(8, color="black", ls="--", lw=1, label="|z| = 8")
        plt.axhline(-8, color="black", ls="--", lw=1)
        plt.axhline(15, color="#c44e52", ls=":", lw=1.2, label="|z| = 15")
        plt.axhline(-15, color="#c44e52", ls=":", lw=1.2)
        plt.yscale("symlog", linthresh=8)
        plt.xlabel("Channel")
        plt.ylabel("z(nPulses_median)")
        plt.title(
            f"Case {case_name}: run2014 subrun{target_subrun} "
            "all-channel nPulses_median z"
        )
        plt.xticks(rotation=90, fontsize=7)
        plt.legend()
        savefig(
            PLOTS
            / f"case_{case_name}_subrun{target_subrun}_all_channel_npulses_median_z.png"
        )
    extreme_channel_summary = pd.DataFrame(extreme_channel_rows)

    # Part 5: ch3/ch82 full active-feature comparison and selected raw metrics.
    warn_name = str(timeline[timeline["subrun"] == 605].iloc[0]["filename"])
    ok_name = str(timeline[timeline["subrun"] == 94].iloc[0]["filename"])
    warn_features = feature_cache[warn_name]
    ok_features = feature_cache[ok_name]
    warn_z = reference.z_score(warn_features)
    ok_z = reference.z_score(ok_features)
    warn_result = detector_cache[warn_name]
    ok_result = detector_cache[ok_name]

    if_comparison_rows: list[dict[str, object]] = []
    selected_metrics: dict[int, list[str]] = {}
    for channel in [3, 82]:
        mean, pre_floor_std, used_std = reference_arrays(reference, channel)
        rows_for_channel: list[dict[str, object]] = []
        for index, feature in enumerate(active_features):
            warn_value = float(warn_features.loc[channel, feature])
            ok_value = float(ok_features.loc[channel, feature])
            warn_z_value = float(warn_z.loc[channel, feature])
            ok_z_value = float(ok_z.loc[channel, feature])
            rows_for_channel.append(
                {
                    "channel": channel,
                    "feature": feature,
                    "subrun605_value": warn_value,
                    "subrun94_value": ok_value,
                    "reference_mean": mean[index],
                    "reference_std_pre_floor": pre_floor_std[index],
                    "reference_std_used": used_std[index],
                    "subrun605_z": warn_z_value,
                    "subrun94_z": ok_z_value,
                    "value_delta_605_minus_94": warn_value - ok_value,
                    "z_movement_605_minus_94": warn_z_value - ok_z_value,
                    "abs_z_movement": abs(warn_z_value - ok_z_value),
                    "max_abs_z_across_pair": max(
                        abs(warn_z_value), abs(ok_z_value)
                    ),
                    "subrun605_over_z8": abs(warn_z_value) > Z_THRESHOLD,
                    "subrun94_over_z8": abs(ok_z_value) > Z_THRESHOLD,
                    "subrun605_method": normalize_text(
                        warn_result.loc[channel, "method"]
                    ),
                    "subrun94_method": normalize_text(
                        ok_result.loc[channel, "method"]
                    ),
                    "subrun605_if_score": float(
                        warn_result.loc[channel, "if_score"]
                    ),
                    "subrun94_if_score": float(
                        ok_result.loc[channel, "if_score"]
                    ),
                }
            )
        rows_for_channel.sort(
            key=lambda row: (
                row["abs_z_movement"],
                row["max_abs_z_across_pair"],
            ),
            reverse=True,
        )
        for rank, row in enumerate(rows_for_channel, start=1):
            row["difference_rank_within_channel"] = rank
            if_comparison_rows.append(row)
        metric_ranking: list[str] = []
        for row in rows_for_channel:
            metric = raw_metric_from_feature(row["feature"], METRIC_COLS)
            if metric and metric not in metric_ranking:
                metric_ranking.append(metric)
            if len(metric_ranking) >= 5:
                break
        selected_metrics[channel] = metric_ranking

    if_comparison = pd.DataFrame(if_comparison_rows)
    for channel in [3, 82]:
        warn_row = warn_result.loc[channel]
        ok_row = ok_result.loc[channel]
        expected_warn_method = "" if channel == 3 else "isolation_forest"
        if normalize_text(warn_row["method"]) != expected_warn_method:
            fail(
                f"subrun605 ch{channel} method "
                f"{normalize_text(warn_row['method'])!r} != "
                f"{expected_warn_method!r}"
            )
        expected_warn_anomalous = channel == 82
        if bool(warn_row["anomalous"]) != expected_warn_anomalous:
            fail(
                f"subrun605 ch{channel} anomalous flag does not match "
                f"verified case premise"
            )
        if bool(
            if_comparison[
                (if_comparison["channel"] == channel)
                & if_comparison["subrun605_over_z8"]
            ].shape[0]
        ):
            fail(f"subrun605 ch{channel} unexpectedly has |z| > 8")
        if bool(
            if_comparison[
                (if_comparison["channel"] == channel)
                & if_comparison["subrun94_over_z8"]
            ].shape[0]
        ):
            fail(f"subrun94 ch{channel} unexpectedly has |z| > 8")
        if bool(ok_row["anomalous"]):
            fail(f"subrun94 ch{channel} is unexpectedly anomalous")

    if_event_rows: list[dict[str, object]] = []
    if_plot_pairs: list[tuple[int, str]] = []
    for channel in [3, 82]:
        for metric in selected_metrics[channel]:
            if len(if_plot_pairs) < 6:
                if_plot_pairs.append((channel, metric))
        contexts = []
        for target_name, target_label in [
            (warn_name, "WARN_target"),
            (ok_name, "OK_target"),
        ]:
            target_seq = int(sequence_by_name[target_name])
            contexts.append((target_name, target_label, 0))
            for offset, neighbor_label in [
                (-2, "previous_2"),
                (-1, "previous_1"),
                (1, "next_1"),
                (2, "next_2"),
            ]:
                index = target_seq + offset
                if 0 <= index < len(timeline):
                    neighbor_name = str(timeline.iloc[index]["filename"])
                    contexts.append(
                        (
                            neighbor_name,
                            f"{target_label}_{neighbor_label}",
                            offset,
                        )
                    )
        seen_contexts = set()
        unique_contexts = []
        for context in contexts:
            if context[0] not in seen_contexts:
                unique_contexts.append(context)
                seen_contexts.add(context[0])
        for metric in selected_metrics[channel]:
            for filename, role, offset in unique_contexts:
                df = raw_file(filename)
                summary = event_metric_summary(df, channel, metric)
                if_event_rows.append(
                    {
                        "channel": channel,
                        "source_metric": metric,
                        "comparison_filename": filename,
                        "comparison_subrun": int(
                            parse_run_subrun(filename)[1]
                        ),
                        "comparison_status": status_by_name[filename],
                        "comparison_role": role,
                        "processed_sequence_offset_from_role_target": offset,
                        **summary,
                    }
                )

    if_event_summary = pd.DataFrame(if_event_rows)

    # Only plot the top three selected raw metrics for each channel.
    for channel in [3, 82]:
        for metric in selected_metrics[channel][:3]:
            warn_df = raw_file(warn_name)
            ok_df = raw_file(ok_name)
            warn_values = pd.to_numeric(
                warn_df.loc[warn_df["channel"] == channel, metric],
                errors="coerce",
            )
            ok_values = pd.to_numeric(
                ok_df.loc[ok_df["channel"] == channel, metric],
                errors="coerce",
            )
            warn_values = warn_values[np.isfinite(warn_values)]
            ok_values = ok_values[np.isfinite(ok_values)]
            plt.figure(figsize=(9, 5))
            if metric == "nPulses":
                all_values = sorted(set(warn_values) | set(ok_values))
                positions = np.arange(len(all_values))
                warn_counts = warn_values.value_counts().reindex(
                    all_values, fill_value=0
                )
                ok_counts = ok_values.value_counts().reindex(
                    all_values, fill_value=0
                )
                width = 0.4
                plt.bar(
                    positions - width / 2,
                    warn_counts.to_numpy(),
                    width,
                    label="WARN subrun605",
                    color="#dd8452",
                )
                plt.bar(
                    positions + width / 2,
                    ok_counts.to_numpy(),
                    width,
                    label="OK subrun94",
                    color="#4c72b0",
                )
                plt.xticks(positions, [str(value) for value in all_values])
                plt.ylabel("Count")
            else:
                combined = np.concatenate(
                    [warn_values.to_numpy(), ok_values.to_numpy()]
                )
                bins = np.histogram_bin_edges(combined, bins="auto")
                plt.hist(
                    warn_values,
                    bins=bins,
                    histtype="step",
                    linewidth=2,
                    label="WARN subrun605",
                    color="#dd8452",
                )
                plt.hist(
                    ok_values,
                    bins=bins,
                    histtype="step",
                    linewidth=2,
                    label="OK subrun94",
                    color="#4c72b0",
                )
                plt.ylabel("Count")
            plt.xlabel(f"Raw event-level {metric}")
            plt.title(
                f"IF-only comparison ch{channel}: {metric}\n"
                "WARN subrun605 versus OK subrun94"
            )
            plt.legend()
            savefig(
                PLOTS
                / f"if_only_ch{channel}_{metric}_subrun605_vs_subrun94.png"
            )

    # Part 6: integrity of the five representative target files.
    integrity_rows: list[dict[str, object]] = []
    target_channels_by_subrun = {
        168: [4],
        902: [38],
        3: [66],
        605: [3, 82],
        94: [3, 82],
    }
    representative_names = []
    for subrun in [168, 902, 3, 605, 94]:
        filename = str(timeline[timeline["subrun"] == subrun].iloc[0]["filename"])
        representative_names.append(filename)
        filepath = path_by_name[filename]
        df = raw_file(filename)
        numeric_relevant = df[METRIC_COLS].apply(
            pd.to_numeric, errors="coerce"
        )
        events = int(df["event_id"].nunique())
        channels = sorted(int(value) for value in df["channel"].unique())
        per_event = df.groupby("event_id")["channel"].nunique()
        duplicate_pairs = int(df.duplicated(["event_id", "channel"]).sum())
        missing_targets = [
            channel
            for channel in target_channels_by_subrun[subrun]
            if channel not in channels
        ]
        integrity_rows.append(
            {
                "filename": filename,
                "filepath": filepath,
                "subrun": subrun,
                "status": status_by_name[filename],
                "file_exists": Path(filepath).is_file(),
                "file_readable": True,
                "file_size_bytes": Path(filepath).stat().st_size,
                "row_count": int(len(df)),
                "unique_event_count": events,
                "unique_channel_count": len(channels),
                "channel_ids_present": ";".join(
                    str(channel) for channel in channels
                ),
                "target_channels": ";".join(
                    str(channel)
                    for channel in target_channels_by_subrun[subrun]
                ),
                "missing_target_channels": ";".join(
                    str(channel) for channel in missing_targets
                ),
                "duplicate_event_channel_rows": duplicate_pairs,
                "nan_count_relevant_raw_columns": int(
                    numeric_relevant.isna().sum().sum()
                ),
                "inf_count_relevant_raw_columns": int(
                    np.isinf(numeric_relevant.to_numpy()).sum()
                ),
                "mean_channels_per_event": float(per_event.mean()),
                "min_channels_per_event": int(per_event.min())
                if len(per_event)
                else 0,
                "max_channels_per_event": int(per_event.max())
                if len(per_event)
                else 0,
                "empty_or_truncated": len(df) == 0 or events == 0,
            }
        )
    integrity = pd.DataFrame(integrity_rows)
    median_rows = float(integrity["row_count"].median())
    median_events = float(integrity["unique_event_count"].median())
    integrity["row_count_ratio_to_representative_median"] = (
        integrity["row_count"] / median_rows
    )
    integrity["event_count_ratio_to_representative_median"] = (
        integrity["unique_event_count"] / median_events
    )
    integrity["strongly_low_coverage"] = (
        integrity["row_count_ratio_to_representative_median"] < 0.5
    ) | (integrity["event_count_ratio_to_representative_median"] < 0.5)
    integrity["integrity_issue"] = (
        ~integrity["file_exists"]
        | ~integrity["file_readable"]
        | integrity["empty_or_truncated"]
        | integrity["missing_target_channels"].ne("")
        | integrity["nan_count_relevant_raw_columns"].gt(0)
        | integrity["inf_count_relevant_raw_columns"].gt(0)
        | integrity["duplicate_event_channel_rows"].gt(0)
    )

    # Derived compact metrics for human synthesis.
    target_npulses = npulses_summary[
        npulses_summary["comparison_role"].eq("target")
    ].copy()
    broadness = {}
    for case_name, target_subrun, target_channel in EXTREME_CASES:
        frame = extreme_channel_summary[
            extreme_channel_summary["case"] == case_name
        ]
        broadness[case_name] = {
            "subrun": target_subrun,
            "target_channel": target_channel,
            "n_channels_over_z8": int(frame["above_z8"].sum()),
            "n_channels_over_z15": int(frame["above_z15"].sum()),
            "channels_over_z8": [
                int(value)
                for value in frame.loc[frame["above_z8"], "channel"]
            ],
            "channels_over_z15": [
                int(value)
                for value in frame.loc[frame["above_z15"], "channel"]
            ],
        }
    if_top_differences = {}
    for channel in [3, 82]:
        frame = if_comparison[
            if_comparison["channel"] == channel
        ].sort_values("difference_rank_within_channel")
        if_top_differences[str(channel)] = frame.head(10)[
            [
                "feature",
                "subrun605_value",
                "subrun94_value",
                "subrun605_z",
                "subrun94_z",
                "z_movement_605_minus_94",
            ]
        ].to_dict("records")

    metrics = {
        "active_feature_count": len(active_features),
        "active_features": active_features,
        "million_z_floor_details": million_floor_details,
        "target_npulses_summaries": target_npulses.replace(
            {np.nan: None}
        ).to_dict("records"),
        "extreme_broadness": broadness,
        "if_only": {
            "verified_case_note": (
                "subrun605 ch82 is IF-only anomalous; ch3 is nominal in "
                "subrun605, contrary to the initial prompt premise"
            ),
            "ch3_subrun605_method": normalize_text(
                warn_result.loc[3, "method"]
            ),
            "ch3_subrun94_method": normalize_text(ok_result.loc[3, "method"]),
            "ch82_subrun605_method": normalize_text(
                warn_result.loc[82, "method"]
            ),
            "ch82_subrun94_method": normalize_text(
                ok_result.loc[82, "method"]
            ),
            "ch3_subrun605_if_score": float(
                warn_result.loc[3, "if_score"]
            ),
            "ch3_subrun94_if_score": float(ok_result.loc[3, "if_score"]),
            "ch82_subrun605_if_score": float(
                warn_result.loc[82, "if_score"]
            ),
            "ch82_subrun94_if_score": float(ok_result.loc[82, "if_score"]),
            "selected_source_metrics": {
                str(channel): metrics_list
                for channel, metrics_list in selected_metrics.items()
            },
            "top_feature_differences": if_top_differences,
        },
        "integrity": integrity.replace({np.nan: None}).to_dict("records"),
        "provenance": {
            "model": str(MODEL_DIR),
            "log": str(LOG),
            "processed_path_cache": str(PATH_CACHE),
            "timeline": str(TIMELINE),
        },
    }

    # All reconstruction and reproduction checks passed before writing.
    case_manifest.to_csv(OUT / "case_manifest.csv", index=False)
    reconstruction.sort_values(
        ["case", "target_channel", "abs_z"], ascending=[True, True, False]
    ).to_csv(OUT / "target_feature_reconstruction.csv", index=False)
    npulses_summary.to_csv(
        OUT / "extreme_npulses_event_summary.csv", index=False
    )
    npulses_value_counts.to_csv(
        OUT / "extreme_npulses_value_counts.csv", index=False
    )
    extreme_channel_summary.sort_values(
        ["case", "abs_z_nPulses_median"], ascending=[True, False]
    ).to_csv(OUT / "extreme_file_channel_summary.csv", index=False)
    if_comparison.sort_values(
        ["channel", "difference_rank_within_channel"]
    ).to_csv(
        OUT / "if_only_ch3_ch82_feature_comparison.csv", index=False
    )
    if_event_summary.to_csv(
        OUT / "if_only_ch3_ch82_event_summary.csv", index=False
    )
    integrity.to_csv(OUT / "representative_file_integrity.csv", index=False)
    (OUT / "raw_csv_diagnostic_metrics.json").write_text(
        json.dumps(metrics, indent=2, allow_nan=False)
    )

    production_stats_after = {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in required
    }
    if production_stats_after != production_stats_before:
        changed = [
            path
            for path in production_stats_before
            if production_stats_before[path] != production_stats_after[path]
        ]
        fail(f"production inputs changed during analysis: {changed}")

    print("Focused run2014 raw Digitizer CSV diagnosis complete.")
    print(f"Active canonical feature count: {len(active_features)}")
    print("\nMillion-z reconstruction:")
    print(json.dumps(million_floor_details, indent=2))
    print("\nTarget event-level nPulses summaries:")
    print(
        target_npulses[
            [
                "case",
                "target_subrun",
                "target_channel",
                "file_unique_events",
                "target_channel_unique_events",
                "occupancy",
                "n_equal_zero",
                "fraction_equal_zero",
                "min",
                "max",
                "mean",
                "std",
                "median",
                "value_counts_json",
            ]
        ].to_string(index=False)
    )
    print("\nExtreme-file breadth:")
    print(json.dumps(broadness, indent=2))
    print("\nIF-only scores:")
    print(json.dumps(metrics["if_only"], indent=2))
    print("\nIntegrity:")
    print(integrity.to_string(index=False))
    print(f"\nOutputs: {OUT}")


if __name__ == "__main__":
    main()
