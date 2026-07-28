#!/usr/bin/env python3
"""Focused diagnosis of the 18 run-2014 bulk-only ALERT files."""

from __future__ import annotations

import itertools
import json
import math
import sys
from collections import Counter
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
RUN_DIR = (
    IF_DIR / "analysis" / "juan_bad_run_diagnosis" / "run2014"
)
OUT = RUN_DIR / "bulk_only_diagnosis"
PLOTS = OUT / "plots"
TIMELINE = RUN_DIR / "run2014_subrun_timeline.csv"
CLASSIFICATION = (
    IF_DIR
    / "analysis"
    / "juan_bad_run_diagnosis"
    / "step1_classification"
    / "subrun_classification.csv"
)
LOG = IF_DIR / "logs" / f"{TAG}.csv"
PATH_CACHE = IF_DIR / "logs" / f"{TAG}_paths.txt"
MODEL_DIR = IF_DIR / "models" / TAG
RUN = 2014
METHOD_ORDER = [
    "statistical",
    "isolation_forest",
    "statistical+IF",
    "missing_channel",
    "new_channel",
    "other",
]
SEGMENTS = [
    ("0-90", 0, 90),
    ("91-180", 91, 180),
    ("181-270", 181, 270),
    ("271-360", 271, 360),
]


def fail(message: str) -> "None":
    raise RuntimeError(f"SANITY CHECK FAILED: {message}")


def as_bool(series: pd.Series, name: str) -> pd.Series:
    if series.dtype == bool:
        return series
    normalized = series.astype(str).str.strip().str.lower()
    if not normalized.isin(["true", "false"]).all():
        fail(f"{name} contains non-boolean values")
    return normalized.eq("true")


def safe_output(path: Path) -> Path:
    if path != OUT and OUT not in path.parents:
        fail(f"attempted output outside bulk_only_diagnosis: {path}")
    return path


def savefig(path: Path) -> None:
    safe_output(path)
    plt.savefig(path, dpi=190, bbox_inches="tight")
    plt.close()


def split_features(value: object) -> list[str]:
    if pd.isna(value) or not str(value).strip():
        return []
    return list(
        dict.fromkeys(
            item.strip() for item in str(value).split(";") if item.strip()
        )
    )


def normalize_method(value: object) -> str:
    raw = "" if pd.isna(value) else str(value).strip()
    if raw in METHOD_ORDER[:-1]:
        return raw
    return "other"


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


def reference_arrays(reference, channel: int) -> tuple[np.ndarray, np.ndarray]:
    state = reference._state[channel]
    mean = state["mean"].copy()
    _, std = reference.get_stats(channel)
    return mean, std


def raw_metric_from_feature(feature: str, metric_cols: list[str]) -> str | None:
    for suffix in ("_mean", "_std", "_median"):
        if feature.endswith(suffix):
            candidate = feature[: -len(suffix)]
            if candidate in metric_cols:
                return candidate
    return None


def finite_summary(values: pd.Series) -> dict[str, object]:
    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric[np.isfinite(numeric)]
    if finite.empty:
        return {
            "n": 0,
            "n_nan": int(numeric.isna().sum()),
            "n_inf": int(np.isinf(numeric.fillna(0)).sum()),
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "median": None,
            "q25": None,
            "q75": None,
        }
    return {
        "n": int(len(finite)),
        "n_nan": int(numeric.isna().sum()),
        "n_inf": int(np.isinf(numeric.fillna(0)).sum()),
        "min": float(finite.min()),
        "max": float(finite.max()),
        "mean": float(finite.mean()),
        "std": float(finite.std(ddof=1)) if len(finite) > 1 else 0.0,
        "median": float(finite.median()),
        "q25": float(finite.quantile(0.25)),
        "q75": float(finite.quantile(0.75)),
    }


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return value


def main() -> None:
    sys.path.insert(0, str(IF_DIR))
    from src.features import METRIC_COLS
    from src.reference import ReferenceModel
    from src.run_list import parse_run_subrun

    required = [
        TIMELINE,
        CLASSIFICATION,
        LOG,
        PATH_CACHE,
        MODEL_DIR / "reference.npz",
        MODEL_DIR / "detector.pkl",
        MODEL_DIR / "config.yaml",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        fail(f"missing required inputs: {missing}")
    if OUT.exists():
        unexpected = [
            path
            for path in OUT.rglob("*")
            if path.is_file() and path.name != "bulk_only_diagnosis.py"
        ]
        if unexpected:
            fail(f"output directory is not new/empty: {unexpected}")
    OUT.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(exist_ok=True)

    production_stats_before = {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in required
    }

    timeline = pd.read_csv(TIMELINE).sort_values("sequence_index").reset_index(
        drop=True
    )
    for column in ["persistent_alert", "bulk_alert", "extreme_alert"]:
        timeline[column] = as_bool(timeline[column], column)
    if (
        len(timeline) != 361
        or timeline["sequence_index"].tolist() != list(range(361))
        or timeline["strict_status"].value_counts().to_dict()
        != {"OK": 213, "WARN": 77, "ALERT": 71}
    ):
        fail("run-2014 timeline does not reproduce 361/213/77/71")

    step1 = pd.read_csv(CLASSIFICATION)
    step1 = step1[step1["run"] == RUN].copy()
    if len(step1) != 361:
        fail(f"Step-1 has {len(step1)} run-2014 files, not 361")
    step1 = step1.rename(
        columns={"sequence_index_within_run": "sequence_index"}
    )
    for column in ["persistent_alert", "bulk_alert", "extreme_alert"]:
        step1[column] = as_bool(step1[column], f"Step-1 {column}")
    compare_columns = [
        "filename",
        "sequence_index",
        "strict_status",
        "n_anomalous_channels",
        "n_persistent_channels",
        "persistent_alert",
        "bulk_alert",
        "extreme_alert",
        "max_z_over_file",
    ]
    left = timeline[compare_columns].sort_values("sequence_index").reset_index(
        drop=True
    )
    right = step1[compare_columns].sort_values("sequence_index").reset_index(
        drop=True
    )
    if not left.equals(right):
        fail("timeline and authoritative Step-1 classification disagree")

    bulk = timeline[
        timeline["strict_status"].eq("ALERT")
        & timeline["bulk_alert"]
        & ~timeline["persistent_alert"]
        & ~timeline["extreme_alert"]
    ].copy()
    if len(bulk) != 18:
        fail(f"selected {len(bulk)} bulk-only files, not 18")
    if (
        not bulk["bulk_alert"].all()
        or bulk["persistent_alert"].any()
        or bulk["extreme_alert"].any()
        or not bulk["strict_status"].eq("ALERT").all()
    ):
        fail("bulk-only selection violates alert flag constraints")
    if (bulk["n_anomalous_channels"] < 5).any():
        fail("bulk-only selection contains a file with fewer than 5 anomalies")
    if (bulk["n_persistent_channels"] >= 2).any():
        fail("bulk-only selection contains persistence-triggering channels")
    if (bulk["max_z_over_file"] >= 15).any():
        fail("bulk-only selection contains an extreme z trigger")

    paths = [
        path
        for path in PATH_CACHE.read_text().splitlines()
        if parse_run_subrun(path)[0] == RUN
    ]
    if len(paths) != 361:
        fail(f"path cache has {len(paths)} successfully processed run-2014 files")
    path_by_name = {Path(path).name: path for path in paths}
    if list(path_by_name) != timeline["filename"].tolist():
        fail("path-cache order differs from timeline")

    log = pd.read_csv(LOG)
    run_names = set(timeline["filename"])
    run_log = log[log["filename"].isin(run_names)].copy()
    del log
    run_log["anomalous"] = as_bool(run_log["anomalous"], "log anomalous")
    if run_log.duplicated(["filename", "channel"]).any():
        fail("duplicate filename/channel rows in run-2014 anomaly log")
    if set(run_log["filename"]) != run_names:
        fail("run-2014 log and timeline filenames differ")
    bulk_names = set(bulk["filename"])
    anomalies = run_log[
        run_log["filename"].isin(bulk_names) & run_log["anomalous"]
    ].copy()
    anomalies["method_class"] = anomalies["method"].map(normalize_method)
    if anomalies["filename"].nunique() != 18:
        fail("not every bulk-only file has anomalous log rows")
    log_counts = anomalies.groupby("filename").size()
    timeline_counts = bulk.set_index("filename")["n_anomalous_channels"]
    if not log_counts.sort_index().equals(timeline_counts.sort_index()):
        fail("log anomaly counts do not match timeline")

    anomaly_sets = {
        filename: set(group["channel"].astype(int))
        for filename, group in anomalies.groupby("filename")
    }
    anomalous_channel_text = {
        filename: ";".join(str(v) for v in sorted(values))
        for filename, values in anomaly_sets.items()
    }
    bulk["anomalous_channels"] = bulk["filename"].map(anomalous_channel_text)
    bulk["previous_status"] = bulk["sequence_index"].map(
        lambda i: timeline.iloc[i - 1]["strict_status"] if i > 0 else ""
    )
    bulk["next_status"] = bulk["sequence_index"].map(
        lambda i: (
            timeline.iloc[i + 1]["strict_status"]
            if i + 1 < len(timeline)
            else ""
        )
    )
    bulk["previous_alert_type"] = bulk["sequence_index"].map(
        lambda i: (
            ";".join(
                name
                for name, col in [
                    ("persistent", "persistent_alert"),
                    ("bulk", "bulk_alert"),
                    ("extreme", "extreme_alert"),
                ]
                if bool(timeline.iloc[i - 1][col])
            )
            if i > 0
            else ""
        )
    )
    bulk["next_alert_type"] = bulk["sequence_index"].map(
        lambda i: (
            ";".join(
                name
                for name, col in [
                    ("persistent", "persistent_alert"),
                    ("bulk", "bulk_alert"),
                    ("extreme", "extreme_alert"),
                ]
                if bool(timeline.iloc[i + 1][col])
            )
            if i + 1 < len(timeline)
            else ""
        )
    )
    bulk_columns = [
        "sequence_index",
        "subrun",
        "filename",
        "strict_status",
        "n_anomalous_channels",
        "n_persistent_channels",
        "max_z_over_file",
        "anomalous_channels",
        "bulk_alert",
        "persistent_alert",
        "extreme_alert",
        "previous_status",
        "next_status",
        "previous_alert_type",
        "next_alert_type",
    ]
    bulk[bulk_columns].to_csv(
        safe_output(OUT / "bulk_only_subruns.csv"), index=False
    )

    # Channel composition.
    channel_rows = []
    for channel in sorted(anomalies["channel"].astype(int).unique()):
        group = anomalies[anomalies["channel"].astype(int) == channel]
        counts = group["method_class"].value_counts()
        channel_rows.append(
            {
                "channel": channel,
                "n_bulk_only_files_anomalous": int(group["filename"].nunique()),
                "fraction_of_18_files": group["filename"].nunique() / 18,
                "n_statistical_only_rows": int(
                    counts.get("statistical", 0)
                ),
                "n_if_only_rows": int(counts.get("isolation_forest", 0)),
                "n_statistical_if_rows": int(
                    counts.get("statistical+IF", 0)
                ),
                "n_other_method_rows": int(
                    sum(
                        counts.get(method, 0)
                        for method in [
                            "missing_channel",
                            "new_channel",
                            "other",
                        ]
                    )
                ),
                "median_max_z_when_anomalous": float(group["max_z"].median()),
                "maximum_max_z": float(group["max_z"].max()),
                "median_if_score_when_anomalous": float(
                    group["if_score"].median()
                ),
            }
        )
    channel_summary = pd.DataFrame(channel_rows).sort_values(
        ["n_bulk_only_files_anomalous", "maximum_max_z", "channel"],
        ascending=[False, False, True],
    )
    channel_summary.insert(
        0, "frequency_rank", range(1, len(channel_summary) + 1)
    )
    channel_summary.to_csv(
        safe_output(OUT / "bulk_only_channel_summary.csv"), index=False
    )

    # Triggered-feature composition.
    feature_records = []
    for row in anomalies.itertuples(index=False):
        features = split_features(row.triggered_features)
        if not features:
            features = ["<none; IF-only>"]
        for feature in features:
            feature_records.append(
                {
                    "filename": row.filename,
                    "channel": int(row.channel),
                    "method": row.method_class,
                    "triggered_feature": feature,
                }
            )
    feature_long = pd.DataFrame(feature_records)
    feature_rows = []
    for feature, group in feature_long.groupby("triggered_feature"):
        method_counts = group["method"].value_counts()
        feature_rows.append(
            {
                "triggered_feature": feature,
                "n_anomalous_row_occurrences": int(len(group)),
                "n_bulk_only_files": int(group["filename"].nunique()),
                "fraction_of_18_files": group["filename"].nunique() / 18,
                "statistical_occurrences": int(
                    method_counts.get("statistical", 0)
                ),
                "if_only_occurrences": int(
                    method_counts.get("isolation_forest", 0)
                ),
                "statistical_if_occurrences": int(
                    method_counts.get("statistical+IF", 0)
                ),
                "other_method_occurrences": int(
                    sum(
                        method_counts.get(method, 0)
                        for method in [
                            "missing_channel",
                            "new_channel",
                            "other",
                        ]
                    )
                ),
                "fraction_of_93_anomalous_rows": len(group) / len(anomalies),
            }
        )
    feature_summary = pd.DataFrame(feature_rows).sort_values(
        ["n_anomalous_row_occurrences", "n_bulk_only_files"],
        ascending=False,
    )
    feature_summary.to_csv(
        safe_output(OUT / "bulk_only_feature_summary.csv"), index=False
    )

    channel_feature = pd.crosstab(
        feature_long["channel"], feature_long["triggered_feature"]
    )
    channel_feature = channel_feature.loc[
        channel_summary["channel"],
        feature_summary["triggered_feature"],
    ]
    channel_feature.index.name = "channel"
    channel_feature.reset_index().to_csv(
        safe_output(OUT / "bulk_only_channel_feature_matrix.csv"),
        index=False,
    )

    # Method composition: retain all requested categories, including zeros.
    method_rows = []
    for method in METHOD_ORDER:
        group = anomalies[anomalies["method_class"] == method]
        method_rows.append(
            {
                "method": method,
                "row_count": int(len(group)),
                "row_fraction": len(group) / len(anomalies),
                "file_count_with_at_least_one": int(
                    group["filename"].nunique()
                ),
                "file_fraction_of_18": group["filename"].nunique() / 18,
            }
        )
    method_summary = pd.DataFrame(method_rows)
    method_summary.to_csv(
        safe_output(OUT / "bulk_only_method_summary.csv"), index=False
    )

    # File x channel and file x feature matrices.
    all_channels = list(range(96))
    subrun_channel = pd.crosstab(
        anomalies["filename"], anomalies["channel"].astype(int)
    ).clip(upper=1)
    subrun_channel = subrun_channel.reindex(
        index=bulk["filename"], columns=all_channels, fill_value=0
    )
    subrun_channel.columns = [f"ch{channel}" for channel in all_channels]
    subrun_channel.insert(
        0,
        "subrun",
        subrun_channel.index.map(bulk.set_index("filename")["subrun"]),
    )
    subrun_channel.insert(
        0,
        "sequence_index",
        subrun_channel.index.map(
            bulk.set_index("filename")["sequence_index"]
        ),
    )
    subrun_channel.reset_index().to_csv(
        safe_output(OUT / "bulk_only_subrun_channel_matrix.csv"),
        index=False,
    )

    subrun_feature = pd.crosstab(
        feature_long["filename"], feature_long["triggered_feature"]
    ).reindex(
        index=bulk["filename"],
        columns=feature_summary["triggered_feature"],
        fill_value=0,
    )
    subrun_feature.insert(
        0,
        "subrun",
        subrun_feature.index.map(bulk.set_index("filename")["subrun"]),
    )
    subrun_feature.insert(
        0,
        "sequence_index",
        subrun_feature.index.map(
            bulk.set_index("filename")["sequence_index"]
        ),
    )
    subrun_feature.reset_index().to_csv(
        safe_output(OUT / "bulk_only_subrun_feature_matrix.csv"),
        index=False,
    )

    pairwise_rows = []
    ordered_names = bulk["filename"].tolist()
    for left_name, right_name in itertools.combinations(ordered_names, 2):
        left_set = anomaly_sets[left_name]
        right_set = anomaly_sets[right_name]
        intersection = left_set & right_set
        union = left_set | right_set
        pairwise_rows.append(
            {
                "filename_a": left_name,
                "subrun_a": int(
                    bulk.set_index("filename").loc[left_name, "subrun"]
                ),
                "filename_b": right_name,
                "subrun_b": int(
                    bulk.set_index("filename").loc[right_name, "subrun"]
                ),
                "intersection_size": len(intersection),
                "union_size": len(union),
                "jaccard_similarity": len(intersection) / len(union),
                "shared_channels": ";".join(
                    str(v) for v in sorted(intersection)
                ),
            }
        )
    pairwise = pd.DataFrame(pairwise_rows).sort_values(
        ["jaccard_similarity", "subrun_a", "subrun_b"],
        ascending=[False, True, True],
    )
    if len(pairwise) != math.comb(18, 2):
        fail("pairwise similarity does not contain 153 unordered pairs")
    pairwise.to_csv(
        safe_output(OUT / "bulk_only_pairwise_similarity.csv"), index=False
    )

    mean_similarity = {}
    for filename in ordered_names:
        related = pairwise[
            pairwise["filename_a"].eq(filename)
            | pairwise["filename_b"].eq(filename)
        ]
        mean_similarity[filename] = float(
            related["jaccard_similarity"].mean()
        )

    # Temporal summary, with immediate adjacency to other states/types.
    temporal_rows = []
    for label, start, end in SEGMENTS:
        segment_files = bulk[
            bulk["sequence_index"].between(start, end)
        ].copy()
        adjacent_warn = 0
        adjacent_other_alert = 0
        adjacent_extreme = 0
        for row in segment_files.itertuples(index=False):
            neighbors = []
            if row.sequence_index > 0:
                neighbors.append(timeline.iloc[row.sequence_index - 1])
            if row.sequence_index + 1 < len(timeline):
                neighbors.append(timeline.iloc[row.sequence_index + 1])
            if any(n["strict_status"] == "WARN" for n in neighbors):
                adjacent_warn += 1
            if any(
                n["strict_status"] == "ALERT"
                and n["filename"] not in bulk_names
                for n in neighbors
            ):
                adjacent_other_alert += 1
            if any(bool(n["extreme_alert"]) for n in neighbors):
                adjacent_extreme += 1
        temporal_rows.append(
            {
                "segment": label,
                "sequence_index_start": start,
                "sequence_index_end": end,
                "n_processed_files": end - start + 1,
                "n_bulk_only_files": int(len(segment_files)),
                "bulk_only_fraction_within_segment": len(segment_files)
                / (end - start + 1),
                "bulk_only_subruns": ";".join(
                    str(v) for v in segment_files["subrun"]
                ),
                "first_bulk_sequence_index": (
                    int(segment_files["sequence_index"].min())
                    if len(segment_files)
                    else None
                ),
                "last_bulk_sequence_index": (
                    int(segment_files["sequence_index"].max())
                    if len(segment_files)
                    else None
                ),
                "n_adjacent_to_WARN": adjacent_warn,
                "n_adjacent_to_other_ALERT": adjacent_other_alert,
                "n_adjacent_to_extreme_ALERT": adjacent_extreme,
            }
        )
    temporal_summary = pd.DataFrame(temporal_rows)
    if temporal_summary["n_bulk_only_files"].sum() != 18:
        fail("temporal segment counts do not sum to 18")
    temporal_summary.to_csv(
        safe_output(OUT / "bulk_only_temporal_summary.csv"), index=False
    )

    # Deterministic representative selection.
    largest_name = str(
        bulk.sort_values(
            ["n_anomalous_channels", "max_z_over_file", "sequence_index"],
            ascending=[False, False, True],
        ).iloc[0]["filename"]
    )
    remaining = [name for name in ordered_names if name != largest_name]
    typical_name = max(
        remaining,
        key=lambda name: (
            mean_similarity[name],
            -int(bulk.set_index("filename").loc[name, "sequence_index"]),
        ),
    )
    distinct_candidates = [
        name for name in remaining if name != typical_name
    ]
    distinct_name = min(
        distinct_candidates,
        key=lambda name: (
            mean_similarity[name],
            int(bulk.set_index("filename").loc[name, "sequence_index"]),
        ),
    )
    representative_roles = {
        largest_name: "largest_n_anomalous_channels",
        typical_name: "most_typical_by_mean_channel_Jaccard",
        distinct_name: "most_distinct_by_mean_channel_Jaccard",
    }
    if len(representative_roles) != 3:
        fail("representative selection did not produce 3 unique files")

    reference = ReferenceModel.load(str(MODEL_DIR / "reference.npz"))
    active_features = list(reference._feat_cols)
    representative_rows = []
    representative_plot_data = {}
    for filename, role in representative_roles.items():
        filepath = path_by_name[filename]
        path = Path(filepath)
        if not path.is_file():
            fail(f"representative raw CSV is missing: {filepath}")
        raw = pd.read_csv(filepath)
        if raw.empty:
            fail(f"representative raw CSV is empty: {filepath}")
        features = canonical_features(filepath, reference)
        file_anomalies = anomalies[anomalies["filename"] == filename].copy()
        anomaly_channels = sorted(file_anomalies["channel"].astype(int))
        if any(channel not in features.index for channel in anomaly_channels):
            fail(f"canonical extraction is missing a target in {filename}")
        file_event_counts = raw.groupby("event_id")["channel"].nunique()
        representative_plot_data[filename] = {}
        for channel in anomaly_channels:
            anomaly = file_anomalies[
                file_anomalies["channel"].astype(int) == channel
            ].iloc[0]
            observed = features.loc[
                channel, active_features
            ].to_numpy(dtype=float)
            mean, std = reference_arrays(reference, channel)
            z = (observed - mean) / std
            finite_order = np.argsort(
                np.nan_to_num(np.abs(z), nan=-np.inf)
            )[::-1]
            top_indices = [
                int(i) for i in finite_order if np.isfinite(z[i])
            ][:5]
            top_features = [
                {
                    "feature": active_features[i],
                    "observed": observed[i],
                    "reference_mean": mean[i],
                    "reference_std": std[i],
                    "z": z[i],
                }
                for i in top_indices
            ]
            representative_plot_data[filename][channel] = {
                item["feature"]: item["z"] for item in top_features
            }
            triggered = split_features(anomaly["triggered_features"])
            triggered_details = []
            for feature in triggered:
                if feature not in active_features:
                    fail(f"triggered feature {feature} is not active")
                i = active_features.index(feature)
                triggered_details.append(
                    {
                        "feature": feature,
                        "observed": observed[i],
                        "reference_mean": mean[i],
                        "reference_std": std[i],
                        "z": z[i],
                    }
                )
            source_metrics = []
            for feature in triggered + [
                item["feature"] for item in top_features
            ]:
                metric = raw_metric_from_feature(feature, METRIC_COLS)
                if metric and metric not in source_metrics:
                    source_metrics.append(metric)
            channel_raw = raw[raw["channel"].astype(int) == channel].copy()
            metric_summaries = {
                metric: finite_summary(channel_raw[metric])
                for metric in source_metrics
            }
            npulses = pd.to_numeric(
                channel_raw["nPulses"], errors="coerce"
            )
            finite_npulses = npulses[np.isfinite(npulses)]
            np_counts = {
                str(int(key) if float(key).is_integer() else float(key)): int(
                    value
                )
                for key, value in finite_npulses.value_counts().sort_index().items()
            }
            occupancy_idx = active_features.index("occupancy")
            frac_dead_idx = active_features.index("frac_dead")
            representative_rows.append(
                {
                    "selection_role": role,
                    "sequence_index": int(
                        bulk.set_index("filename").loc[
                            filename, "sequence_index"
                        ]
                    ),
                    "subrun": int(
                        bulk.set_index("filename").loc[filename, "subrun"]
                    ),
                    "filename": filename,
                    "filepath": filepath,
                    "file_row_count": int(len(raw)),
                    "file_unique_events": int(raw["event_id"].nunique()),
                    "file_unique_channels": int(raw["channel"].nunique()),
                    "file_mean_channels_per_event": float(
                        file_event_counts.mean()
                    ),
                    "file_max_channels_per_event": int(
                        file_event_counts.max()
                    ),
                    "n_anomalous_channels_in_file": len(anomaly_channels),
                    "mean_channel_set_jaccard_to_other_bulk_files": (
                        mean_similarity[filename]
                    ),
                    "channel": channel,
                    "method": anomaly["method_class"],
                    "triggered_features": (
                        "" if not triggered else ";".join(triggered)
                    ),
                    "max_z_log": float(anomaly["max_z"]),
                    "if_score_log": float(anomaly["if_score"]),
                    "channel_rows": int(len(channel_raw)),
                    "channel_unique_events": int(
                        channel_raw["event_id"].nunique()
                    ),
                    "occupancy": float(observed[occupancy_idx]),
                    "occupancy_z": float(z[occupancy_idx]),
                    "frac_dead": float(observed[frac_dead_idx]),
                    "frac_dead_z": float(z[frac_dead_idx]),
                    "nPulses_min": (
                        float(finite_npulses.min())
                        if len(finite_npulses)
                        else None
                    ),
                    "nPulses_max": (
                        float(finite_npulses.max())
                        if len(finite_npulses)
                        else None
                    ),
                    "nPulses_mean": (
                        float(finite_npulses.mean())
                        if len(finite_npulses)
                        else None
                    ),
                    "nPulses_std": (
                        float(finite_npulses.std(ddof=1))
                        if len(finite_npulses) > 1
                        else 0.0
                    ),
                    "nPulses_median": (
                        float(finite_npulses.median())
                        if len(finite_npulses)
                        else None
                    ),
                    "nPulses_zero_count": int((finite_npulses == 0).sum()),
                    "nPulses_zero_fraction": (
                        float((finite_npulses == 0).mean())
                        if len(finite_npulses)
                        else None
                    ),
                    "nPulses_value_counts_json": json.dumps(np_counts),
                    "triggered_feature_details_json": json.dumps(
                        json_clean(triggered_details)
                    ),
                    "top_five_abs_z_features_json": json.dumps(
                        json_clean(top_features)
                    ),
                    "selected_raw_source_metric_summaries_json": json.dumps(
                        json_clean(metric_summaries)
                    ),
                    "raw_nan_count_active_source_metrics": int(
                        raw[
                            [
                                metric
                                for metric in METRIC_COLS
                                if metric in raw.columns
                            ]
                        ].isna().sum().sum()
                    ),
                }
            )
    representative_raw = pd.DataFrame(representative_rows)
    representative_raw.to_csv(
        safe_output(OUT / "bulk_only_representative_raw_summary.csv"),
        index=False,
    )

    # Plots.
    colors = [
        "#d95f02" if channel in (3, 82) else "#4c72b0"
        for channel in channel_summary["channel"]
    ]
    plt.figure(figsize=(12, 5))
    plt.bar(
        channel_summary["channel"].astype(str),
        channel_summary["n_bulk_only_files_anomalous"],
        color=colors,
    )
    plt.axhline(9, color="#c44e52", linestyle="--", linewidth=1, label="50%")
    plt.axhline(
        4.5, color="#dd8452", linestyle=":", linewidth=1, label="25%"
    )
    plt.xlabel("Channel")
    plt.ylabel("Bulk-only files with anomalous channel (of 18)")
    plt.title("Run 2014 bulk-only ALERT channel recurrence")
    plt.xticks(rotation=90)
    plt.legend()
    savefig(PLOTS / "bulk_only_channel_frequency.png")

    feature_plot = feature_summary[
        feature_summary["triggered_feature"] != "<none; IF-only>"
    ].copy()
    plt.figure(figsize=(11, 6))
    plt.barh(
        feature_plot["triggered_feature"][::-1],
        feature_plot["n_anomalous_row_occurrences"][::-1],
        color="#4c72b0",
    )
    plt.xlabel("Triggered anomalous-row occurrences")
    plt.ylabel("Triggered feature")
    plt.title("Run 2014 bulk-only ALERT statistical feature frequency")
    savefig(PLOTS / "bulk_only_feature_frequency.png")

    nonempty_cf = channel_feature.loc[
        channel_feature.sum(axis=1) > 0,
        [
            col
            for col in channel_feature.columns
            if col != "<none; IF-only>"
            and channel_feature[col].sum() > 0
        ],
    ]
    plt.figure(
        figsize=(
            max(9, 0.65 * len(nonempty_cf.columns)),
            max(6, 0.30 * len(nonempty_cf)),
        )
    )
    plt.imshow(nonempty_cf.to_numpy(), aspect="auto", cmap="Blues")
    plt.colorbar(label="Triggered occurrences")
    plt.xticks(
        range(len(nonempty_cf.columns)),
        nonempty_cf.columns,
        rotation=55,
        ha="right",
    )
    plt.yticks(
        range(len(nonempty_cf.index)),
        [f"ch{v}" for v in nonempty_cf.index],
    )
    plt.title("Bulk-only channel × statistical-feature frequency")
    plt.xlabel("Triggered feature")
    plt.ylabel("Channel")
    savefig(PLOTS / "bulk_only_channel_feature_heatmap.png")

    recurring_channels = channel_summary.loc[
        channel_summary["n_bulk_only_files_anomalous"] >= 2, "channel"
    ].tolist()
    recurrence = pd.crosstab(
        anomalies["filename"], anomalies["channel"].astype(int)
    ).clip(upper=1)
    recurrence = recurrence.reindex(
        index=ordered_names, columns=recurring_channels, fill_value=0
    )
    plt.figure(
        figsize=(
            max(9, 0.55 * len(recurring_channels)),
            max(6, 0.42 * len(ordered_names)),
        )
    )
    plt.imshow(recurrence.to_numpy(), aspect="auto", cmap="Blues", vmin=0, vmax=1)
    plt.xticks(
        range(len(recurring_channels)),
        [f"ch{v}" for v in recurring_channels],
        rotation=45,
        ha="right",
    )
    plt.yticks(
        range(len(ordered_names)),
        [f"sub{v}" for v in bulk["subrun"]],
    )
    plt.title("Recurring anomalous-channel groups across 18 bulk-only files")
    plt.xlabel("Channels appearing in at least two bulk-only files")
    plt.ylabel("Bulk-only subrun")
    savefig(PLOTS / "bulk_only_subrun_channel_recurrence_heatmap.png")

    plt.figure(figsize=(13, 4.5))
    status_y = {"OK": 0, "WARN": 1, "ALERT": 2}
    plt.scatter(
        timeline["sequence_index"],
        timeline["strict_status"].map(status_y),
        c=timeline["strict_status"].map(
            {"OK": "#bdbdbd", "WARN": "#e6ab02", "ALERT": "#d95f02"}
        ),
        s=17,
        alpha=0.75,
        label="All processed files",
    )
    plt.scatter(
        bulk["sequence_index"],
        [2.15] * len(bulk),
        marker="v",
        s=65,
        color="#542788",
        label="Bulk-only ALERT",
        zorder=5,
    )
    for boundary in [90.5, 180.5, 270.5]:
        plt.axvline(boundary, color="#666666", linestyle=":", linewidth=0.8)
    plt.yticks([0, 1, 2], ["OK", "WARN", "ALERT"])
    plt.xlabel("Processed-file sequence index")
    plt.title("Run 2014 temporal location of 18 bulk-only ALERTs")
    plt.legend(loc="upper left", ncol=2)
    savefig(PLOTS / "bulk_only_temporal_location.png")

    # Representative canonical-z heatmaps.
    for filename, channel_map in representative_plot_data.items():
        all_plot_features = []
        for feature_map in channel_map.values():
            for feature in feature_map:
                if feature not in all_plot_features:
                    all_plot_features.append(feature)
        channels = sorted(channel_map)
        matrix = np.full((len(channels), len(all_plot_features)), np.nan)
        for i, channel in enumerate(channels):
            for j, feature in enumerate(all_plot_features):
                if feature in channel_map[channel]:
                    matrix[i, j] = channel_map[channel][feature]
        max_abs = max(8.0, float(np.nanmax(np.abs(matrix))))
        plt.figure(
            figsize=(
                max(10, 0.55 * len(all_plot_features)),
                max(4, 0.7 * len(channels)),
            )
        )
        im = plt.imshow(
            matrix,
            aspect="auto",
            cmap="coolwarm",
            vmin=-max_abs,
            vmax=max_abs,
        )
        plt.colorbar(im, label="Canonical z score (top-five union)")
        plt.xticks(
            range(len(all_plot_features)),
            all_plot_features,
            rotation=55,
            ha="right",
        )
        plt.yticks(range(len(channels)), [f"ch{v}" for v in channels])
        subrun = int(bulk.set_index("filename").loc[filename, "subrun"])
        plt.title(
            f"Representative bulk-only subrun{subrun}: anomalous-channel z patterns"
        )
        plt.xlabel("Feature")
        plt.ylabel("Anomalous channel")
        savefig(
            PLOTS / f"bulk_only_subrun{subrun}_anomalous_feature_z_heatmap.png"
        )

    # Machine-readable metrics for synthesis and validation.
    statistical_rows = anomalies[
        anomalies["method_class"].isin(["statistical", "statistical+IF"])
    ]
    npulse_rows = feature_long[
        feature_long["triggered_feature"] == "nPulses_median"
    ]
    similarity_values = pairwise["jaccard_similarity"]
    n_channels_distribution = (
        bulk["n_anomalous_channels"].value_counts().sort_index()
    )
    metrics = {
        "n_bulk_only_files": 18,
        "n_anomalous_rows": int(len(anomalies)),
        "n_anomalous_channels_distribution": {
            str(k): int(v) for k, v in n_channels_distribution.items()
        },
        "channels_at_least_50_percent": channel_summary.loc[
            channel_summary["fraction_of_18_files"] >= 0.5, "channel"
        ].astype(int).tolist(),
        "channels_at_least_25_percent": channel_summary.loc[
            channel_summary["fraction_of_18_files"] >= 0.25, "channel"
        ].astype(int).tolist(),
        "ch3_file_count": int(
            channel_summary.set_index("channel").loc[
                3, "n_bulk_only_files_anomalous"
            ]
        ),
        "ch82_file_count": int(
            channel_summary.set_index("channel").loc[
                82, "n_bulk_only_files_anomalous"
            ]
        ),
        "nPulses_median": {
            "file_count": int(npulse_rows["filename"].nunique()),
            "anomalous_row_count": int(len(npulse_rows)),
            "statistical_triggered_row_denominator": int(
                len(statistical_rows)
            ),
            "fraction_of_statistical_triggered_rows": (
                len(npulse_rows) / len(statistical_rows)
            ),
        },
        "methods": method_summary.to_dict("records"),
        "similarity": {
            "mean_pairwise_jaccard": float(similarity_values.mean()),
            "median_pairwise_jaccard": float(similarity_values.median()),
            "zero_similarity_pair_count": int(
                (similarity_values == 0).sum()
            ),
            "pair_count": int(len(similarity_values)),
            "maximum_pairwise_jaccard": float(similarity_values.max()),
        },
        "temporal": temporal_summary.to_dict("records"),
        "representatives": [
            {
                "filename": filename,
                "subrun": int(
                    bulk.set_index("filename").loc[filename, "subrun"]
                ),
                "selection_role": role,
                "mean_channel_jaccard": mean_similarity[filename],
            }
            for filename, role in representative_roles.items()
        ],
        "active_feature_count": len(active_features),
        "production_inputs_unchanged": True,
    }
    after_stats = {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in required
    }
    if after_stats != production_stats_before:
        fail("one or more production inputs changed during diagnosis")
    with safe_output(OUT / "bulk_only_diagnostic_metrics.json").open("w") as handle:
        json.dump(json_clean(metrics), handle, indent=2)

    print("Bulk-only run2014 diagnosis tables and plots complete.")
    print(json.dumps(json_clean(metrics), indent=2))


if __name__ == "__main__":
    main()
