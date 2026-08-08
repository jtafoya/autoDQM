"""Post-process per-run detector outputs into auditable bad-run incidents.

This module deliberately does not train or apply an anomaly detector.  It reads
the run-specific anomaly logs produced by the existing pipeline, replays the
canonical monitor alert logic, classifies runs, builds deterministic anomaly
signatures, clusters neighboring compatible runs, and writes a range-aware
knowledge-base candidate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

from .plot import _compute_persistence_status


REQUIRED_LOG_COLUMNS = {
    "filename", "channel", "anomalous", "method",
    "triggered_features", "max_z", "if_score",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_scan_config(path: Path) -> dict:
    with path.open() as handle:
        cfg = yaml.safe_load(handle) or {}
    for section in ("campaign", "model", "scan", "alert_replay", "similarity", "knowledge_base"):
        if section not in cfg:
            raise ValueError(f"Missing required configuration section: {section}")
    scan = cfg["scan"]
    if int(scan["min_run"]) > int(scan["max_run"]):
        raise ValueError("scan.min_run must be <= scan.max_run")
    if int(scan["min_subruns_for_primary_bad"]) < 1:
        raise ValueError("min_subruns_for_primary_bad must be positive")
    if int(scan["min_consecutive_alert_subruns"]) < 1:
        raise ValueError("min_consecutive_alert_subruns must be positive")
    weights = cfg["similarity"].get("weights", {})
    required_weights = {"channels", "features", "methods", "scores", "alert_behavior"}
    if set(weights) != required_weights or sum(float(v) for v in weights.values()) <= 0:
        raise ValueError(f"similarity.weights must define exactly {sorted(required_weights)}")
    threshold = float(cfg["similarity"]["threshold"])
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("similarity.threshold must be in [0, 1]")
    return cfg


def campaign_dir(cfg: Mapping[str, Any]) -> Path:
    return Path(cfg["campaign"]["root_dir"]) / str(cfg["campaign"]["tag"])


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text)
    tmp.replace(path)


def _atomic_json(path: Path, payload: Any) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    with tmp.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def _normalise_bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    truthy = {"true", "1", "yes", "y", "t"}
    falsey = {"false", "0", "no", "n", "f", "", "nan", "none"}

    def convert(value: Any) -> bool:
        token = str(value).strip().lower()
        if token in truthy:
            return True
        if token in falsey:
            return False
        raise ValueError(f"Unrecognised boolean value in anomaly log: {value!r}")

    return series.map(convert)


def longest_consecutive_streak(subruns: Iterable[int]) -> int:
    ordered = sorted(set(int(s) for s in subruns))
    longest = current = 0
    previous = None
    for subrun in ordered:
        current = current + 1 if previous is not None and subrun == previous + 1 else 1
        longest = max(longest, current)
        previous = subrun
    return longest


def classify_run(
    run: int,
    valid_subruns: Iterable[int],
    alert_subruns: Iterable[int],
    min_valid_subruns: int,
    min_alert_streak: int,
) -> dict:
    valid = sorted(set(int(s) for s in valid_subruns))
    alerts = sorted(set(int(s) for s in alert_subruns))
    invalid_alerts = sorted(set(alerts) - set(valid))
    if invalid_alerts:
        raise ValueError(f"Run {run}: ALERT subruns are not valid subruns: {invalid_alerts}")
    streak = longest_consecutive_streak(alerts)
    n_valid = len(valid)
    n_alert = len(alerts)
    return {
        "run": int(run),
        "n_valid_subruns": n_valid,
        "n_alert_subruns": n_alert,
        "alert_fraction": (n_alert / n_valid) if n_valid else 0.0,
        "longest_consecutive_alert_streak": streak,
        "first_alert_subrun": alerts[0] if alerts else "",
        "last_alert_subrun": alerts[-1] if alerts else "",
        "primary_bad_run": bool(n_valid >= min_valid_subruns and streak >= min_alert_streak),
        "short_run": bool(0 < n_valid < min_valid_subruns),
        "valid_subruns": valid,
        "alert_subruns": alerts,
    }


def _split_features(value: Any) -> List[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def _numeric_summary(series: pd.Series) -> dict:
    values = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    if values.empty:
        return {"count": 0, "mean": None, "median": None, "p90": None, "max": None}
    return {
        "count": int(len(values)),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "p90": float(values.quantile(0.90)),
        "max": float(values.max()),
    }


def _counter_dict(counter: Counter) -> dict:
    return {str(key): int(value) for key, value in sorted(counter.items(), key=lambda item: str(item[0]))}


def analyse_run_log(
    run: int,
    log_path: Path,
    alert_cfg: Mapping[str, Any],
    scan_cfg: Mapping[str, Any],
) -> Tuple[dict, dict, List[dict]]:
    df = pd.read_csv(log_path)
    missing = REQUIRED_LOG_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Run {run}: anomaly log is missing columns {sorted(missing)}")
    if df.empty:
        raise ValueError(f"Run {run}: completed anomaly log is empty")
    df["anomalous"] = _normalise_bool_series(df["anomalous"])
    if df.duplicated(["filename", "channel"]).any():
        raise ValueError(f"Run {run}: duplicate filename/channel rows in {log_path}")

    status_df = _compute_persistence_status(
        df,
        file_alert_n_channels=int(alert_cfg["file_alert_n_channels"]),
        alert_consecutive_n=int(alert_cfg["alert_consecutive_n"]),
        single_file_alert_n_channels=int(alert_cfg["single_file_alert_n_channels"]),
        single_file_alert_max_z=float(alert_cfg["single_file_alert_max_z"]),
    )
    observed_runs = set(int(v) for v in status_df["run"].dropna().tolist())
    if observed_runs != {int(run)}:
        raise ValueError(f"Run {run}: log contains unexpected runs {sorted(observed_runs)}")

    valid_subruns = [int(v) for v in status_df["subrun"].dropna().tolist()]
    alert_subruns = [
        int(row.subrun) for row in status_df.itertuples()
        if row.status == "alert" and row.subrun is not None
    ]
    summary = classify_run(
        run,
        valid_subruns,
        alert_subruns,
        int(scan_cfg["min_subruns_for_primary_bad"]),
        int(scan_cfg["min_consecutive_alert_subruns"]),
    )

    file_groups = {name: group for name, group in df.groupby("filename")}
    audit_rows: List[dict] = []
    for status in status_df.itertuples():
        group = file_groups[status.filename]
        anomalous = group[group["anomalous"]]
        worst_z = pd.to_numeric(anomalous["max_z"], errors="coerce").max()
        worst_z = 0.0 if pd.isna(worst_z) else float(worst_z)
        alert_persistent = int(status.n_persistent) >= int(alert_cfg["file_alert_n_channels"])
        alert_bulk = (
            int(alert_cfg["single_file_alert_n_channels"]) > 0
            and int(status.n_anomalous) >= int(alert_cfg["single_file_alert_n_channels"])
        )
        alert_extreme = (
            float(alert_cfg["single_file_alert_max_z"]) > 0
            and worst_z >= float(alert_cfg["single_file_alert_max_z"])
        )
        audit_rows.append({
            "run": int(run),
            "subrun": int(status.subrun),
            "filename": status.filename,
            "status": status.status,
            "n_anomalous": int(status.n_anomalous),
            "n_persistent": int(status.n_persistent),
            "n_transient": int(status.n_transient),
            "alert_persistent": bool(alert_persistent),
            "alert_bulk": bool(alert_bulk),
            "alert_extreme": bool(alert_extreme),
            "anomalous_channels": ";".join(str(v) for v in sorted(anomalous["channel"].tolist(), key=str)),
            "source_log": str(log_path),
        })

    anomalous_df = df[df["anomalous"]].copy()
    channel_counts = Counter(str(value) for value in anomalous_df["channel"].tolist())
    feature_counts: Counter = Counter()
    for value in anomalous_df["triggered_features"].tolist():
        feature_counts.update(_split_features(value))
    method_counts = Counter(
        str(value).strip() for value in anomalous_df["method"].dropna().tolist()
        if str(value).strip()
    )
    n_valid = max(1, int(summary["n_valid_subruns"]))
    alert_rows = [row for row in audit_rows if row["status"] == "alert"]
    signature = {
        "run": int(run),
        "n_valid_subruns": int(summary["n_valid_subruns"]),
        "alert_fraction": float(summary["alert_fraction"]),
        "longest_consecutive_alert_streak": int(summary["longest_consecutive_alert_streak"]),
        "anomalous_channel_counts": _counter_dict(channel_counts),
        "anomalous_channel_subrun_frequency": {
            key: value / n_valid for key, value in _counter_dict(channel_counts).items()
        },
        "top_anomalous_channels": [str(key) for key, _ in channel_counts.most_common(10)],
        "triggered_feature_counts": _counter_dict(feature_counts),
        "triggered_feature_frequency": {
            key: value / max(1, sum(feature_counts.values()))
            for key, value in _counter_dict(feature_counts).items()
        },
        "top_triggered_features": [str(key) for key, _ in feature_counts.most_common(10)],
        "detection_method_counts": _counter_dict(method_counts),
        "detection_method_fractions": {
            key: value / max(1, sum(method_counts.values()))
            for key, value in _counter_dict(method_counts).items()
        },
        "max_z_distribution": _numeric_summary(anomalous_df["max_z"]),
        "if_score_distribution": _numeric_summary(anomalous_df["if_score"]),
        "alert_composition": {
            "persistent_fraction": sum(bool(row["alert_persistent"]) for row in alert_rows) / max(1, len(alert_rows)),
            "bulk_fraction": sum(bool(row["alert_bulk"]) for row in alert_rows) / max(1, len(alert_rows)),
            "extreme_fraction": sum(bool(row["alert_extreme"]) for row in alert_rows) / max(1, len(alert_rows)),
        },
    }
    return summary, signature, audit_rows


def _weighted_jaccard(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 1.0
    numerator = sum(min(float(left.get(k, 0.0)), float(right.get(k, 0.0))) for k in keys)
    denominator = sum(max(float(left.get(k, 0.0)), float(right.get(k, 0.0))) for k in keys)
    return numerator / denominator if denominator else 1.0


def _scaled_similarity(left: Any, right: Any, scale: float) -> float:
    if left is None and right is None:
        return 1.0
    if left is None or right is None:
        return 0.0
    return math.exp(-abs(float(left) - float(right)) / max(float(scale), 1e-12))


def signature_similarity(left: Mapping[str, Any], right: Mapping[str, Any], cfg: Mapping[str, Any]) -> dict:
    scales = cfg.get("score_scales", {})
    channels = _weighted_jaccard(
        left.get("anomalous_channel_subrun_frequency", {}),
        right.get("anomalous_channel_subrun_frequency", {}),
    )
    features = _weighted_jaccard(
        left.get("triggered_feature_frequency", {}),
        right.get("triggered_feature_frequency", {}),
    )
    methods = _weighted_jaccard(
        left.get("detection_method_fractions", {}),
        right.get("detection_method_fractions", {}),
    )
    score_parts = []
    for distribution, scale_name in (("max_z_distribution", "max_z"), ("if_score_distribution", "if_score")):
        for statistic_name in ("median", "p90"):
            score_parts.append(_scaled_similarity(
                left.get(distribution, {}).get(statistic_name),
                right.get(distribution, {}).get(statistic_name),
                float(scales.get(scale_name, 1.0)),
            ))
    scores = statistics.mean(score_parts) if score_parts else 0.0
    alert_behavior = statistics.mean([
        max(0.0, 1.0 - abs(float(left.get("alert_fraction", 0.0)) - float(right.get("alert_fraction", 0.0)))),
        _scaled_similarity(
            left.get("longest_consecutive_alert_streak", 0),
            right.get("longest_consecutive_alert_streak", 0),
            float(scales.get("alert_streak", 3.0)),
        ),
    ])
    components = {
        "channels": channels,
        "features": features,
        "methods": methods,
        "scores": scores,
        "alert_behavior": alert_behavior,
    }
    weights = {key: float(value) for key, value in cfg["weights"].items()}
    total_weight = sum(weights.values())
    total = sum(components[key] * weights[key] for key in components) / total_weight
    return {"similarity": float(total), **{f"{key}_similarity": float(value) for key, value in components.items()}}


def build_neighbor_audit(
    run_summaries: Mapping[int, Mapping[str, Any]],
    signatures: Mapping[int, Mapping[str, Any]],
    similarity_cfg: Mapping[str, Any],
) -> List[dict]:
    primary = sorted(run for run, row in run_summaries.items() if row.get("primary_bad_run"))
    threshold = float(similarity_cfg["threshold"])
    rows: List[dict] = []
    for left, right in zip(primary, primary[1:]):
        gap = right - left
        if gap > 2:
            continue
        components = signature_similarity(signatures[left], signatures[right], similarity_cfg)
        relation = "adjacent_primary"
        bridge_run: Any = ""
        eligible = gap == 1
        reason = "adjacent primary bad runs"
        if gap == 2:
            bridge_run = left + 1
            bridge = run_summaries.get(bridge_run, {})
            relation = "short_run_bridge_candidate"
            eligible = bool(bridge.get("short_run") and bridge.get("scan_status") == "too_short")
            reason = (
                "observed short run bracketed by primary bad runs"
                if eligible else f"gap run state is {bridge.get('scan_status', 'incomplete')}, not observed short"
            )
        merge = bool(eligible and components["similarity"] >= threshold)
        if eligible and not merge:
            reason = f"signature similarity below threshold ({components['similarity']:.6f} < {threshold:.6f})"
        rows.append({
            "left_run": left,
            "right_run": right,
            "run_gap": gap,
            "relation": relation,
            "bridge_run": bridge_run,
            **components,
            "threshold": threshold,
            "merge_decision": merge,
            "decision_reason": reason,
        })
    return rows


class _UnionFind:
    def __init__(self, values: Iterable[int]) -> None:
        self.parent = {int(value): int(value) for value in values}

    def find(self, value: int) -> int:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _representative_runs(primary_runs: Sequence[int], start: int, end: int) -> List[int]:
    ordered = sorted(primary_runs)
    if len(ordered) <= 3:
        return ordered
    midpoint = (start + end) / 2.0
    middle = min(ordered[1:-1], key=lambda run: (abs(run - midpoint), run))
    return [ordered[0], middle, ordered[-1]]


def build_incident_ranges(
    run_summaries: Mapping[int, Mapping[str, Any]],
    signatures: Mapping[int, Mapping[str, Any]],
    neighbor_rows: Sequence[Mapping[str, Any]],
    min_range_length_for_bridge: int,
) -> Tuple[List[dict], List[dict]]:
    primary = sorted(run for run, row in run_summaries.items() if row.get("primary_bad_run"))
    union = _UnionFind(primary)
    approved_bridges: Dict[Tuple[int, int], int] = {}
    approved_scores: Dict[Tuple[int, int], float] = {}
    for row in neighbor_rows:
        if not row.get("merge_decision"):
            continue
        left, right = int(row["left_run"]), int(row["right_run"])
        union.union(left, right)
        approved_scores[(left, right)] = float(row["similarity"])
        if row.get("bridge_run") != "":
            approved_bridges[(left, right)] = int(row["bridge_run"])

    groups: Dict[int, List[int]] = {}
    for run in primary:
        groups.setdefault(union.find(run), []).append(run)

    ranges: List[dict] = []
    member_rows: List[dict] = []
    for primary_runs in sorted(groups.values(), key=lambda values: min(values)):
        bridge_runs = sorted(
            bridge for (left, right), bridge in approved_bridges.items()
            if left in primary_runs and right in primary_runs
        )
        members = sorted(set(primary_runs) | set(bridge_runs))
        if bridge_runs and (members[-1] - members[0] + 1) < int(min_range_length_for_bridge):
            bridge_runs = []
            members = sorted(primary_runs)
        start, end = min(members), max(members)
        reps = _representative_runs(primary_runs, start, end)
        alert_fractions = [float(run_summaries[run]["alert_fraction"]) for run in primary_runs]
        internal_scores = [
            score for (left, right), score in approved_scores.items()
            if left in primary_runs and right in primary_runs
        ]
        channel_totals: Counter = Counter()
        feature_totals: Counter = Counter()
        method_totals: Counter = Counter()
        for run in primary_runs:
            channel_totals.update(signatures[run].get("anomalous_channel_counts", {}))
            feature_totals.update(signatures[run].get("triggered_feature_counts", {}))
            method_totals.update(signatures[run].get("detection_method_counts", {}))
        range_row = {
            "run_start": start,
            "run_end": end,
            "n_runs": end - start + 1,
            "primary_bad_runs": ";".join(str(run) for run in primary_runs),
            "short_run_bridge_runs": ";".join(str(run) for run in bridge_runs),
            "representative_runs": ";".join(str(run) for run in reps),
            "mean_alert_fraction": statistics.mean(alert_fractions),
            "median_alert_fraction": statistics.median(alert_fractions),
            "minimum_neighbor_similarity": min(internal_scores) if internal_scores else 1.0,
            "dominant_anomalous_channels": ";".join(str(key) for key, _ in channel_totals.most_common(10)),
            "dominant_triggered_features": ";".join(str(key) for key, _ in feature_totals.most_common(10)),
            "dominant_detection_methods": ";".join(str(key) for key, _ in method_totals.most_common(10)),
        }
        ranges.append(range_row)
        for run in members:
            member_rows.append({
                "run_start": start,
                "run_end": end,
                "run": run,
                "membership_reason": "short_run_bridge" if run in bridge_runs else "primary_bad",
                "n_valid_subruns": run_summaries[run]["n_valid_subruns"],
                "alert_subruns": ";".join(str(v) for v in run_summaries[run]["alert_subruns"]),
            })
    return ranges, member_rows


def _parse_int_list(value: Any) -> List[int]:
    return [int(token) for token in str(value).split(";") if str(token).strip()]


def build_expanded_kb(
    existing_entries: Sequence[Mapping[str, Any]],
    ranges: Sequence[Mapping[str, Any]],
    member_rows: Sequence[Mapping[str, Any]],
    campaign_tag: str,
) -> List[dict]:
    # Replace only entries generated by the same campaign; every human entry and
    # every other campaign remains byte-for-byte equivalent at the data level.
    entries = [
        dict(entry) for entry in existing_entries
        if not (entry.get("source") == "autoDQM_IF_scan" and entry.get("campaign_tag") == campaign_tag)
    ]
    manual_by_run = {
        int(entry["run"]): entry for entry in entries
        if "run" in entry and entry.get("source") != "autoDQM_IF_scan"
    }
    members_by_range: Dict[Tuple[int, int], List[dict]] = {}
    for member in member_rows:
        key = (int(member["run_start"]), int(member["run_end"]))
        members_by_range.setdefault(key, []).append(dict(member))

    auto_entries: List[dict] = []
    for incident in ranges:
        start, end = int(incident["run_start"]), int(incident["run_end"])
        representatives = _parse_int_list(incident["representative_runs"])
        overlapping_manual = sorted(run for run in manual_by_run if start <= run <= end)
        metadata = {
            "source": "autoDQM_IF_scan",
            "campaign_tag": campaign_tag,
            "member_runs": [
                {"run": int(row["run"]), "membership_reason": row["membership_reason"]}
                for row in members_by_range.get((start, end), [])
            ],
            "overlapping_manual_runs": overlapping_manual,
            "mean_alert_fraction": float(incident["mean_alert_fraction"]),
            "median_alert_fraction": float(incident["median_alert_fraction"]),
            "minimum_neighbor_similarity": float(incident["minimum_neighbor_similarity"]),
            "dominant_anomalous_channels": [v for v in str(incident["dominant_anomalous_channels"]).split(";") if v],
            "dominant_triggered_features": [v for v in str(incident["dominant_triggered_features"]).split(";") if v],
            "dominant_detection_methods": [v for v in str(incident["dominant_detection_methods"]).split(";") if v],
        }
        if start == end and start in manual_by_run:
            manual = manual_by_run[start]
            manual.setdefault("run_start", start)
            manual.setdefault("run_end", end)
            manual.setdefault("representative_runs", representatives)
            manual["autoDQM_incident_metadata"] = metadata
            continue
        auto_entries.append({
            "run_start": start,
            "run_end": end,
            "representative_runs": representatives,
            "category": "Undefined",
            "cause": "Undefined",
            "action": "Undefined",
            "recovery": "Undefined",
            **metadata,
        })
    return entries + auto_entries


def _status_record_for_run(run: int, root: Path) -> dict:
    status_path = root / "runs" / f"run{run}" / "status.json"
    if not status_path.exists():
        return {"run": run, "scan_status": "incomplete", "status_path": str(status_path)}
    try:
        payload = json.loads(status_path.read_text())
    except Exception as exc:
        return {"run": run, "scan_status": "failed", "status_path": str(status_path), "error": str(exc)}
    payload["run"] = run
    payload.setdefault("scan_status", "incomplete")
    payload["status_path"] = str(status_path)
    return payload


def postprocess(config_path: Path, allow_incomplete: bool = False) -> dict:
    cfg = load_scan_config(config_path)
    root = campaign_dir(cfg)
    output_dir = root / "postprocess"
    output_dir.mkdir(parents=True, exist_ok=True)
    scan_cfg = cfg["scan"]
    min_run, max_run = int(scan_cfg["min_run"]), int(scan_cfg["max_run"])

    detector_states = {
        run: _status_record_for_run(run, root)
        for run in range(min_run, max_run + 1)
    }
    blocking_states = {
        run: state["scan_status"] for run, state in detector_states.items()
        if state["scan_status"] not in {"completed", "no_data"}
    }
    if blocking_states and not allow_incomplete:
        counts = Counter(blocking_states.values())
        raise RuntimeError(
            "Campaign is not complete; refusing to generate a partial KB candidate. "
            f"Blocking states: {dict(sorted(counts.items()))}. Run campaign.py status, "
            "finish/retry the detector jobs, or use --allow-incomplete only for a smoke test."
        )

    summaries: Dict[int, dict] = {}
    signatures: Dict[int, dict] = {}
    subrun_audit: List[dict] = []
    for run in range(min_run, max_run + 1):
        status = detector_states[run]
        detector_status = status["scan_status"]
        if detector_status == "completed":
            log_path = Path(status.get("anomaly_log", root / "runs" / f"run{run}" / "anomaly_log.csv"))
            try:
                summary, signature, audit = analyse_run_log(run, log_path, cfg["alert_replay"], scan_cfg)
                summary["detector_status"] = detector_status
                summary["scan_status"] = "too_short" if summary["short_run"] else "completed"
                summary["source_log"] = str(log_path)
                summaries[run] = summary
                signatures[run] = signature
                subrun_audit.extend(audit)
            except Exception as exc:
                summaries[run] = {
                    **classify_run(run, [], [], int(scan_cfg["min_subruns_for_primary_bad"]), int(scan_cfg["min_consecutive_alert_subruns"])),
                    "detector_status": detector_status,
                    "scan_status": "failed",
                    "source_log": str(log_path),
                    "error": str(exc),
                }
        else:
            summaries[run] = {
                **classify_run(run, [], [], int(scan_cfg["min_subruns_for_primary_bad"]), int(scan_cfg["min_consecutive_alert_subruns"])),
                "detector_status": detector_status,
                "scan_status": detector_status,
                "source_log": status.get("anomaly_log", ""),
                "error": status.get("error", ""),
            }

    analysis_blocking = {
        run: row["scan_status"] for run, row in summaries.items()
        if row["scan_status"] in {"failed", "incomplete"}
    }
    if analysis_blocking and not allow_incomplete:
        counts = Counter(analysis_blocking.values())
        raise RuntimeError(
            "Detector output validation/post-processing is incomplete; refusing to generate a KB candidate. "
            f"Blocking states: {dict(sorted(counts.items()))}."
        )

    neighbor_rows = build_neighbor_audit(summaries, signatures, cfg["similarity"])
    ranges, member_rows = build_incident_ranges(
        summaries,
        signatures,
        neighbor_rows,
        int(scan_cfg["minimum_range_length_for_short_bridge"]),
    )

    summary_fields = [
        "run", "n_valid_subruns", "n_alert_subruns", "alert_fraction",
        "longest_consecutive_alert_streak", "first_alert_subrun", "last_alert_subrun",
        "primary_bad_run", "short_run", "scan_status", "detector_status",
        "valid_subruns", "alert_subruns", "source_log", "error",
    ]
    csv_summaries = []
    for row in summaries.values():
        serialised = dict(row)
        serialised["valid_subruns"] = ";".join(str(v) for v in row.get("valid_subruns", []))
        serialised["alert_subruns"] = ";".join(str(v) for v in row.get("alert_subruns", []))
        csv_summaries.append(serialised)
    _write_csv(output_dir / "run_scan_summary.csv", csv_summaries, summary_fields)
    _write_csv(
        output_dir / "primary_bad_runs.csv",
        [row for row in csv_summaries if row["primary_bad_run"]],
        summary_fields,
    )
    _atomic_json(output_dir / "run_anomaly_signatures.json", {str(k): v for k, v in sorted(signatures.items())})
    _write_csv(output_dir / "subrun_alert_audit.csv", subrun_audit, [
        "run", "subrun", "filename", "status", "n_anomalous", "n_persistent", "n_transient",
        "alert_persistent", "alert_bulk", "alert_extreme", "anomalous_channels", "source_log",
    ])
    neighbor_fields = [
        "left_run", "right_run", "run_gap", "relation", "bridge_run", "similarity",
        "channels_similarity", "features_similarity", "methods_similarity", "scores_similarity",
        "alert_behavior_similarity", "threshold", "merge_decision", "decision_reason",
    ]
    _write_csv(output_dir / "neighboring_run_similarity.csv", neighbor_rows, neighbor_fields)
    range_fields = [
        "run_start", "run_end", "n_runs", "primary_bad_runs", "short_run_bridge_runs",
        "representative_runs", "mean_alert_fraction", "median_alert_fraction",
        "minimum_neighbor_similarity", "dominant_anomalous_channels",
        "dominant_triggered_features", "dominant_detection_methods",
    ]
    _write_csv(output_dir / "bad_run_ranges.csv", ranges, range_fields)
    _write_csv(output_dir / "bad_run_range_members.csv", member_rows, [
        "run_start", "run_end", "run", "membership_reason", "n_valid_subruns", "alert_subruns",
    ])

    kb_input = Path(cfg["knowledge_base"]["input_path"])
    kb_backup = output_dir / "llm_knowledge_base.source_backup.yaml"
    kb_backup_tmp = kb_backup.with_name(f".{kb_backup.name}.tmp")
    shutil.copy2(kb_input, kb_backup_tmp)
    kb_backup_tmp.replace(kb_backup)
    existing = yaml.safe_load(kb_input.read_text()) or []
    if not isinstance(existing, list):
        raise ValueError(f"Knowledge base must contain a YAML list: {kb_input}")
    expanded = build_expanded_kb(existing, ranges, member_rows, str(cfg["campaign"]["tag"]))
    kb_output = output_dir / str(cfg["knowledge_base"].get("output_filename", "llm_knowledge_base_expanded.yaml"))
    kb_text = (
        "# Range-aware candidate generated by autoDQM_IF_scan.\n"
        "# The source knowledge base is unchanged; see llm_knowledge_base.source_backup.yaml.\n\n"
        + yaml.safe_dump(expanded, sort_keys=False, allow_unicode=True, width=120)
    )
    _atomic_text(kb_output, kb_text)

    counts = Counter(row["scan_status"] for row in summaries.values())
    n_bridges = sum(1 for row in member_rows if row["membership_reason"] == "short_run_bridge")
    isolated = sum(1 for row in ranges if int(row["run_start"]) == int(row["run_end"]))
    range_labels = [
        str(row["run_start"]) if int(row["run_start"]) == int(row["run_end"])
        else f"{row['run_start']}-{row['run_end']}"
        for row in ranges
    ]
    lines = [
        "AutoDQM bad-run scan summary",
        f"Generated: {utc_now()}",
        f"Campaign: {cfg['campaign']['tag']}",
        f"Requested runs: {max_run - min_run + 1} ({min_run}-{max_run})",
        f"Runs with usable detector output: {counts['completed'] + counts['too_short']}",
        f"No-data runs: {counts['no_data']}",
        f"Failed runs: {counts['failed']}",
        f"Incomplete runs: {counts['incomplete']}",
        f"Short observed runs: {counts['too_short']}",
        f"Primary bad runs: {sum(bool(row['primary_bad_run']) for row in summaries.values())}",
        f"Short-run bridges absorbed: {n_bridges}",
        f"Final incident ranges: {len(ranges)}",
        f"Isolated bad-run entries: {isolated}",
        "Ranges: " + (", ".join(range_labels) if range_labels else "none"),
        f"Expanded KB candidate: {kb_output}",
    ]
    _atomic_text(output_dir / "bad_run_scan_summary.txt", "\n".join(lines) + "\n")
    provenance = {
        "generated_at": utc_now(),
        "command": " ".join(sys.argv),
        "config_path": str(config_path.resolve()),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "configuration": cfg,
        "campaign_metadata": json.loads((root / "campaign_metadata.json").read_text())
        if (root / "campaign_metadata.json").exists() else None,
    }
    _atomic_json(output_dir / "postprocess_metadata.json", provenance)
    return {"output_dir": str(output_dir), "counts": dict(counts), "ranges": len(ranges)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="TASK 1 scan configuration YAML")
    parser.add_argument(
        "--allow-incomplete", action="store_true",
        help="Generate partial outputs despite failed/incomplete detector jobs (smoke tests only)",
    )
    args = parser.parse_args()
    result = postprocess(args.config, allow_incomplete=args.allow_incomplete)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
