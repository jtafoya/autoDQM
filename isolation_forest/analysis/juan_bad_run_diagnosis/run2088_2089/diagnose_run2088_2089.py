#!/usr/bin/env python3
"""Read-only model/log-level comparison of runs 2088 and 2089."""

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
STEP1 = (
    IF_DIR
    / "analysis"
    / "juan_bad_run_diagnosis"
    / "step1_classification"
)
SUBRUN_CLASSIFICATION = STEP1 / "subrun_classification.csv"
RUN_CLASSIFICATION = STEP1 / "run_classification.csv"
LOG = IF_DIR / "logs" / f"{TAG}.csv"
PATH_CACHE = IF_DIR / "logs" / f"{TAG}_paths.txt"
MODEL_DIR = IF_DIR / "models" / TAG
OUT = (
    IF_DIR
    / "analysis"
    / "juan_bad_run_diagnosis"
    / "run2088_2089"
)
PLOTS = OUT / "plots"
RUNS = [2088, 2089]
EXPECTED = {
    2088: {"total": 203, "OK": 180, "ALERT": 23, "WARN": 0, "PEND": 0},
    2089: {"total": 369, "OK": 318, "ALERT": 51, "WARN": 0, "PEND": 0},
}
METHOD_ORDER = [
    "statistical",
    "isolation_forest",
    "statistical+IF",
    "missing_channel",
    "new_channel",
    "other",
]
MECHANISM_COMBINATIONS = [
    ("persistent only", True, False, False),
    ("bulk only", False, True, False),
    ("extreme only", False, False, True),
    ("persistent + bulk", True, True, False),
    ("persistent + extreme", True, False, True),
    ("bulk + extreme", False, True, True),
    ("persistent + bulk + extreme", True, True, True),
]
RUN_COLORS = {2088: "#4c72b0", 2089: "#dd8452"}


def fail(message: str) -> "None":
    raise RuntimeError(f"SANITY CHECK FAILED: {message}")


def as_bool(series: pd.Series, name: str) -> pd.Series:
    if series.dtype == bool:
        return series
    values = series.astype(str).str.strip().str.lower()
    if not values.isin(["true", "false"]).all():
        fail(f"{name} contains non-boolean values")
    return values.eq("true")


def safe_output(path: Path) -> Path:
    if path != OUT and OUT not in path.parents:
        fail(f"attempted output outside run2088_2089: {path}")
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
    text = "" if pd.isna(value) else str(value).strip()
    return text if text in METHOD_ORDER[:-1] else "other"


def mechanism_label(row: pd.Series) -> str:
    for label, persistent, bulk, extreme in MECHANISM_COMBINATIONS:
        if (
            bool(row["persistent_alert"]) == persistent
            and bool(row["bulk_alert"]) == bulk
            and bool(row["extreme_alert"]) == extreme
        ):
            return label
    return "none"


def longest_true_streak(flags: list[bool]) -> int:
    best = current = 0
    for flag in flags:
        if flag:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def jaccard(left: set, right: set) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


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


def similarity_stats(
    sets_a: list[set],
    sets_b: list[set] | None = None,
) -> dict[str, object]:
    if sets_b is None:
        values = [
            jaccard(sets_a[i], sets_a[j])
            for i in range(len(sets_a))
            for j in range(i)
        ]
    else:
        values = [jaccard(a, b) for a in sets_a for b in sets_b]
    if not values:
        return {
            "n_pairs": 0,
            "mean_jaccard": math.nan,
            "median_jaccard": math.nan,
            "q25_jaccard": math.nan,
            "q75_jaccard": math.nan,
            "maximum_jaccard": math.nan,
            "zero_similarity_pairs": 0,
        }
    arr = np.asarray(values, dtype=float)
    return {
        "n_pairs": len(values),
        "mean_jaccard": float(np.mean(arr)),
        "median_jaccard": float(np.median(arr)),
        "q25_jaccard": float(np.quantile(arr, 0.25)),
        "q75_jaccard": float(np.quantile(arr, 0.75)),
        "maximum_jaccard": float(np.max(arr)),
        "zero_similarity_pairs": int(np.sum(arr == 0)),
    }


def select_typical(
    alert_rows: pd.DataFrame,
    selected: set[str],
) -> pd.Series:
    candidates = alert_rows[
        alert_rows["mechanism"] == "extreme only"
    ].copy()
    if candidates.empty:
        candidates = alert_rows.copy()
    mode_n = int(candidates["n_anomalous_channels"].mode().min())
    candidates = candidates[
        candidates["n_anomalous_channels"] == mode_n
    ].copy()
    target_z = float(candidates["max_z_over_file"].median())
    target_seq = float(candidates["sequence_index_within_run"].median())
    candidates["_distance"] = (
        (candidates["max_z_over_file"] - target_z).abs()
        / max(target_z, 1)
        + (
            candidates["sequence_index_within_run"] - target_seq
        ).abs()
        / max(len(alert_rows), 1)
    )
    candidates = candidates[~candidates["filename"].isin(selected)]
    return candidates.sort_values(
        ["_distance", "sequence_index_within_run"]
    ).iloc[0]


def add_representative(
    rows: list[dict[str, object]],
    selected: set[str],
    row: pd.Series,
    reason: str,
    anomalies: pd.DataFrame,
    feature_long: pd.DataFrame,
) -> None:
    filename = str(row["filename"])
    if filename in selected:
        fail(f"duplicate representative selection: {filename}")
    selected.add(filename)
    file_anomalies = anomalies[anomalies["filename"] == filename]
    channel_text = ";".join(
        str(value)
        for value in sorted(file_anomalies["channel"].astype(int))
    )
    feature_counts = (
        feature_long[feature_long["filename"] == filename][
            "triggered_feature"
        ].value_counts()
    )
    feature_text = ";".join(
        f"{feature}:{count}"
        for feature, count in feature_counts.items()
    )
    rows.append(
        {
            "run": int(row["run"]),
            "sequence_index_within_run": int(
                row["sequence_index_within_run"]
            ),
            "subrun": int(row["subrun"]),
            "filename": filename,
            "selection_reason": reason,
            "strict_status": str(row["strict_status"]),
            "n_anomalous_channels": int(row["n_anomalous_channels"]),
            "n_persistent_channels": int(row["n_persistent_channels"]),
            "max_z": float(row["max_z_over_file"]),
            "persistent_alert": bool(row["persistent_alert"]),
            "bulk_alert": bool(row["bulk_alert"]),
            "extreme_alert": bool(row["extreme_alert"]),
            "alert_mechanism": str(row["mechanism"]),
            "dominant_anomalous_channels": channel_text,
            "dominant_triggered_features": feature_text,
        }
    )


def main() -> None:
    sys.path.insert(0, str(IF_DIR))
    from src.run_list import parse_run_subrun

    required = [
        SUBRUN_CLASSIFICATION,
        RUN_CLASSIFICATION,
        LOG,
        PATH_CACHE,
        MODEL_DIR / "reference.npz",
        MODEL_DIR / "detector.pkl",
        MODEL_DIR / "config.yaml",
        MODEL_DIR / "training_metadata.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        fail(f"missing authoritative inputs: {missing}")
    if OUT.exists():
        unexpected = [
            path
            for path in OUT.rglob("*")
            if path.is_file() and path.name != "diagnose_run2088_2089.py"
        ]
        if unexpected:
            fail(f"output directory is not new/empty: {unexpected}")
    OUT.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(exist_ok=True)

    before_stats = {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in required
    }

    run_class = pd.read_csv(RUN_CLASSIFICATION)
    subrun_class = pd.read_csv(SUBRUN_CLASSIFICATION)
    timeline = subrun_class[subrun_class["run"].isin(RUNS)].copy()
    for column in [
        "raw_bad",
        "persistent_alert",
        "bulk_alert",
        "extreme_alert",
    ]:
        timeline[column] = as_bool(timeline[column], column)
    timeline = timeline.sort_values(
        ["run", "sequence_index_within_run"]
    ).reset_index(drop=True)

    for run in RUNS:
        expected = EXPECTED[run]
        current = timeline[timeline["run"] == run].copy()
        if len(current) != expected["total"]:
            fail(f"run {run} has {len(current)} files, expected {expected['total']}")
        if current["sequence_index_within_run"].tolist() != list(
            range(expected["total"])
        ):
            fail(f"run {run} processed indices are not contiguous from zero")
        status_counts = current["strict_status"].value_counts().to_dict()
        for status in ["OK", "WARN", "PEND", "ALERT"]:
            if int(status_counts.get(status, 0)) != expected[status]:
                fail(
                    f"run {run} {status}={status_counts.get(status, 0)}, "
                    f"expected {expected[status]}"
                )
        row = run_class[run_class["run"] == run]
        if len(row) != 1:
            fail(f"run classification has {len(row)} rows for {run}")
        row = row.iloc[0]
        checks = {
            "n_sampled_subruns": expected["total"],
            "n_OK": expected["OK"],
            "n_WARN": expected["WARN"],
            "n_PEND": expected["PEND"],
            "n_ALERT": expected["ALERT"],
        }
        for column, value in checks.items():
            if int(row[column]) != value:
                fail(f"run classification {run} {column} mismatch")
        calculated_alert = (
            current["persistent_alert"]
            | current["bulk_alert"]
            | current["extreme_alert"]
        )
        if not calculated_alert.equals(
            current["strict_status"].eq("ALERT")
        ):
            fail(f"run {run} alert flags do not reproduce strict status")

    processed_paths = PATH_CACHE.read_text().splitlines()
    path_order_verified = {}
    for run in RUNS:
        run_paths = [
            path
            for path in processed_paths
            if parse_run_subrun(path)[0] == run
        ]
        ordered_names = (
            timeline[timeline["run"] == run]
            .sort_values("sequence_index_within_run")["filename"]
            .tolist()
        )
        if [Path(path).name for path in run_paths] != ordered_names:
            fail(f"run {run} path-cache order differs from classification")
        path_order_verified[run] = True

    timeline_columns = [
        "run",
        "sequence_index_within_run",
        "subrun",
        "filename",
        "strict_status",
        "n_anomalous_channels",
        "n_persistent_channels",
        "persistent_alert",
        "bulk_alert",
        "extreme_alert",
        "max_z_over_file",
    ]
    timeline[timeline_columns].to_csv(
        safe_output(OUT / "run2088_2089_subrun_timeline.csv"),
        index=False,
    )

    log = pd.read_csv(LOG)
    names = set(timeline["filename"])
    selected_log = log[log["filename"].isin(names)].copy()
    del log
    selected_log["anomalous"] = as_bool(
        selected_log["anomalous"], "anomalous"
    )
    if selected_log.duplicated(["filename", "channel"]).any():
        fail("duplicate filename/channel rows in selected anomaly log")
    if set(selected_log["filename"]) != names:
        fail("selected anomaly log filenames differ from timeline")
    run_map = timeline.set_index("filename")["run"]
    status_map = timeline.set_index("filename")["strict_status"]
    selected_log["run"] = selected_log["filename"].map(run_map)
    selected_log["strict_status"] = selected_log["filename"].map(status_map)
    anomalies = selected_log[selected_log["anomalous"]].copy()
    anomalies["method_class"] = anomalies["method"].map(normalize_method)

    timeline["mechanism"] = timeline.apply(mechanism_label, axis=1)
    mechanism_map = timeline.set_index("filename")["mechanism"]
    anomalies["alert_mechanism"] = anomalies["filename"].map(mechanism_map)

    # Alert mechanism decomposition.
    condition_rows = []
    for run in RUNS:
        run_timeline = timeline[timeline["run"] == run]
        alerts = run_timeline[run_timeline["strict_status"] == "ALERT"]
        denominator = len(run_timeline)
        for label, persistent, bulk, extreme in MECHANISM_COMBINATIONS:
            mask = (
                alerts["persistent_alert"].eq(persistent)
                & alerts["bulk_alert"].eq(bulk)
                & alerts["extreme_alert"].eq(extreme)
            )
            count = int(mask.sum())
            condition_rows.append(
                {
                    "run": run,
                    "summary_type": "exclusive_combination",
                    "condition": label,
                    "count": count,
                    "rate_per_sampled_subrun": count / denominator,
                    "fraction_of_run_ALERTs": count / len(alerts),
                }
            )
        for label, column in [
            ("involving persistence", "persistent_alert"),
            ("involving bulk", "bulk_alert"),
            ("involving extreme", "extreme_alert"),
        ]:
            count = int(alerts[column].sum())
            condition_rows.append(
                {
                    "run": run,
                    "summary_type": "simple_total",
                    "condition": label,
                    "count": count,
                    "rate_per_sampled_subrun": count / denominator,
                    "fraction_of_run_ALERTs": count / len(alerts),
                }
            )
    condition_summary = pd.DataFrame(condition_rows)
    for run in RUNS:
        exclusive = condition_summary[
            (condition_summary["run"] == run)
            & condition_summary["summary_type"].eq(
                "exclusive_combination"
            )
        ]
        if int(exclusive["count"].sum()) != EXPECTED[run]["ALERT"]:
            fail(f"run {run} exclusive mechanism counts do not sum to ALERTs")
    condition_summary.to_csv(
        safe_output(OUT / "run2088_2089_alert_condition_summary.csv"),
        index=False,
    )

    # Feature-long records, including explicit IF-only placeholder.
    feature_records = []
    for row in anomalies.itertuples(index=False):
        features = split_features(row.triggered_features)
        if not features:
            features = ["<none; IF-only>"]
        for feature in features:
            feature_records.append(
                {
                    "run": int(row.run),
                    "filename": row.filename,
                    "channel": int(row.channel),
                    "strict_status": row.strict_status,
                    "method": row.method_class,
                    "alert_mechanism": row.alert_mechanism,
                    "triggered_feature": feature,
                }
            )
    feature_long = pd.DataFrame(feature_records)

    # Per-run channel summaries, including all 96 channels.
    channel_summaries = {}
    for run in RUNS:
        run_timeline = timeline[timeline["run"] == run].sort_values(
            "sequence_index_within_run"
        )
        run_anomalies = anomalies[anomalies["run"] == run]
        alert_names = set(
            run_timeline.loc[
                run_timeline["strict_status"] == "ALERT", "filename"
            ]
        )
        anomaly_sets = {
            filename: set(group["channel"].astype(int))
            for filename, group in run_anomalies.groupby("filename")
        }
        ordered_names = run_timeline["filename"].tolist()
        rows = []
        for channel in range(96):
            group = run_anomalies[
                run_anomalies["channel"].astype(int) == channel
            ]
            flags = [
                channel in anomaly_sets.get(filename, set())
                for filename in ordered_names
            ]
            alert_count = int(group["filename"].isin(alert_names).sum())
            rows.append(
                {
                    "channel": channel,
                    "anomalous_subrun_count": int(len(group)),
                    "anomalous_fraction": len(group) / len(run_timeline),
                    "ALERT_subrun_anomalous_count": alert_count,
                    "ALERT_subrun_presence_fraction": alert_count
                    / len(alert_names),
                    "longest_consecutive_anomalous_streak": (
                        longest_true_streak(flags)
                    ),
                    "maximum_max_z": (
                        float(group["max_z"].max())
                        if len(group)
                        else math.nan
                    ),
                    "median_max_z_when_anomalous": (
                        float(group["max_z"].median())
                        if len(group)
                        else math.nan
                    ),
                    "median_if_score_when_anomalous": (
                        float(group["if_score"].median())
                        if len(group)
                        else math.nan
                    ),
                }
            )
        summary = pd.DataFrame(rows)
        summary["frequency_rank"] = (
            summary["anomalous_subrun_count"]
            .rank(method="first", ascending=False)
            .astype(int)
        )
        summary = summary[
            ["frequency_rank"]
            + [c for c in summary.columns if c != "frequency_rank"]
        ].sort_values("frequency_rank")
        channel_summaries[run] = summary
        summary.to_csv(
            safe_output(OUT / f"run{run}_channel_summary.csv"),
            index=False,
        )

    ch88 = channel_summaries[2088].set_index("channel")
    ch89 = channel_summaries[2089].set_index("channel")
    channel_comparison = pd.DataFrame({"channel": range(96)})
    channel_comparison["2088_anomaly_fraction"] = channel_comparison[
        "channel"
    ].map(ch88["anomalous_fraction"])
    channel_comparison["2089_anomaly_fraction"] = channel_comparison[
        "channel"
    ].map(ch89["anomalous_fraction"])
    channel_comparison["anomaly_fraction_difference_2089_minus_2088"] = (
        channel_comparison["2089_anomaly_fraction"]
        - channel_comparison["2088_anomaly_fraction"]
    )
    channel_comparison["2088_ALERT_presence_fraction"] = channel_comparison[
        "channel"
    ].map(ch88["ALERT_subrun_presence_fraction"])
    channel_comparison["2089_ALERT_presence_fraction"] = channel_comparison[
        "channel"
    ].map(ch89["ALERT_subrun_presence_fraction"])
    channel_comparison[
        "ALERT_presence_fraction_difference_2089_minus_2088"
    ] = (
        channel_comparison["2089_ALERT_presence_fraction"]
        - channel_comparison["2088_ALERT_presence_fraction"]
    )
    channel_comparison["new_anomalous_channel_in_2089"] = (
        channel_comparison["2088_anomaly_fraction"].eq(0)
        & channel_comparison["2089_anomaly_fraction"].gt(0)
    )
    channel_comparison = channel_comparison.sort_values(
        [
            "anomaly_fraction_difference_2089_minus_2088",
            "2089_anomaly_fraction",
        ],
        ascending=False,
    )
    channel_comparison.to_csv(
        safe_output(OUT / "run2088_vs_2089_channel_comparison.csv"),
        index=False,
    )

    # Per-run feature summaries and normalized comparison.
    feature_summaries = {}
    for run in RUNS:
        run_features = feature_long[feature_long["run"] == run]
        rows = []
        for feature, group in run_features.groupby("triggered_feature"):
            alert_group = group[group["strict_status"] == "ALERT"]
            mechanism_counts = alert_group["alert_mechanism"].value_counts()
            rows.append(
                {
                    "triggered_feature": feature,
                    "overall_occurrence_count": int(len(group)),
                    "overall_rate_per_sampled_subrun": len(group)
                    / EXPECTED[run]["total"],
                    "anomalous_file_count": int(group["filename"].nunique()),
                    "anomalous_file_fraction": group["filename"].nunique()
                    / EXPECTED[run]["total"],
                    "ALERT_occurrence_count": int(len(alert_group)),
                    "ALERT_occurrence_rate_per_sampled_subrun": (
                        len(alert_group) / EXPECTED[run]["total"]
                    ),
                    "ALERT_file_count": int(
                        alert_group["filename"].nunique()
                    ),
                    "ALERT_file_presence_fraction": (
                        alert_group["filename"].nunique()
                        / EXPECTED[run]["ALERT"]
                    ),
                    "extreme_only_ALERT_occurrences": int(
                        mechanism_counts.get("extreme only", 0)
                    ),
                    "bulk_only_ALERT_occurrences": int(
                        mechanism_counts.get("bulk only", 0)
                    ),
                    "bulk_extreme_ALERT_occurrences": int(
                        mechanism_counts.get("bulk + extreme", 0)
                    ),
                    "other_ALERT_mechanism_occurrences": int(
                        sum(
                            count
                            for label, count in mechanism_counts.items()
                            if label
                            not in [
                                "extreme only",
                                "bulk only",
                                "bulk + extreme",
                            ]
                        )
                    ),
                }
            )
        summary = pd.DataFrame(rows).sort_values(
            ["overall_rate_per_sampled_subrun", "triggered_feature"],
            ascending=[False, True],
        )
        feature_summaries[run] = summary
        summary.to_csv(
            safe_output(OUT / f"run{run}_feature_summary.csv"),
            index=False,
        )

    feature_union = sorted(
        set(feature_summaries[2088]["triggered_feature"])
        | set(feature_summaries[2089]["triggered_feature"])
    )
    feature_comparison_rows = []
    for feature in feature_union:
        values = {}
        for run in RUNS:
            summary = feature_summaries[run].set_index(
                "triggered_feature"
            )
            if feature in summary.index:
                values[run] = summary.loc[feature]
            else:
                values[run] = None
        count88 = (
            int(values[2088]["overall_occurrence_count"])
            if values[2088] is not None
            else 0
        )
        count89 = (
            int(values[2089]["overall_occurrence_count"])
            if values[2089] is not None
            else 0
        )
        rate88 = count88 / EXPECTED[2088]["total"]
        rate89 = count89 / EXPECTED[2089]["total"]
        feature_comparison_rows.append(
            {
                "feature": feature,
                "2088_count": count88,
                "2089_count": count89,
                "2088_rate_per_sampled_subrun": rate88,
                "2089_rate_per_sampled_subrun": rate89,
                "rate_difference_2089_minus_2088": rate89 - rate88,
                "rate_ratio_2089_over_2088": (
                    rate89 / rate88 if rate88 > 0 else math.nan
                ),
                "new_feature_in_2089": rate88 == 0 and rate89 > 0,
            }
        )
    feature_comparison = pd.DataFrame(feature_comparison_rows).sort_values(
        ["rate_difference_2089_minus_2088", "2089_rate_per_sampled_subrun"],
        ascending=False,
    )
    feature_comparison.to_csv(
        safe_output(OUT / "run2088_vs_2089_feature_comparison.csv"),
        index=False,
    )

    # Method comparison.
    method_rows = []
    for run in RUNS:
        run_anomalies = anomalies[anomalies["run"] == run]
        for method in METHOD_ORDER:
            group = run_anomalies[
                run_anomalies["method_class"] == method
            ]
            method_rows.append(
                {
                    "run": run,
                    "method": method,
                    "row_count": int(len(group)),
                    "row_fraction_of_anomalous_rows": (
                        len(group) / len(run_anomalies)
                    ),
                    "row_rate_per_sampled_subrun": (
                        len(group) / EXPECTED[run]["total"]
                    ),
                    "file_count_with_method": int(
                        group["filename"].nunique()
                    ),
                    "file_fraction_of_sampled_subruns": (
                        group["filename"].nunique()
                        / EXPECTED[run]["total"]
                    ),
                    "ALERT_file_count_with_method": int(
                        group.loc[
                            group["strict_status"] == "ALERT", "filename"
                        ].nunique()
                    ),
                    "ALERT_file_presence_fraction": (
                        group.loc[
                            group["strict_status"] == "ALERT", "filename"
                        ].nunique()
                        / EXPECTED[run]["ALERT"]
                    ),
                }
            )
    method_summary = pd.DataFrame(method_rows)
    method_summary.to_csv(
        safe_output(OUT / "run2088_2089_method_summary.csv"),
        index=False,
    )

    # Channel x feature matrices and normalized comparison.
    channel_feature_matrices = {}
    for run in RUNS:
        run_features = feature_long[feature_long["run"] == run]
        matrix = pd.crosstab(
            run_features["channel"], run_features["triggered_feature"]
        ).reindex(
            index=range(96), columns=feature_union, fill_value=0
        )
        matrix.index.name = "channel"
        channel_feature_matrices[run] = matrix
        matrix.reset_index().to_csv(
            safe_output(OUT / f"run{run}_channel_feature_matrix.csv"),
            index=False,
        )
    pair_rows = []
    for channel in range(96):
        for feature in feature_union:
            count88 = int(
                channel_feature_matrices[2088].loc[channel, feature]
            )
            count89 = int(
                channel_feature_matrices[2089].loc[channel, feature]
            )
            if count88 == 0 and count89 == 0:
                continue
            rate88 = count88 / EXPECTED[2088]["total"]
            rate89 = count89 / EXPECTED[2089]["total"]
            pair_rows.append(
                {
                    "channel": channel,
                    "feature": feature,
                    "count_2088": count88,
                    "count_2089": count89,
                    "normalized_rate_2088": rate88,
                    "normalized_rate_2089": rate89,
                    "rate_change_2089_minus_2088": rate89 - rate88,
                    "rate_ratio_2089_over_2088": (
                        rate89 / rate88 if rate88 > 0 else math.nan
                    ),
                    "new_pair_in_2089": count88 == 0 and count89 > 0,
                }
            )
    pair_comparison = pd.DataFrame(pair_rows).sort_values(
        ["rate_change_2089_minus_2088", "normalized_rate_2089"],
        ascending=False,
    )
    pair_comparison.to_csv(
        safe_output(
            OUT / "run2088_vs_2089_channel_feature_comparison.csv"
        ),
        index=False,
    )

    # ALERT matrices and within/cross-run Jaccard summaries.
    alert_channel_sets = {}
    alert_feature_sets = {}
    similarity_rows = []
    for run in RUNS:
        run_timeline = timeline[
            (timeline["run"] == run)
            & timeline["strict_status"].eq("ALERT")
        ].sort_values("sequence_index_within_run")
        alert_names = run_timeline["filename"].tolist()
        run_anomalies = anomalies[
            (anomalies["run"] == run)
            & anomalies["filename"].isin(alert_names)
        ]
        channel_matrix = pd.crosstab(
            run_anomalies["filename"], run_anomalies["channel"].astype(int)
        ).clip(upper=1).reindex(
            index=alert_names, columns=range(96), fill_value=0
        )
        channel_matrix.columns = [
            f"ch{channel}" for channel in range(96)
        ]
        channel_matrix.insert(
            0,
            "subrun",
            channel_matrix.index.map(
                run_timeline.set_index("filename")["subrun"]
            ),
        )
        channel_matrix.insert(
            0,
            "sequence_index_within_run",
            channel_matrix.index.map(
                run_timeline.set_index("filename")[
                    "sequence_index_within_run"
                ]
            ),
        )
        channel_matrix.reset_index().to_csv(
            safe_output(OUT / f"run{run}_alert_channel_matrix.csv"),
            index=False,
        )
        run_feature_long = feature_long[
            (feature_long["run"] == run)
            & feature_long["filename"].isin(alert_names)
        ]
        feature_matrix = pd.crosstab(
            run_feature_long["filename"],
            run_feature_long["triggered_feature"],
        ).reindex(
            index=alert_names, columns=feature_union, fill_value=0
        )
        feature_matrix.insert(
            0,
            "subrun",
            feature_matrix.index.map(
                run_timeline.set_index("filename")["subrun"]
            ),
        )
        feature_matrix.insert(
            0,
            "sequence_index_within_run",
            feature_matrix.index.map(
                run_timeline.set_index("filename")[
                    "sequence_index_within_run"
                ]
            ),
        )
        feature_matrix.reset_index().to_csv(
            safe_output(OUT / f"run{run}_alert_feature_matrix.csv"),
            index=False,
        )
        alert_channel_sets[run] = [
            set(
                run_anomalies.loc[
                    run_anomalies["filename"] == filename, "channel"
                ].astype(int)
            )
            for filename in alert_names
        ]
        alert_feature_sets[run] = [
            set(
                run_feature_long.loc[
                    run_feature_long["filename"] == filename,
                    "triggered_feature",
                ]
            )
            for filename in alert_names
        ]
    for representation, sets in [
        ("channel", alert_channel_sets),
        ("feature", alert_feature_sets),
    ]:
        for comparison, left_run, right_run, cross in [
            ("within_run2088", 2088, 2088, False),
            ("within_run2089", 2089, 2089, False),
            ("cross_run2088_vs_2089", 2088, 2089, True),
        ]:
            stats = similarity_stats(
                sets[left_run],
                sets[right_run] if cross else None,
            )
            similarity_rows.append(
                {
                    "representation": representation,
                    "comparison": comparison,
                    "left_run": left_run,
                    "right_run": right_run,
                    **stats,
                }
            )
    similarity_summary = pd.DataFrame(similarity_rows)
    similarity_summary.to_csv(
        safe_output(OUT / "run2088_2089_similarity_summary.csv"),
        index=False,
    )

    # Temporal quartiles and boundary windows.
    quartile_rows = []
    boundary_rows = []
    for run in RUNS:
        run_timeline = timeline[timeline["run"] == run].sort_values(
            "sequence_index_within_run"
        ).copy()
        n = len(run_timeline)
        run_timeline["quartile_number"] = (
            run_timeline["sequence_index_within_run"] * 4 // n + 1
        ).clip(upper=4)
        for quartile, group in run_timeline.groupby("quartile_number"):
            quartile_rows.append(
                {
                    "run": run,
                    "quartile": f"Q{int(quartile)}",
                    "sequence_index_start": int(
                        group["sequence_index_within_run"].min()
                    ),
                    "sequence_index_end": int(
                        group["sequence_index_within_run"].max()
                    ),
                    "n_files": int(len(group)),
                    "n_ALERT": int(
                        group["strict_status"].eq("ALERT").sum()
                    ),
                    "ALERT_fraction": float(
                        group["strict_status"].eq("ALERT").mean()
                    ),
                    "n_bulk": int(group["bulk_alert"].sum()),
                    "bulk_rate": float(group["bulk_alert"].mean()),
                    "n_extreme": int(group["extreme_alert"].sum()),
                    "extreme_rate": float(group["extreme_alert"].mean()),
                    "n_persistent": int(group["persistent_alert"].sum()),
                    "persistent_rate": float(
                        group["persistent_alert"].mean()
                    ),
                }
            )
        for window_size in [10, 20, 40]:
            for position, group in [
                ("beginning", run_timeline.head(window_size)),
                ("end", run_timeline.tail(window_size)),
            ]:
                boundary_rows.append(
                    {
                        "run": run,
                        "position": position,
                        "window_size": window_size,
                        "sequence_index_start": int(
                            group["sequence_index_within_run"].min()
                        ),
                        "sequence_index_end": int(
                            group["sequence_index_within_run"].max()
                        ),
                        "n_ALERT": int(
                            group["strict_status"].eq("ALERT").sum()
                        ),
                        "ALERT_fraction": float(
                            group["strict_status"].eq("ALERT").mean()
                        ),
                        "n_bulk": int(group["bulk_alert"].sum()),
                        "n_extreme": int(group["extreme_alert"].sum()),
                        "n_persistent": int(group["persistent_alert"].sum()),
                    }
                )
    temporal_quartiles = pd.DataFrame(quartile_rows)
    temporal_quartiles.to_csv(
        safe_output(OUT / "run2088_2089_temporal_quartiles.csv"),
        index=False,
    )
    boundary_summary = pd.DataFrame(boundary_rows)
    boundary_summary.to_csv(
        safe_output(OUT / "run2088_2089_boundary_summary.csv"),
        index=False,
    )

    # Approximately four unique log-level representatives per run.
    representative_rows = []
    for run in RUNS:
        alerts = timeline[
            (timeline["run"] == run)
            & timeline["strict_status"].eq("ALERT")
        ].copy()
        selected: set[str] = set()
        typical = select_typical(alerts, selected)
        add_representative(
            representative_rows,
            selected,
            typical,
            "typical extreme-only ALERT (modal anomaly count; near median severity/sequence)",
            anomalies,
            feature_long,
        )
        largest_n = (
            alerts[~alerts["filename"].isin(selected)]
            .sort_values(
                [
                    "n_anomalous_channels",
                    "max_z_over_file",
                    "sequence_index_within_run",
                ],
                ascending=[False, False, True],
            )
            .iloc[0]
        )
        add_representative(
            representative_rows,
            selected,
            largest_n,
            "largest n_anomalous_channels",
            anomalies,
            feature_long,
        )
        largest_z = (
            alerts[~alerts["filename"].isin(selected)]
            .sort_values(
                [
                    "max_z_over_file",
                    "n_anomalous_channels",
                    "sequence_index_within_run",
                ],
                ascending=[False, False, True],
            )
            .iloc[0]
        )
        add_representative(
            representative_rows,
            selected,
            largest_z,
            "largest max_z among remaining ALERTs",
            anomalies,
            feature_long,
        )
        secondary = alerts[
            alerts["mechanism"].isin(["bulk only", "bulk + extreme"])
            & ~alerts["filename"].isin(selected)
        ].copy()
        if len(secondary):
            secondary = secondary.sort_values(
                [
                    "mechanism",
                    "n_anomalous_channels",
                    "max_z_over_file",
                ],
                ascending=[True, False, False],
            ).iloc[0]
            reason = "representative secondary bulk-involving mechanism"
        else:
            secondary = select_typical(alerts, selected)
            reason = (
                "additional representative of dominant extreme-only mechanism "
                "(secondary mechanism already selected or absent)"
            )
        add_representative(
            representative_rows,
            selected,
            secondary,
            reason,
            anomalies,
            feature_long,
        )
        if len(selected) != 4:
            fail(f"run {run} representative selection is not 4 unique files")
    representatives = pd.DataFrame(representative_rows)
    representatives.to_csv(
        safe_output(OUT / "run2088_2089_representative_subruns.csv"),
        index=False,
    )

    # Plots: four separate timelines for each run.
    for run in RUNS:
        run_timeline = timeline[timeline["run"] == run].sort_values(
            "sequence_index_within_run"
        )
        x = run_timeline["sequence_index_within_run"].to_numpy()
        status_y = run_timeline["strict_status"].map(
            {"OK": 0, "ALERT": 1}
        ).to_numpy()
        status_color = run_timeline["strict_status"].map(
            {"OK": "#bdbdbd", "ALERT": "#d95f02"}
        ).to_numpy()
        plt.figure(figsize=(12, 3.8))
        plt.scatter(x, status_y, c=status_color, s=22, alpha=0.85)
        plt.yticks([0, 1], ["OK", "ALERT"])
        plt.xlabel("Processed-file sequence index")
        plt.title(f"Run {run}: strict status in successful processed order")
        savefig(PLOTS / f"run{run}_strict_status_timeline.png")

        plt.figure(figsize=(12, 4.2))
        plt.plot(
            x,
            run_timeline["n_anomalous_channels"].to_numpy(),
            marker="o",
            markersize=2.7,
            linewidth=0.7,
            color=RUN_COLORS[run],
        )
        plt.axhline(5, linestyle="--", color="#c44e52", label="bulk threshold")
        plt.xlabel("Processed-file sequence index")
        plt.ylabel("n_anomalous_channels")
        plt.title(f"Run {run}: anomalous-channel count")
        plt.legend()
        savefig(PLOTS / f"run{run}_n_anomalous_channels_timeline.png")

        plt.figure(figsize=(12, 4.2))
        plt.plot(
            x,
            run_timeline["n_persistent_channels"].to_numpy(),
            marker="o",
            markersize=2.7,
            linewidth=0.7,
            color=RUN_COLORS[run],
        )
        plt.axhline(
            2, linestyle="--", color="#c44e52", label="persistence threshold"
        )
        plt.xlabel("Processed-file sequence index")
        plt.ylabel("n_persistent_channels")
        plt.title(f"Run {run}: persistent-channel count")
        plt.legend()
        savefig(PLOTS / f"run{run}_n_persistent_channels_timeline.png")

        finite_positive = run_timeline["max_z_over_file"].clip(
            lower=0.1
        ).to_numpy()
        plt.figure(figsize=(12, 4.2))
        plt.plot(
            x,
            finite_positive,
            marker="o",
            markersize=2.7,
            linewidth=0.7,
            color=RUN_COLORS[run],
        )
        plt.axhline(15, linestyle="--", color="#c44e52", label="extreme threshold")
        plt.yscale("log")
        plt.xlabel("Processed-file sequence index")
        plt.ylabel("max_z_over_file (log scale)")
        plt.title(f"Run {run}: maximum channel z score")
        plt.legend()
        savefig(PLOTS / f"run{run}_max_z_over_file_timeline.png")

    plt.figure(figsize=(12, 4.6))
    for run in RUNS:
        run_timeline = timeline[timeline["run"] == run].sort_values(
            "sequence_index_within_run"
        )
        progress = (
            run_timeline["sequence_index_within_run"]
            / max(len(run_timeline) - 1, 1)
            * 100
        ).to_numpy()
        alert = (
            run_timeline["strict_status"].eq("ALERT").astype(int).to_numpy()
        )
        plt.scatter(
            progress[alert == 1],
            np.full(int(alert.sum()), run),
            marker="|",
            s=150,
            linewidth=1.4,
            color=RUN_COLORS[run],
            label=f"Run {run} ALERT",
        )
    plt.yticks(RUNS, [str(run) for run in RUNS])
    plt.xlabel("Normalized progress through run (%)")
    plt.title("ALERT occurrence through normalized run progress")
    plt.legend()
    savefig(PLOTS / "run2088_2089_normalized_alert_progress.png")

    exclusive_plot = condition_summary[
        condition_summary["summary_type"] == "exclusive_combination"
    ]
    labels = [item[0] for item in MECHANISM_COMBINATIONS]
    x = np.arange(len(labels))
    width = 0.36
    plt.figure(figsize=(13, 5.5))
    for offset, run in zip([-width / 2, width / 2], RUNS):
        values = (
            exclusive_plot[exclusive_plot["run"] == run]
            .set_index("condition")
            .reindex(labels)["rate_per_sampled_subrun"]
            * 100
        )
        plt.bar(
            x + offset,
            values.to_numpy(),
            width,
            label=str(run),
            color=RUN_COLORS[run],
        )
    plt.xticks(x, labels, rotation=35, ha="right")
    plt.ylabel("Rate per sampled subrun (%)")
    plt.title("Run 2088 vs 2089 exclusive ALERT mechanisms")
    plt.legend()
    savefig(PLOTS / "run2088_2089_alert_mechanism_comparison.png")

    # Channel comparison plots.
    plt.figure(figsize=(7, 7))
    plt.scatter(
        channel_comparison["2088_anomaly_fraction"].to_numpy(),
        channel_comparison["2089_anomaly_fraction"].to_numpy(),
        color="#4c72b0",
        alpha=0.75,
    )
    limit = float(
        max(
            channel_comparison["2088_anomaly_fraction"].max(),
            channel_comparison["2089_anomaly_fraction"].max(),
        )
        * 1.08
    )
    plt.plot([0, limit], [0, limit], linestyle="--", color="#666666")
    top_labels = channel_comparison.head(10)
    for row in top_labels.itertuples(index=False):
        plt.annotate(
            f"ch{row.channel}",
            (row._1, row._2),
            fontsize=8,
            xytext=(3, 3),
            textcoords="offset points",
        )
    plt.xlim(0, limit)
    plt.ylim(0, limit)
    plt.xlabel("Run 2088 anomalous fraction")
    plt.ylabel("Run 2089 anomalous fraction")
    plt.title("Per-channel anomaly frequency comparison")
    savefig(PLOTS / "run2088_vs_2089_channel_fraction_scatter.png")

    top_changes = channel_comparison.head(20).sort_values(
        "anomaly_fraction_difference_2089_minus_2088"
    )
    plt.figure(figsize=(10, 6))
    plt.barh(
        [f"ch{v}" for v in top_changes["channel"]],
        (
            top_changes[
                "anomaly_fraction_difference_2089_minus_2088"
            ].to_numpy()
            * 100
        ),
        color="#dd8452",
    )
    plt.xlabel("Anomaly fraction change, 2089 - 2088 (percentage points)")
    plt.title("Largest per-channel anomaly-rate increases in run 2089")
    savefig(PLOTS / "run2088_vs_2089_channel_rate_increases.png")

    # Feature comparison plot excluding IF-only placeholder.
    feature_plot = feature_comparison[
        feature_comparison["feature"] != "<none; IF-only>"
    ].copy()
    feature_plot["_max_rate"] = feature_plot[
        [
            "2088_rate_per_sampled_subrun",
            "2089_rate_per_sampled_subrun",
        ]
    ].max(axis=1)
    feature_plot = feature_plot.nlargest(15, "_max_rate").sort_values(
        "_max_rate"
    )
    y = np.arange(len(feature_plot))
    plt.figure(figsize=(11, 7))
    plt.barh(
        y - 0.18,
        feature_plot["2088_rate_per_sampled_subrun"].to_numpy() * 100,
        0.36,
        color=RUN_COLORS[2088],
        label="2088",
    )
    plt.barh(
        y + 0.18,
        feature_plot["2089_rate_per_sampled_subrun"].to_numpy() * 100,
        0.36,
        color=RUN_COLORS[2089],
        label="2089",
    )
    plt.yticks(y, feature_plot["feature"])
    plt.xlabel("Triggered occurrences per sampled subrun (%)")
    plt.title("Normalized triggered-feature frequency")
    plt.legend()
    savefig(PLOTS / "run2088_vs_2089_feature_rate_comparison.png")

    # Method rate comparison.
    x = np.arange(len(METHOD_ORDER))
    width = 0.36
    plt.figure(figsize=(11, 5.2))
    for offset, run in zip([-width / 2, width / 2], RUNS):
        values = (
            method_summary[method_summary["run"] == run]
            .set_index("method")
            .reindex(METHOD_ORDER)["row_rate_per_sampled_subrun"]
            * 100
        )
        plt.bar(
            x + offset,
            values.to_numpy(),
            width,
            color=RUN_COLORS[run],
            label=str(run),
        )
    plt.xticks(x, METHOD_ORDER, rotation=30, ha="right")
    plt.ylabel("Anomalous rows per sampled subrun (%)")
    plt.title("Normalized anomaly-method composition")
    plt.legend()
    savefig(PLOTS / "run2088_2089_method_rate_comparison.png")

    # Top channel-feature rate changes.
    pair_plot = pair_comparison.head(20).sort_values(
        "rate_change_2089_minus_2088"
    )
    plt.figure(figsize=(12, 7))
    labels = [
        f"ch{channel} / {feature}"
        for channel, feature in zip(
            pair_plot["channel"], pair_plot["feature"]
        )
    ]
    plt.barh(
        labels,
        pair_plot["rate_change_2089_minus_2088"].to_numpy() * 100,
        color="#dd8452",
    )
    plt.xlabel("Rate change, 2089 - 2088 (occurrences per 100 files)")
    plt.title("Largest normalized channel-feature increases")
    savefig(PLOTS / "run2088_vs_2089_channel_feature_rate_changes.png")

    # Temporal quartile comparison.
    qlabels = ["Q1", "Q2", "Q3", "Q4"]
    x = np.arange(4)
    width = 0.36
    plt.figure(figsize=(9, 5))
    for offset, run in zip([-width / 2, width / 2], RUNS):
        values = (
            temporal_quartiles[temporal_quartiles["run"] == run]
            .set_index("quartile")
            .reindex(qlabels)["ALERT_fraction"]
            * 100
        )
        plt.bar(
            x + offset,
            values.to_numpy(),
            width,
            color=RUN_COLORS[run],
            label=str(run),
        )
    plt.xticks(x, qlabels)
    plt.ylabel("ALERT fraction within quartile (%)")
    plt.title("Temporal quartile ALERT-rate comparison")
    plt.legend()
    savefig(PLOTS / "run2088_2089_temporal_quartile_comparison.png")

    # Machine-readable synthesis metrics.
    metrics = {
        "status": {
            str(run): {
                "total": EXPECTED[run]["total"],
                "OK": EXPECTED[run]["OK"],
                "ALERT": EXPECTED[run]["ALERT"],
                "WARN": 0,
                "PEND": 0,
                "non_ALERT_fraction": EXPECTED[run]["OK"]
                / EXPECTED[run]["total"],
            }
            for run in RUNS
        },
        "path_order_verified": {
            str(run): path_order_verified[run] for run in RUNS
        },
        "alert_conditions": condition_summary.to_dict("records"),
        "top_channel_rate_increases": channel_comparison.head(20).to_dict(
            "records"
        ),
        "new_channels_2089": channel_comparison.loc[
            channel_comparison["new_anomalous_channel_in_2089"], "channel"
        ].astype(int).tolist(),
        "top_feature_rate_increases": feature_comparison.head(20).to_dict(
            "records"
        ),
        "top_channel_feature_rate_increases": pair_comparison.head(25).to_dict(
            "records"
        ),
        "methods": method_summary.to_dict("records"),
        "similarity": similarity_summary.to_dict("records"),
        "temporal_quartiles": temporal_quartiles.to_dict("records"),
        "boundary_windows": boundary_summary.to_dict("records"),
        "representatives": representatives.to_dict("records"),
        "production_inputs_unchanged": True,
        "raw_csv_files_read": 0,
        "root_files_read": 0,
    }
    after_stats = {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in required
    }
    if before_stats != after_stats:
        fail("one or more authoritative inputs changed during diagnosis")
    with safe_output(OUT / "run2088_2089_diagnostic_metrics.json").open(
        "w"
    ) as handle:
        json.dump(json_clean(metrics), handle, indent=2, allow_nan=False)

    print("Run 2088/2089 model-log diagnosis tables and plots complete.")
    print(
        json.dumps(
            {
                "files": {run: EXPECTED[run]["total"] for run in RUNS},
                "alerts": {run: EXPECTED[run]["ALERT"] for run in RUNS},
                "anomalous_rows": {
                    run: int((anomalies["run"] == run).sum())
                    for run in RUNS
                },
                "representative_subruns": {
                    run: representatives.loc[
                        representatives["run"] == run, "subrun"
                    ].astype(int).tolist()
                    for run in RUNS
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
