#!/usr/bin/env python3
"""Build authoritative subrun/run classifications for the Juan reproduction.

The strict status is imported from src.plot._compute_persistence_status, the
same canonical helper used by src.evaluate.step_evaluate.  The local replay
below mirrors that helper only to expose the per-file persistent channel set
and the three independent alert-condition flags requested by this analysis.
"""

from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

import pandas as pd
import yaml


REPO = Path("/afs/cern.ch/user/p/pengy/autoDQM")
IF_DIR = REPO / "isolation_forest"
TAG = (
    "juan_reproduction_digi_z8_if0001_train20_seed42"
    "_noTrigger_noLVDS_ignoreTriggerConfig"
)
LOG = IF_DIR / "logs" / f"{TAG}.csv"
PROCESSED_PATH_CACHE = IF_DIR / "logs" / f"{TAG}_paths.txt"
FROZEN_SELECTION_TSV = (
    IF_DIR / "condor" / "apply_good_training_sampled_paths_seed42_frac40.tsv"
)
MODEL_DIR = IF_DIR / "models" / TAG
CONFIG = MODEL_DIR / "config.yaml"
TRAINING_METADATA = MODEL_DIR / "training_metadata.json"
EVAL_COUNTS = IF_DIR / "reports" / TAG / "eval_confusion_data.json"
EVAL_SUMMARY = IF_DIR / "reports" / TAG / "eval_summary.txt"
RUN_OUTPUT_DIR = IF_DIR / "logs" / TAG
OUT_DIR = (
    IF_DIR
    / "analysis"
    / "juan_bad_run_diagnosis"
    / "step1_classification"
)

SPECIFIC_RUNS = [1601, 1710, 1711, 2013, 2014, 2085, 2086, 2087, 2088, 2089]
REQUIRED_COLUMNS = {
    "timestamp",
    "filename",
    "channel",
    "anomalous",
    "method",
    "triggered_features",
    "max_z",
    "if_score",
}


def fail(message: str) -> "None":
    raise RuntimeError(f"SANITY CHECK FAILED: {message}")


def channel_key(value: object) -> tuple[int, object]:
    try:
        return (0, int(value))
    except (TypeError, ValueError):
        return (1, str(value))


def join_channels(values: set[object]) -> str:
    return ";".join(str(value) for value in sorted(values, key=channel_key))


def markdown_table(df: pd.DataFrame) -> str:
    headers = [str(column) for column in df.columns]
    rows = [[str(value) for value in row] for row in df.itertuples(index=False, name=None)]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def main() -> None:
    sys.path.insert(0, str(IF_DIR))
    from src.plot import _compute_persistence_status
    from src.run_list import parse_run_subrun, run_subrun_sort_key

    required_files = [
        LOG,
        PROCESSED_PATH_CACHE,
        FROZEN_SELECTION_TSV,
        CONFIG,
        TRAINING_METADATA,
        EVAL_COUNTS,
        EVAL_SUMMARY,
    ]
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        fail(f"required input files are missing: {missing}")

    config = yaml.safe_load(CONFIG.read_text())
    metadata = json.loads(TRAINING_METADATA.read_text())
    thresholds = {
        "file_alert_n_channels": int(config["file_alert_n_channels"]),
        "alert_consecutive_n": int(config["alert_consecutive_n"]),
        "single_file_alert_n_channels": int(
            config["single_file_alert_n_channels"]
        ),
        "single_file_alert_max_z": float(config["single_file_alert_max_z"]),
    }
    expected_thresholds = {
        "file_alert_n_channels": 2,
        "alert_consecutive_n": 5,
        "single_file_alert_n_channels": 5,
        "single_file_alert_max_z": 15.0,
    }
    if thresholds != expected_thresholds:
        fail(f"thresholds {thresholds} != required {expected_thresholds}")

    effective = metadata["effective_config"]
    feature_provenance = {
        "use_trigger": effective.get("use_trigger"),
        "use_lvds": effective.get("use_lvds"),
        "include_trigger_config": effective.get("include_trigger_config"),
        "include_daq_config": effective.get("include_daq_config"),
    }
    expected_features = {
        "use_trigger": False,
        "use_lvds": False,
        "include_trigger_config": False,
        "include_daq_config": True,
    }
    if feature_provenance != expected_features:
        fail(
            f"effective feature provenance {feature_provenance} "
            f"!= expected {expected_features}"
        )

    df = pd.read_csv(LOG)
    missing_columns = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing_columns:
        fail(f"combined log lacks columns: {missing_columns}")
    if df.empty:
        fail("combined log is empty")

    if df["anomalous"].dtype != bool:
        normalized = df["anomalous"].astype(str).str.strip().str.lower()
        if not normalized.isin(["true", "false"]).all():
            fail("anomalous column contains values other than True/False")
        df["anomalous"] = normalized.eq("true")

    if df.duplicated(["filename", "channel"]).any():
        examples = (
            df.loc[df.duplicated(["filename", "channel"], keep=False),
                   ["filename", "channel"]]
            .head()
            .to_dict("records")
        )
        fail(f"duplicate filename/channel rows found: {examples}")

    processed_paths = PROCESSED_PATH_CACHE.read_text().splitlines()
    if not processed_paths or any(not path.strip() for path in processed_paths):
        fail("processed path cache is empty or contains blank lines")
    if len(processed_paths) != len(set(processed_paths)):
        fail("processed path cache contains duplicates")

    processed_names = [Path(path).name for path in processed_paths]
    if len(processed_names) != len(set(processed_names)):
        fail("processed path cache contains duplicate basenames")

    log_first_seen_names = df["filename"].drop_duplicates().tolist()
    if log_first_seen_names != processed_names:
        fail(
            "combined log first-seen filename order does not exactly match "
            "the successful combined processed path cache"
        )
    if set(df["filename"]) != set(processed_names):
        fail("combined log filenames do not match processed path cache")

    parsed_cache: list[tuple[int, int]] = []
    for path, name in zip(processed_paths, processed_names):
        path_pair = parse_run_subrun(path)
        name_pair = parse_run_subrun(name)
        if path_pair != name_pair or None in path_pair:
            fail(f"run/subrun parsing mismatch for {path}")
        parsed_cache.append((int(path_pair[0]), int(path_pair[1])))
    if len(parsed_cache) != len(set(parsed_cache)):
        fail("duplicate run/subrun pairs exist in processed path cache")

    # The frozen successful sequence is already run/subrun sorted.  Numerical
    # gaps are intentionally ignored: adjacent cache entries are consecutive
    # processed files for persistence purposes.
    canonical_sorted_names = sorted(processed_names, key=run_subrun_sort_key)
    if processed_names != canonical_sorted_names:
        fail("processed path cache order differs from canonical run/subrun order")

    frozen_rows: list[tuple[int, str]] = []
    for line_number, line in enumerate(
        FROZEN_SELECTION_TSV.read_text().splitlines(), start=1
    ):
        fields = line.split("\t", 1)
        if len(fields) != 2:
            fail(f"malformed frozen TSV line {line_number}")
        frozen_rows.append((int(fields[0]), fields[1]))
    if len(frozen_rows) != len({path for _, path in frozen_rows}):
        fail("original frozen selection TSV contains duplicate paths")

    successful_path_set = set(processed_paths)
    selected_path_set = {path for _, path in frozen_rows}
    unexpected_processed = successful_path_set - selected_path_set
    if unexpected_processed:
        fail(
            f"{len(unexpected_processed)} processed paths are absent from "
            "the frozen selection TSV"
        )
    omitted_selection = selected_path_set - successful_path_set
    omitted_runs = sorted(
        {run for run, path in frozen_rows if path in omitted_selection}
    )
    if omitted_runs != [1635] or len(omitted_selection) != 188:
        fail(
            "frozen-selection vs successful-output difference was not the "
            f"known failed run1635/188-file case: runs={omitted_runs}, "
            f"paths={len(omitted_selection)}"
        )

    # Every successfully published per-run cache must exactly match its slice
    # of the original frozen selection.  This proves the actual apply order.
    run_cache_files = sorted(RUN_OUTPUT_DIR.glob(f"{TAG}_run*_paths.txt"))
    if len(run_cache_files) != 96:
        fail(f"expected 96 successful per-run caches, found {len(run_cache_files)}")
    concatenated_run_paths: list[str] = []
    for cache_file in run_cache_files:
        stem_tail = cache_file.name.split("_run")[-1].split("_paths.txt")[0]
        run = int(stem_tail)
        actual = cache_file.read_text().splitlines()
        expected = [path for row_run, path in frozen_rows if row_run == run]
        if actual != expected:
            fail(f"per-run path cache order differs from frozen TSV for run {run}")
        concatenated_run_paths.extend(actual)
    if concatenated_run_paths != processed_paths:
        fail("combined processed path cache differs from concatenated per-run caches")

    canonical = _compute_persistence_status(
        df,
        file_alert_n_channels=thresholds["file_alert_n_channels"],
        alert_consecutive_n=thresholds["alert_consecutive_n"],
        single_file_alert_n_channels=thresholds[
            "single_file_alert_n_channels"
        ],
        single_file_alert_max_z=thresholds["single_file_alert_max_z"],
    ).set_index("filename")
    if canonical.index.tolist() != processed_names:
        fail("canonical replay order differs from processed path cache")

    grouped = {name: group for name, group in df.groupby("filename", sort=False)}
    run_counts = pd.Series([run for run, _ in parsed_cache]).value_counts().to_dict()
    history: dict[object, deque[bool]] = {}
    current_run: int | None = None
    reset_count = 0
    sequence_index = 0
    rows: list[dict[str, object]] = []

    for filename, (run, subrun) in zip(processed_names, parsed_cache):
        if run != current_run:
            current_run = run
            history = {}
            sequence_index = 0
            reset_count += 1

        group = grouped[filename]
        all_channels = set(group["channel"])
        anomalous_group = group[group["anomalous"]]
        anomalous_channels = set(anomalous_group["channel"])
        persistent_channels: set[object] = set()

        for channel in anomalous_channels:
            channel_history = history.get(channel, deque())
            if (
                len(channel_history)
                >= thresholds["alert_consecutive_n"] - 1
                and all(channel_history)
            ):
                persistent_channels.add(channel)

        if sequence_index < thresholds["alert_consecutive_n"] - 1:
            if persistent_channels:
                fail(
                    f"persistence did not reset at run {run} boundary "
                    f"(sequence index {sequence_index})"
                )

        for channel in all_channels:
            if channel not in history:
                history[channel] = deque(
                    maxlen=thresholds["alert_consecutive_n"] - 1
                )
            history[channel].append(channel in anomalous_channels)

        n_bad = len(anomalous_channels)
        n_persistent = len(persistent_channels)
        valid_anomalous_z = pd.to_numeric(
            anomalous_group["max_z"], errors="coerce"
        ).dropna()
        max_z = (
            float(valid_anomalous_z.max())
            if not valid_anomalous_z.empty
            else 0.0
        )
        persistent_alert = (
            n_persistent >= thresholds["file_alert_n_channels"]
        )
        bulk_alert = (
            n_bad >= thresholds["single_file_alert_n_channels"]
        )
        extreme_alert = (
            max_z >= thresholds["single_file_alert_max_z"]
        )
        n_transient = n_bad - n_persistent
        run_too_short = run_counts[run] < thresholds["alert_consecutive_n"]
        if persistent_alert or bulk_alert or extreme_alert:
            local_status = "alert"
        elif n_persistent > 0:
            local_status = "warn"
        elif n_transient > 0 and run_too_short:
            local_status = "pend"
        else:
            local_status = "ok"

        canonical_row = canonical.loc[filename]
        if (
            local_status != canonical_row["status"]
            or n_bad != int(canonical_row["n_anomalous"])
            or n_persistent != int(canonical_row["n_persistent"])
        ):
            fail(
                f"local detail replay disagrees with canonical helper for "
                f"{filename}: local={local_status}/{n_bad}/{n_persistent}, "
                f"canonical={canonical_row['status']}/"
                f"{canonical_row['n_anomalous']}/"
                f"{canonical_row['n_persistent']}"
            )

        rows.append(
            {
                "run": run,
                "subrun": subrun,
                "filename": filename,
                "sequence_index_within_run": sequence_index,
                "n_channels": len(all_channels),
                "n_anomalous_channels": n_bad,
                "anomalous_channels": join_channels(anomalous_channels),
                "raw_bad": n_bad >= thresholds["file_alert_n_channels"],
                "n_persistent_channels": n_persistent,
                "persistent_channels": join_channels(persistent_channels),
                "persistent_alert": persistent_alert,
                "bulk_alert": bulk_alert,
                "extreme_alert": extreme_alert,
                "max_z_over_file": max_z,
                "strict_status": local_status.upper(),
            }
        )
        sequence_index += 1

    subrun_df = pd.DataFrame(rows)
    if len(subrun_df) != len(processed_paths):
        fail("each successfully sampled file did not produce exactly one row")
    if subrun_df["filename"].duplicated().any():
        fail("duplicate filename exists in subrun table")
    if subrun_df.duplicated(["run", "subrun"]).any():
        fail("duplicate run/subrun exists in subrun table")
    if reset_count != subrun_df["run"].nunique():
        fail("persistence reset count differs from number of runs")

    status_totals = (
        subrun_df["strict_status"]
        .value_counts()
        .reindex(["OK", "WARN", "PEND", "ALERT"], fill_value=0)
        .astype(int)
    )
    existing_counts_lower = json.loads(EVAL_COUNTS.read_text())["counts"][
        "known_good"
    ]
    existing_totals = pd.Series(
        {
            "OK": int(existing_counts_lower.get("ok", 0)),
            "WARN": int(existing_counts_lower.get("warn", 0)),
            "PEND": int(existing_counts_lower.get("pend", 0)),
            "ALERT": int(existing_counts_lower.get("alert", 0)),
        }
    )
    if not status_totals.equals(existing_totals):
        fail(
            f"strict totals {status_totals.to_dict()} disagree with existing "
            f"evaluation {existing_totals.to_dict()}"
        )

    run_rows: list[dict[str, object]] = []
    for run, group in subrun_df.groupby("run", sort=True):
        counts = (
            group["strict_status"]
            .value_counts()
            .reindex(["OK", "WARN", "PEND", "ALERT"], fill_value=0)
        )
        n = len(group)
        n_raw_bad = int(group["raw_bad"].sum())
        n_alert = int(counts["ALERT"])
        run_rows.append(
            {
                "run": int(run),
                "n_sampled_subruns": n,
                "n_raw_bad": n_raw_bad,
                "raw_bad_fraction": n_raw_bad / n,
                "n_OK": int(counts["OK"]),
                "n_WARN": int(counts["WARN"]),
                "n_PEND": int(counts["PEND"]),
                "n_ALERT": n_alert,
                "strict_alert_fraction": n_alert / n,
                "all_raw_bad": n_raw_bad == n,
                "all_strict_ALERT": n_alert == n,
            }
        )
    run_df = pd.DataFrame(run_rows)

    specific = run_df[run_df["run"].isin(SPECIFIC_RUNS)].copy()
    missing_specific = sorted(set(SPECIFIC_RUNS) - set(specific["run"]))
    if missing_specific:
        fail(f"requested comparison runs are absent: {missing_specific}")
    specific["_order"] = specific["run"].map(
        {run: index for index, run in enumerate(SPECIFIC_RUNS)}
    )
    specific = specific.sort_values("_order").drop(columns="_order")
    display = specific[
        [
            "run",
            "n_sampled_subruns",
            "raw_bad_fraction",
            "strict_alert_fraction",
            "n_OK",
            "n_WARN",
            "n_PEND",
            "n_ALERT",
            "all_raw_bad",
            "all_strict_ALERT",
        ]
    ].copy()
    display["raw_bad_fraction"] = display["raw_bad_fraction"].map(
        lambda value: f"{value:.6f}"
    )
    display["strict_alert_fraction"] = display["strict_alert_fraction"].map(
        lambda value: f"{value:.6f}"
    )

    all_raw_bad = run_df.loc[run_df["all_raw_bad"], "run"].astype(int).tolist()
    all_strict_alert = (
        run_df.loc[run_df["all_strict_ALERT"], "run"].astype(int).tolist()
    )

    summary = f"""# Step 1 — authoritative subrun/run classification

## A. Exact artifacts used

- Authoritative combined channel-level log: `{LOG}`
- Authoritative successful processed sequence: `{PROCESSED_PATH_CACHE}`
- Original frozen selection TSV: `{FROZEN_SELECTION_TSV}`
- Successful per-run apply outputs/path caches: `{RUN_OUTPUT_DIR}/`
- Exact model directory/tag: `{MODEL_DIR}`
- Model config snapshot: `{CONFIG}`
- Effective training provenance: `{TRAINING_METADATA}`
- Existing evaluation counts: `{EVAL_COUNTS}`
- Existing evaluation summary: `{EVAL_SUMMARY}`

The strict status comes directly from `src.plot._compute_persistence_status`,
which is the canonical helper imported by `src.evaluate.step_evaluate`.
The detail replay in `build_classification.py` mirrors that helper and
`src.monitor.process_file` to expose channel sets and individual alert flags;
every row was required to agree with the canonical helper.

## B. Number of sampled subruns analyzed

Analyzed **{len(subrun_df)}** successfully processed sampled subruns across
**{subrun_df["run"].nunique()}** runs.

The original frozen TSV contains {len(frozen_rows)} paths across
{len({run for run, _ in frozen_rows})} runs. Run 1635 (188 selected paths) did
not publish a successful per-run output because sampled subrun 470 had no
events; the validation job rejected 187 logged filenames versus 188 expected.
Therefore the successful reproduction's combined log/cache contains 13,432
paths and excludes run 1635. No successfully processed path is absent from the
original TSV, and each of the other 96 per-run caches matches its TSV slice
exactly and in order.

## C. Strict replay versus previous evaluation

Yes. The strict replay totals exactly reproduce the existing evaluation:
**OK={status_totals["OK"]}, WARN={status_totals["WARN"]},
PEND={status_totals["PEND"]}, ALERT={status_totals["ALERT"]}**.

Thresholds were verified exactly: 2 persistent channels, 5 processed files,
5 bulk channels, and anomalous-channel max_z >= 15.

## D. Runs that are all_raw_bad

`{all_raw_bad}`

## E. Runs that are all_strict_ALERT

`{all_strict_alert}`

## F. Requested run comparison

{markdown_table(display)}

## G. Is report.py “bad run” equivalent to strict ALERT?

**No.** `report.py` labels a subrun raw bad whenever it has at least 2
anomalous channels in that file. Strict ALERT instead requires at least one of:
2 channels persistent across 5 processed files, at least 5 anomalous channels
in one file, or anomalous-channel max_z >= 15. The unequal per-subrun
fractions above provide direct evidence that the labels are not interchangeable
(for example, run 2014 is 0.667590 raw bad versus 0.196676 strict ALERT, while
run 2086 is 0.043478 raw bad versus 0 strict ALERT). The all-run lists happen
to coincide for this sample, but that does not make the subrun definitions
equivalent.

## Sanity checks

- Required channel-log columns present: yes.
- One subrun row per successful processed path: yes ({len(subrun_df)}).
- Duplicate filename/channel log rows: none.
- Duplicate filenames in subrun table: none.
- Duplicate run/subrun pairs: none.
- Combined log order equals successful combined path cache: yes.
- Each successful per-run path cache equals its frozen TSV slice: yes.
- Combined cache equals concatenated successful per-run caches: yes.
- Persistence state reset at all {reset_count} run boundaries: yes.
- Detail replay agrees row-by-row with canonical helper: yes.
- Strict totals agree with existing evaluation output: yes.
"""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    output_paths = [
        OUT_DIR / "subrun_classification.csv",
        OUT_DIR / "run_classification.csv",
        OUT_DIR / "step1_summary.md",
    ]
    existing_outputs = [str(path) for path in output_paths if path.exists()]
    if existing_outputs:
        fail(f"refusing to overwrite existing analysis outputs: {existing_outputs}")
    subrun_df.to_csv(OUT_DIR / "subrun_classification.csv", index=False)
    run_df.to_csv(OUT_DIR / "run_classification.csv", index=False)
    (OUT_DIR / "step1_summary.md").write_text(summary)

    print("Authoritative Juan Step 1 classification complete.")
    print(f"Log: {LOG}")
    print(f"Processed sequence: {PROCESSED_PATH_CACHE}")
    print(f"Original frozen selection: {FROZEN_SELECTION_TSV}")
    print(f"Subruns: {len(subrun_df)}")
    print("Status totals:", status_totals.to_dict())
    print()
    print(display.to_string(index=False))
    print()
    print(f"all_raw_bad: {all_raw_bad}")
    print(f"all_strict_ALERT: {all_strict_alert}")
    print(f"Outputs: {OUT_DIR}")


if __name__ == "__main__":
    main()
