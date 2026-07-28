#!/usr/bin/env python3
"""Read-only detailed diagnosis of run 2014 for the reproduced Juan model."""

from __future__ import annotations

import json
import math
import os
import re
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
LOG = IF_DIR / "logs" / f"{TAG}.csv"
PATH_CACHE = IF_DIR / "logs" / f"{TAG}_paths.txt"
STEP1_DIR = (
    IF_DIR
    / "analysis"
    / "juan_bad_run_diagnosis"
    / "step1_classification"
)
SUBRUN_CLASSIFICATION = STEP1_DIR / "subrun_classification.csv"
RUN_CLASSIFICATION = STEP1_DIR / "run_classification.csv"
MODEL_DIR = IF_DIR / "models" / TAG
OUT = (
    IF_DIR
    / "analysis"
    / "juan_bad_run_diagnosis"
    / "run2014"
)
REP_OUT = OUT / "representative_subruns"
RUN = 2014
EXPECTED_STATUS = {"OK": 213, "WARN": 77, "ALERT": 71, "PEND": 0}
EXPECTED_N = 361
STATUS_ORDER = ["OK", "WARN", "ALERT"]
STATUS_COLORS = {"OK": "#3274a1", "WARN": "#e69500", "ALERT": "#d62728"}
ALERT_COMBINATIONS = [
    ("persistent only", True, False, False),
    ("bulk only", False, True, False),
    ("extreme only", False, False, True),
    ("persistent + bulk", True, True, False),
    ("persistent + extreme", True, False, True),
    ("bulk + extreme", False, True, True),
    ("persistent + bulk + extreme", True, True, True),
]


def fail(message: str) -> "None":
    raise RuntimeError(f"SANITY CHECK FAILED: {message}")


def safe_output(path: Path) -> Path:
    if OUT not in path.parents and path != OUT:
        fail(f"attempted output outside run2014 analysis directory: {path}")
    return path


def savefig(path: Path) -> None:
    safe_output(path)
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()


def as_bool(series: pd.Series, name: str) -> pd.Series:
    if series.dtype == bool:
        return series
    normalized = series.astype(str).str.strip().str.lower()
    if not normalized.isin(["true", "false"]).all():
        fail(f"{name} contains non-boolean values")
    return normalized.eq("true")


def contiguous_segments(
    timeline: pd.DataFrame, selector, label: str
) -> list[dict[str, object]]:
    mask = timeline.apply(selector, axis=1).tolist()
    segments: list[dict[str, object]] = []
    start: int | None = None
    for position, active in enumerate(mask + [False]):
        if active and start is None:
            start = position
        elif not active and start is not None:
            end = position - 1
            first = timeline.iloc[start]
            last = timeline.iloc[end]
            statuses = timeline.iloc[start : end + 1]["strict_status"]
            segments.append(
                {
                    "segment_type": label,
                    "start_sequence_index": int(first["sequence_index"]),
                    "end_sequence_index": int(last["sequence_index"]),
                    "start_subrun": int(first["subrun"]),
                    "end_subrun": int(last["subrun"]),
                    "length": end - start + 1,
                    "n_OK": int((statuses == "OK").sum()),
                    "n_WARN": int((statuses == "WARN").sum()),
                    "n_ALERT": int((statuses == "ALERT").sum()),
                }
            )
            start = None
    return segments


def longest_true_streak(flags: list[bool]) -> int:
    best = current = 0
    for flag in flags:
        if flag:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def representative_row(
    group: pd.DataFrame, selected: set[str], status: str
) -> pd.Series:
    available = group[~group["filename"].isin(selected)].copy()
    if available.empty:
        fail(f"no unique {status} representative candidate")
    mode_bad = int(available["n_anomalous_channels"].mode().iloc[0])
    candidates = available[available["n_anomalous_channels"] == mode_bad].copy()
    target_z = candidates["max_z_over_file"].median()
    target_seq = candidates["sequence_index"].median()
    candidates["_distance"] = (
        (candidates["max_z_over_file"] - target_z).abs()
        + (candidates["sequence_index"] - target_seq).abs()
        / max(len(group), 1)
    )
    return candidates.sort_values(
        ["_distance", "sequence_index"]
    ).iloc[0]


def add_representative(
    selected_rows: list[dict[str, object]],
    selected_names: set[str],
    row: pd.Series,
    reason: str,
) -> None:
    if row["filename"] in selected_names:
        fail(f"duplicate representative selected: {row['filename']}")
    selected_names.add(str(row["filename"]))
    selected_rows.append(
        {
            "filename": row["filename"],
            "subrun": int(row["subrun"]),
            "status": row["strict_status"],
            "selection_reason": reason,
            "n_anomalous_channels": int(row["n_anomalous_channels"]),
            "n_persistent_channels": int(row["n_persistent_channels"]),
            "max_z_over_file": float(row["max_z_over_file"]),
            "persistent_alert": bool(row["persistent_alert"]),
            "bulk_alert": bool(row["bulk_alert"]),
            "extreme_alert": bool(row["extreme_alert"]),
        }
    )


def main() -> None:
    sys.path.insert(0, str(IF_DIR))
    from src.plot import _load_models, plot_file
    from src.run_list import parse_run_subrun

    required = [
        LOG,
        PATH_CACHE,
        SUBRUN_CLASSIFICATION,
        RUN_CLASSIFICATION,
        MODEL_DIR / "reference.npz",
        MODEL_DIR / "detector.pkl",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        fail(f"missing required inputs: {missing}")

    allowed_preexisting = {OUT / "analyze_run2014.py"}
    if OUT.exists():
        unexpected = [
            path
            for path in OUT.rglob("*")
            if path.is_file() and path not in allowed_preexisting
        ]
        if unexpected:
            fail(f"run2014 output directory is not new/empty: {unexpected}")

    production_inputs = [
        LOG,
        PATH_CACHE,
        SUBRUN_CLASSIFICATION,
        RUN_CLASSIFICATION,
        MODEL_DIR / "reference.npz",
        MODEL_DIR / "detector.pkl",
        MODEL_DIR / "config.yaml",
        MODEL_DIR / "training_metadata.json",
    ]
    before_stats = {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in production_inputs
    }

    step1 = pd.read_csv(SUBRUN_CLASSIFICATION)
    run_row = pd.read_csv(RUN_CLASSIFICATION).query("run == @RUN")
    if len(run_row) != 1:
        fail(f"run classification has {len(run_row)} rows for run {RUN}")
    rr = run_row.iloc[0]
    expected_run_row = {
        "n_sampled_subruns": 361,
        "n_OK": 213,
        "n_WARN": 77,
        "n_PEND": 0,
        "n_ALERT": 71,
    }
    for column, expected in expected_run_row.items():
        if int(rr[column]) != expected:
            fail(f"run_classification {column}={rr[column]} != {expected}")

    timeline = step1.query("run == @RUN").copy()
    if len(timeline) != EXPECTED_N:
        fail(f"Step 1 has {len(timeline)} run-2014 rows, expected {EXPECTED_N}")
    for column in [
        "persistent_alert",
        "bulk_alert",
        "extreme_alert",
        "raw_bad",
    ]:
        timeline[column] = as_bool(timeline[column], column)
    actual_status = timeline["strict_status"].value_counts().to_dict()
    for status, expected in EXPECTED_STATUS.items():
        if int(actual_status.get(status, 0)) != expected:
            fail(
                f"run-2014 {status} count={actual_status.get(status, 0)} "
                f"!= {expected}"
            )
    if set(timeline["strict_status"]) - set(EXPECTED_STATUS):
        fail(f"unexpected Step-1 statuses: {set(timeline['strict_status'])}")

    timeline = timeline.sort_values("sequence_index_within_run").reset_index(
        drop=True
    )
    expected_indices = list(range(EXPECTED_N))
    if timeline["sequence_index_within_run"].tolist() != expected_indices:
        fail("Step-1 sequence indices are not exactly 0..360")
    timeline = timeline.rename(
        columns={"sequence_index_within_run": "sequence_index"}
    )

    processed_paths = PATH_CACHE.read_text().splitlines()
    run_paths = [
        path for path in processed_paths if parse_run_subrun(path)[0] == RUN
    ]
    if len(run_paths) != EXPECTED_N:
        fail(f"processed path cache has {len(run_paths)} run-2014 files")
    path_by_filename = {Path(path).name: path for path in run_paths}
    if list(path_by_filename) != timeline["filename"].tolist():
        fail("Step-1 run-2014 order differs from successful path-cache order")
    if timeline.duplicated(["run", "subrun"]).any():
        fail("duplicate run/subrun in run-2014 timeline")

    # Read the authoritative log and attach strict status.
    log = pd.read_csv(LOG)
    required_log_columns = {
        "filename",
        "channel",
        "anomalous",
        "method",
        "triggered_features",
        "max_z",
        "if_score",
    }
    if required_log_columns - set(log.columns):
        fail(f"log missing columns: {required_log_columns - set(log.columns)}")
    run_names = set(timeline["filename"])
    run_log = log[log["filename"].isin(run_names)].copy()
    del log
    if set(run_log["filename"]) != run_names:
        fail("run-2014 log filenames do not exactly match timeline filenames")
    if run_log.duplicated(["filename", "channel"]).any():
        fail("duplicate run-2014 filename/channel rows")
    run_log["anomalous"] = as_bool(run_log["anomalous"], "anomalous")
    status_map = timeline.set_index("filename")["strict_status"]
    sequence_map = timeline.set_index("filename")["sequence_index"]
    run_log["strict_status"] = run_log["filename"].map(status_map)
    run_log["sequence_index"] = run_log["filename"].map(sequence_map)
    if run_log["strict_status"].isna().any():
        fail("status join produced missing values")

    # Reconfirm alert decomposition encoded by Step 1.
    calculated_alert = (
        timeline["persistent_alert"]
        | timeline["bulk_alert"]
        | timeline["extreme_alert"]
    )
    if not (
        calculated_alert
        == timeline["strict_status"].eq("ALERT")
    ).all():
        fail("Step-1 alert flags do not exactly reproduce strict ALERT status")
    if timeline.iloc[:4]["persistent_alert"].any():
        fail("persistence appears before five processed run-2014 files")

    # Part 1: compact timeline.
    timeline_columns = [
        "sequence_index",
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
    timeline_out = timeline[timeline_columns].copy()

    # Temporal segments for quantitative synthesis.
    temporal_segments: list[dict[str, object]] = []
    temporal_segments.extend(
        contiguous_segments(
            timeline, lambda row: row["strict_status"] == "ALERT", "ALERT"
        )
    )
    temporal_segments.extend(
        contiguous_segments(
            timeline, lambda row: row["strict_status"] == "WARN", "WARN"
        )
    )
    temporal_segments.extend(
        contiguous_segments(
            timeline, lambda row: row["strict_status"] != "OK", "NON_OK"
        )
    )
    segments_df = pd.DataFrame(temporal_segments).sort_values(
        ["segment_type", "start_sequence_index"]
    )

    # Part 2: mutually exclusive alert-condition combinations and simple totals.
    alert_rows = timeline[timeline["strict_status"] == "ALERT"]
    condition_rows: list[dict[str, object]] = []
    for label, persistence, bulk, extreme in ALERT_COMBINATIONS:
        mask = (
            alert_rows["persistent_alert"].eq(persistence)
            & alert_rows["bulk_alert"].eq(bulk)
            & alert_rows["extreme_alert"].eq(extreme)
        )
        count = int(mask.sum())
        condition_rows.append(
            {
                "summary_type": "exclusive_combination",
                "condition": label,
                "count": count,
                "fraction_of_71_alerts": count / len(alert_rows),
            }
        )
    for label, column in [
        ("involving persistence", "persistent_alert"),
        ("involving bulk", "bulk_alert"),
        ("involving extreme", "extreme_alert"),
    ]:
        count = int(alert_rows[column].sum())
        condition_rows.append(
            {
                "summary_type": "simple_total",
                "condition": label,
                "count": count,
                "fraction_of_71_alerts": count / len(alert_rows),
            }
        )
    condition_df = pd.DataFrame(condition_rows)
    exclusive_total = int(
        condition_df.query("summary_type == 'exclusive_combination'")[
            "count"
        ].sum()
    )
    if exclusive_total != 71:
        fail(f"exclusive alert-condition counts sum to {exclusive_total}, not 71")

    # Part 3: one row per channel.
    channels = sorted(run_log["channel"].unique())
    anomaly_sets = {
        filename: set(
            group.loc[group["anomalous"], "channel"].tolist()
        )
        for filename, group in run_log.groupby("filename", sort=False)
    }
    ordered_names = timeline["filename"].tolist()
    channel_rows: list[dict[str, object]] = []
    for channel in channels:
        channel_log = run_log[
            (run_log["channel"] == channel) & run_log["anomalous"]
        ]
        flags = [channel in anomaly_sets[name] for name in ordered_names]
        status_counts = channel_log["strict_status"].value_counts()
        channel_rows.append(
            {
                "channel": channel,
                "n_anomalous_subruns": int(sum(flags)),
                "anomalous_fraction_of_361": sum(flags) / EXPECTED_N,
                "n_ALERT_subruns_anomalous": int(
                    status_counts.get("ALERT", 0)
                ),
                "n_WARN_subruns_anomalous": int(
                    status_counts.get("WARN", 0)
                ),
                "n_OK_subruns_anomalous": int(status_counts.get("OK", 0)),
                "longest_consecutive_anomalous_streak": longest_true_streak(
                    flags
                ),
                "maximum_max_z": float(channel_log["max_z"].max())
                if not channel_log.empty
                else math.nan,
                "median_max_z_when_anomalous": float(
                    channel_log["max_z"].median()
                )
                if not channel_log.empty
                else math.nan,
                "median_if_score_when_anomalous": float(
                    channel_log["if_score"].median()
                )
                if not channel_log.empty
                else math.nan,
            }
        )
    channel_df = pd.DataFrame(channel_rows).sort_values(
        [
            "n_ALERT_subruns_anomalous",
            "n_WARN_subruns_anomalous",
            "n_anomalous_subruns",
            "longest_consecutive_anomalous_streak",
            "maximum_max_z",
            "channel",
        ],
        ascending=[False, False, False, False, False, True],
    )
    channel_df.insert(0, "importance_rank", range(1, len(channel_df) + 1))

    anomalous = run_log[run_log["anomalous"]].copy()
    if anomalous.empty:
        fail("run 2014 has no anomalous channel rows")
    total_alert_anomalous_rows = int(
        anomalous["strict_status"].eq("ALERT").sum()
    )
    cumulative = 0
    dominant_channels: list[object] = []
    for row in channel_df.itertuples(index=False):
        if row.n_ALERT_subruns_anomalous <= 0:
            continue
        dominant_channels.append(row.channel)
        cumulative += int(row.n_ALERT_subruns_anomalous)
        if (
            cumulative >= 0.8 * total_alert_anomalous_rows
            and len(dominant_channels) >= 3
        ):
            break
        if len(dominant_channels) >= 10:
            break
    if not dominant_channels:
        fail("could not select dominant channels")

    # Part 4: method and split triggered-feature summaries.
    anomalous["method"] = anomalous["method"].fillna("").replace("", "<none>")
    method_counts = (
        anomalous.groupby(["method", "strict_status"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=STATUS_ORDER, fill_value=0)
    )
    method_df = method_counts.copy()
    method_df.insert(0, "n_anomalous_rows", method_df.sum(axis=1))
    method_df.insert(
        1,
        "fraction_of_all_anomalous_rows",
        method_df["n_anomalous_rows"] / len(anomalous),
    )
    for status in STATUS_ORDER:
        denominator = int((anomalous["strict_status"] == status).sum())
        method_df[f"fraction_within_{status}_anomalous_rows"] = (
            method_df[status] / denominator if denominator else 0.0
        )
    method_df = method_df.reset_index().sort_values(
        "n_anomalous_rows", ascending=False
    )

    feature_records: list[dict[str, object]] = []
    for row in anomalous[
        ["filename", "channel", "strict_status", "triggered_features"]
    ].itertuples(index=False):
        raw = "" if pd.isna(row.triggered_features) else str(row.triggered_features)
        features = [value.strip() for value in raw.split(";") if value.strip()]
        if not features:
            features = ["<none; IF-only>"]
        for feature in dict.fromkeys(features):
            feature_records.append(
                {
                    "filename": row.filename,
                    "channel": row.channel,
                    "strict_status": row.strict_status,
                    "triggered_feature": feature,
                }
            )
    feature_long = pd.DataFrame(feature_records)
    feature_counts = (
        feature_long.groupby(["triggered_feature", "strict_status"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=STATUS_ORDER, fill_value=0)
    )
    feature_df = feature_counts.copy()
    feature_df.insert(0, "n_anomalous_row_occurrences", feature_df.sum(axis=1))
    feature_df.insert(
        1,
        "fraction_of_all_anomalous_rows",
        feature_df["n_anomalous_row_occurrences"] / len(anomalous),
    )
    for status in STATUS_ORDER:
        denominator = int((anomalous["strict_status"] == status).sum())
        feature_df[f"fraction_within_{status}_anomalous_rows"] = (
            feature_df[status] / denominator if denominator else 0.0
        )
    for channel in dominant_channels:
        ch_records = feature_long[feature_long["channel"] == channel]
        counts = ch_records["triggered_feature"].value_counts()
        denom = int(
            anomalous[
                (anomalous["channel"] == channel)
            ].shape[0]
        )
        feature_df[f"ch{channel}_count"] = feature_df.index.map(
            counts
        ).fillna(0).astype(int)
        feature_df[f"ch{channel}_fraction_of_anomalous_rows"] = (
            feature_df[f"ch{channel}_count"] / denom if denom else 0.0
        )
    feature_df = feature_df.reset_index().sort_values(
        ["ALERT", "WARN", "n_anomalous_row_occurrences"],
        ascending=False,
    )

    # Part 5: dominant channel × feature frequency matrix.
    dominant_feature_long = feature_long[
        feature_long["channel"].isin(dominant_channels)
    ]
    channel_feature = pd.crosstab(
        dominant_feature_long["channel"],
        dominant_feature_long["triggered_feature"],
    ).reindex(dominant_channels, fill_value=0)
    channel_feature.index.name = "channel"
    channel_feature = channel_feature.loc[
        :,
        channel_feature.sum(axis=0).sort_values(ascending=False).index,
    ]

    # Part 6: five unique representative subruns.
    selected_rows: list[dict[str, object]] = []
    selected_names: set[str] = set()
    ok_group = timeline[timeline["strict_status"] == "OK"]
    warn_group = timeline[timeline["strict_status"] == "WARN"]
    alert_group = timeline[timeline["strict_status"] == "ALERT"]
    add_representative(
        selected_rows,
        selected_names,
        representative_row(ok_group, selected_names, "OK"),
        "representative OK (modal anomaly count, near median severity/sequence)",
    )
    add_representative(
        selected_rows,
        selected_names,
        representative_row(warn_group, selected_names, "WARN"),
        "representative WARN (modal anomaly count, near median severity/sequence)",
    )
    first_alert = alert_group.sort_values("sequence_index").iloc[0]
    add_representative(
        selected_rows,
        selected_names,
        first_alert,
        "first strict ALERT in processed-file order",
    )
    largest_bad = alert_group[
        ~alert_group["filename"].isin(selected_names)
    ].sort_values(
        ["n_anomalous_channels", "max_z_over_file", "sequence_index"],
        ascending=[False, False, True],
    ).iloc[0]
    add_representative(
        selected_rows,
        selected_names,
        largest_bad,
        "largest n_anomalous_channels among remaining ALERTs",
    )
    largest_z = alert_group[
        ~alert_group["filename"].isin(selected_names)
    ].sort_values(
        ["max_z_over_file", "n_anomalous_channels", "sequence_index"],
        ascending=[False, False, True],
    ).iloc[0]
    add_representative(
        selected_rows,
        selected_names,
        largest_z,
        "largest max_z_over_file among remaining ALERTs",
    )
    representative_df = pd.DataFrame(selected_rows)
    if len(representative_df) != 5 or representative_df["filename"].duplicated().any():
        fail("representative selection did not produce five unique files")
    if any(parse_run_subrun(name)[0] != RUN for name in representative_df["filename"]):
        fail("representative selection contains another run")

    # Quantitative metrics for synthesis.
    alert_segments = segments_df.query("segment_type == 'ALERT'")
    warn_segments = segments_df.query("segment_type == 'WARN'")
    non_ok_segments = segments_df.query("segment_type == 'NON_OK'")
    isolated_alerts = int((alert_segments["length"] == 1).sum())
    top_alert_channels = (
        channel_df.set_index("channel")["n_ALERT_subruns_anomalous"]
        .sort_values(ascending=False)
    )
    top_warn_channels = (
        channel_df.set_index("channel")["n_WARN_subruns_anomalous"]
        .sort_values(ascending=False)
    )
    top5_alert = [str(value) for value in top_alert_channels.head(5).index]
    top5_warn = [str(value) for value in top_warn_channels.head(5).index]
    top5_overlap = sorted(set(top5_alert) & set(top5_warn))
    channel_status_corr = float(
        channel_df[
            ["n_ALERT_subruns_anomalous", "n_WARN_subruns_anomalous"]
        ].corr(method="spearman").iloc[0, 1]
    )
    metrics = {
        "run": RUN,
        "n_sampled_subruns": EXPECTED_N,
        "status_counts": EXPECTED_STATUS,
        "alert_condition_summary": {
            row["condition"]: {
                "count": int(row["count"]),
                "fraction": float(row["fraction_of_71_alerts"]),
            }
            for row in condition_rows
        },
        "temporal": {
            "n_alert_episodes": int(len(alert_segments)),
            "longest_alert_episode": int(alert_segments["length"].max()),
            "n_isolated_alert_episodes": isolated_alerts,
            "n_warn_episodes": int(len(warn_segments)),
            "longest_warn_episode": int(warn_segments["length"].max()),
            "n_non_ok_episodes": int(len(non_ok_segments)),
            "longest_non_ok_episode": int(non_ok_segments["length"].max()),
            "first_alert_sequence": int(
                alert_group["sequence_index"].min()
            ),
            "last_alert_sequence": int(
                alert_group["sequence_index"].max()
            ),
            "first_alert_subrun": int(
                alert_group.sort_values("sequence_index").iloc[0]["subrun"]
            ),
            "last_alert_subrun": int(
                alert_group.sort_values("sequence_index").iloc[-1]["subrun"]
            ),
        },
        "dominant_channels": [str(value) for value in dominant_channels],
        "top_10_channels": channel_df.head(10).replace(
            {np.nan: None}
        ).to_dict("records"),
        "warn_alert_channel_comparison": {
            "top5_alert_channels": top5_alert,
            "top5_warn_channels": top5_warn,
            "top5_overlap": top5_overlap,
            "spearman_frequency_correlation": (
                None if math.isnan(channel_status_corr) else channel_status_corr
            ),
        },
        "top_15_features": feature_df.head(15).replace(
            {np.nan: None}
        ).to_dict("records"),
        "methods": method_df.replace({np.nan: None}).to_dict("records"),
        "representatives": representative_df.to_dict("records"),
        "provenance": {
            "log": str(LOG),
            "processed_path_cache": str(PATH_CACHE),
            "step1_subrun_classification": str(SUBRUN_CLASSIFICATION),
            "step1_run_classification": str(RUN_CLASSIFICATION),
            "model_directory": str(MODEL_DIR),
            "model_tag": TAG,
        },
    }

    # All checks above passed. Create outputs only now.
    OUT.mkdir(parents=True, exist_ok=True)
    REP_OUT.mkdir(parents=True, exist_ok=True)
    timeline_out.to_csv(
        safe_output(OUT / "run2014_subrun_timeline.csv"), index=False
    )
    condition_df.to_csv(
        safe_output(OUT / "run2014_alert_condition_summary.csv"), index=False
    )
    channel_df.to_csv(
        safe_output(OUT / "run2014_channel_summary.csv"), index=False
    )
    feature_df.to_csv(
        safe_output(OUT / "run2014_feature_summary.csv"), index=False
    )
    method_df.to_csv(
        safe_output(OUT / "run2014_method_summary.csv"), index=False
    )
    channel_feature.to_csv(
        safe_output(OUT / "run2014_channel_feature_matrix.csv")
    )
    representative_df.to_csv(
        safe_output(OUT / "run2014_representative_subruns.csv"), index=False
    )
    segments_df.to_csv(
        safe_output(OUT / "run2014_temporal_segments.csv"), index=False
    )
    (OUT / "run2014_diagnostic_metrics.json").write_text(
        json.dumps(metrics, indent=2, allow_nan=False)
    )

    # Presentation-quality plotting defaults.
    plt.style.use("default")
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.titlesize": 16,
            "axes.labelsize": 13,
            "legend.fontsize": 10,
        }
    )
    x = timeline["sequence_index"].to_numpy()

    plt.figure(figsize=(16, 4.8))
    for status in STATUS_ORDER:
        subset = timeline[timeline["strict_status"] == status]
        y = STATUS_ORDER.index(status)
        plt.scatter(
            subset["sequence_index"].to_numpy(),
            np.full(len(subset), y),
            s=28,
            color=STATUS_COLORS[status],
            label=f"{status} (n={len(subset)})",
            alpha=0.9,
        )
    plt.yticks(range(len(STATUS_ORDER)), STATUS_ORDER)
    plt.xlabel("Processed-file sequence index within run 2014")
    plt.ylabel("Strict status")
    plt.title("Run 2014 strict status timeline")
    plt.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.25))
    savefig(OUT / "run2014_status_timeline.png")

    plt.figure(figsize=(16, 5))
    plt.plot(
        x,
        timeline["n_anomalous_channels"].to_numpy(),
        color="#4c72b0",
        lw=1.2,
    )
    plt.scatter(
        alert_group["sequence_index"].to_numpy(),
        alert_group["n_anomalous_channels"].to_numpy(),
        color=STATUS_COLORS["ALERT"],
        s=18,
        label="strict ALERT",
        zorder=3,
    )
    plt.axhline(5, color="#d62728", ls="--", lw=1.2, label="bulk threshold = 5")
    plt.xlabel("Processed-file sequence index within run 2014")
    plt.ylabel("Anomalous channels")
    plt.title("Run 2014 anomalous-channel count")
    plt.legend()
    savefig(OUT / "run2014_n_anomalous_channels.png")

    plt.figure(figsize=(16, 5))
    plt.plot(
        x,
        timeline["n_persistent_channels"].to_numpy(),
        color="#dd8452",
        lw=1.2,
    )
    plt.scatter(
        alert_group["sequence_index"].to_numpy(),
        alert_group["n_persistent_channels"].to_numpy(),
        color=STATUS_COLORS["ALERT"],
        s=18,
        label="strict ALERT",
        zorder=3,
    )
    plt.axhline(
        2, color="#d62728", ls="--", lw=1.2, label="persistence threshold = 2"
    )
    plt.xlabel("Processed-file sequence index within run 2014")
    plt.ylabel("Persistent channels")
    plt.title("Run 2014 persistent-channel count (5-file window)")
    plt.legend()
    savefig(OUT / "run2014_n_persistent_channels.png")

    plt.figure(figsize=(16, 5))
    positive_z = timeline["max_z_over_file"].clip(lower=0.01).to_numpy()
    plt.plot(x, positive_z, color="#55a868", lw=1.2)
    plt.scatter(
        alert_group["sequence_index"].to_numpy(),
        alert_group["max_z_over_file"].clip(lower=0.01).to_numpy(),
        color=STATUS_COLORS["ALERT"],
        s=18,
        label="strict ALERT",
        zorder=3,
    )
    plt.axhline(15, color="#d62728", ls="--", lw=1.2, label="extreme threshold = 15")
    plt.yscale("log")
    plt.xlabel("Processed-file sequence index within run 2014")
    plt.ylabel("Maximum anomalous-channel |z| (log scale)")
    plt.title("Run 2014 maximum z-score by processed file")
    plt.legend()
    savefig(OUT / "run2014_max_z_over_file.png")

    exclusive_plot = condition_df.query(
        "summary_type == 'exclusive_combination'"
    ).copy()
    plt.figure(figsize=(12, 6))
    y_positions = np.arange(len(exclusive_plot))
    bars = plt.barh(
        y_positions, exclusive_plot["count"].to_numpy(), color="#c44e52"
    )
    plt.yticks(y_positions, exclusive_plot["condition"])
    plt.bar_label(bars, fmt="%d", padding=4)
    plt.xlabel("Strict ALERT subruns")
    plt.ylabel("")
    plt.title("Run 2014 strict ALERT condition decomposition (N=71)")
    savefig(OUT / "run2014_alert_condition_decomposition.png")

    active_channels = channel_df[channel_df["n_anomalous_subruns"] > 0].copy()
    active_channels = active_channels.sort_values("channel")
    plt.figure(figsize=(16, 6))
    plt.bar(
        active_channels["channel"].astype(str).to_numpy(),
        active_channels["n_anomalous_subruns"].to_numpy(),
        color="#4c72b0",
    )
    plt.xticks(rotation=90, fontsize=8)
    plt.xlabel("Channel")
    plt.ylabel("Sampled subruns anomalous")
    plt.title("Run 2014 anomalous frequency by channel")
    savefig(OUT / "run2014_channel_anomalous_frequency.png")

    plt.figure(figsize=(16, 6))
    plt.bar(
        active_channels["channel"].astype(str).to_numpy(),
        active_channels["n_ALERT_subruns_anomalous"].to_numpy(),
        color="#c44e52",
    )
    plt.xticks(rotation=90, fontsize=8)
    plt.xlabel("Channel")
    plt.ylabel("Strict ALERT subruns anomalous")
    plt.title("Run 2014 channel frequency within strict ALERT subruns")
    savefig(OUT / "run2014_channel_alert_frequency.png")

    plt.figure(figsize=(16, 6))
    plt.bar(
        active_channels["channel"].astype(str).to_numpy(),
        active_channels["longest_consecutive_anomalous_streak"].to_numpy(),
        color="#dd8452",
    )
    plt.xticks(rotation=90, fontsize=8)
    plt.xlabel("Channel")
    plt.ylabel("Longest processed-file anomaly streak")
    plt.title("Run 2014 longest consecutive anomalous streak by channel")
    savefig(OUT / "run2014_channel_longest_streak.png")

    top_features = feature_df.head(15).sort_values(
        "n_anomalous_row_occurrences"
    )
    plt.figure(figsize=(12, 7))
    plt.barh(
        top_features["triggered_feature"].to_numpy(),
        top_features["n_anomalous_row_occurrences"].to_numpy(),
        color="#8172b3",
    )
    plt.xlabel("Anomalous channel-row feature occurrences")
    plt.ylabel("")
    plt.title("Run 2014 dominant triggered features")
    savefig(OUT / "run2014_feature_frequency_overall.png")

    status_feature = feature_df.head(15).set_index("triggered_feature")[
        STATUS_ORDER
    ]
    status_feature = status_feature.loc[
        status_feature.sum(axis=1).sort_values().index
    ]
    plt.figure(figsize=(12, 8))
    status_y = np.arange(len(status_feature))
    status_left = np.zeros(len(status_feature), dtype=float)
    for status in STATUS_ORDER:
        values = status_feature[status].to_numpy(dtype=float)
        plt.barh(
            status_y,
            values,
            left=status_left,
            color=STATUS_COLORS[status],
            label=status,
        )
        status_left += values
    plt.yticks(status_y, status_feature.index)
    plt.xlabel("Feature occurrences in anomalous channel rows")
    plt.ylabel("")
    plt.title("Run 2014 triggered features separated by strict status")
    plt.legend(title="Strict status")
    savefig(OUT / "run2014_feature_frequency_by_status.png")

    method_plot = method_df.set_index("method")[STATUS_ORDER]
    method_plot = method_plot.loc[method_plot.sum(axis=1).sort_values().index]
    plt.figure(figsize=(11, 6))
    method_y = np.arange(len(method_plot))
    method_left = np.zeros(len(method_plot), dtype=float)
    for status in STATUS_ORDER:
        values = method_plot[status].to_numpy(dtype=float)
        plt.barh(
            method_y,
            values,
            left=method_left,
            color=STATUS_COLORS[status],
            label=status,
        )
        method_left += values
    plt.yticks(method_y, method_plot.index)
    plt.xlabel("Anomalous channel rows")
    plt.ylabel("")
    plt.title("Run 2014 anomaly-detection method by strict status")
    plt.legend(title="Strict status")
    savefig(OUT / "run2014_method_by_status.png")

    # Show at most the 20 most frequent matrix columns for legibility.
    heatmap_matrix = channel_feature.iloc[:, :20]
    plt.figure(
        figsize=(
            max(10, 0.7 * len(heatmap_matrix.columns)),
            max(4, 0.6 * len(heatmap_matrix.index)),
        )
    )
    matrix_values = heatmap_matrix.to_numpy(dtype=float)
    image = plt.imshow(matrix_values, aspect="auto", cmap="magma")
    plt.colorbar(image, label="Feature-trigger occurrences")
    plt.xticks(
        np.arange(len(heatmap_matrix.columns)),
        heatmap_matrix.columns,
        rotation=45,
        ha="right",
    )
    plt.yticks(
        np.arange(len(heatmap_matrix.index)),
        [f"ch{channel}" for channel in heatmap_matrix.index],
    )
    threshold = matrix_values.max() * 0.55 if matrix_values.size else 0
    for row_index in range(matrix_values.shape[0]):
        for column_index in range(matrix_values.shape[1]):
            value = matrix_values[row_index, column_index]
            plt.text(
                column_index,
                row_index,
                f"{int(value)}",
                ha="center",
                va="center",
                color="black" if value > threshold else "white",
                fontsize=9,
            )
    plt.xlabel("Triggered feature")
    plt.ylabel("Dominant channel")
    plt.title("Run 2014 dominant channel × triggered-feature structure")
    savefig(OUT / "run2014_channel_feature_heatmap.png")

    # Part 7: canonical diagnostic plots for the five selected files.
    detector = _load_models(str(MODEL_DIR))
    for rep in representative_df.itertuples(index=False):
        filepath = path_by_filename[rep.filename]
        if parse_run_subrun(filepath)[0] != RUN:
            fail(f"representative path belongs to another run: {filepath}")
        subdir = safe_output(REP_OUT / Path(rep.filename).stem)
        subdir.mkdir(parents=True, exist_ok=False)
        plot_file(
            filepath,
            detector,
            subdir,
            single_file_alert_n_channels=5,
            single_file_alert_max_z=15.0,
            fmt="png",
        )

    after_stats = {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in production_inputs
    }
    if after_stats != before_stats:
        changed = [
            path
            for path in before_stats
            if before_stats[path] != after_stats[path]
        ]
        fail(f"production input files changed during analysis: {changed}")

    all_created_files = [path for path in OUT.rglob("*") if path.is_file()]
    non_run2014_plot_files = [
        path
        for path in all_created_files
        if path.suffix.lower() in {".png", ".pdf", ".svg"}
        and "run2014" not in path.name
        and not re.search(r"Digitizer_run2014_subrun\d+", str(path))
    ]
    if non_run2014_plot_files:
        fail(f"plots not identifiable as run 2014: {non_run2014_plot_files}")

    print("Run 2014 diagnosis artifacts generated successfully.")
    print(f"Output directory: {OUT}")
    print(f"Status counts: {actual_status}")
    print("Alert condition decomposition:")
    print(condition_df.to_string(index=False))
    print("\nTop channels:")
    print(channel_df.head(12).to_string(index=False))
    print("\nTop features:")
    print(
        feature_df[
            [
                "triggered_feature",
                "n_anomalous_row_occurrences",
                "OK",
                "WARN",
                "ALERT",
            ]
        ].head(15).to_string(index=False)
    )
    print("\nMethods:")
    print(method_df.to_string(index=False))
    print("\nTemporal metrics:")
    print(json.dumps(metrics["temporal"], indent=2))
    print("\nRepresentatives:")
    print(representative_df.to_string(index=False))
    print(f"\nCreated {len(all_created_files)} files.")


if __name__ == "__main__":
    main()
