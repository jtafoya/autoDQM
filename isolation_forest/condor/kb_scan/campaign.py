#!/usr/bin/env python3
"""Prepare and execute provenance-checked per-run Isolation Forest scans."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

ISOLATION_FOREST_DIR = Path(__file__).resolve().parents[2]
if str(ISOLATION_FOREST_DIR) not in sys.path:
    sys.path.insert(0, str(ISOLATION_FOREST_DIR))

from src.detector import AnomalyDetector  # noqa: E402
from src.reference import ReferenceModel  # noqa: E402
from src.run_list import parse_run_subrun, resolve_run_files, run_subrun_sort_key  # noqa: E402


APPLICATION_CODE_PATHS = [
    "isolation_forest/src/pipeline.py",
    "isolation_forest/src/args.py",
    "isolation_forest/src/monitor.py",
    "isolation_forest/src/features.py",
    "isolation_forest/src/reference.py",
    "isolation_forest/src/detector.py",
    "isolation_forest/src/run_list.py",
]

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_scan_config(path: Path) -> dict:
    with path.open() as handle:
        cfg = yaml.safe_load(handle)
    if not isinstance(cfg, dict):
        raise ValueError(f"Scan configuration must be a mapping: {path}")
    for section in ("campaign", "model", "scan", "alert_replay"):
        if section not in cfg:
            raise ValueError(f"Missing configuration section: {section}")
    min_run = int(cfg["scan"]["min_run"])
    max_run = int(cfg["scan"]["max_run"])
    if min_run > max_run:
        raise ValueError("scan.min_run must not exceed scan.max_run")
    return cfg


def campaign_dir(cfg: Mapping[str, Any]) -> Path:
    return Path(cfg["campaign"]["root_dir"]) / str(cfg["campaign"]["tag"])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_text(text)
    os.replace(tmp, path)


def atomic_json(path: Path, payload: Any) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _npz_bool(npz: Mapping[str, Any], key: str) -> bool:
    values = np.asarray(npz[key]).reshape(-1)
    if len(values) != 1:
        raise ValueError(f"reference.npz field {key} is not scalar")
    return bool(values[0])


def resolved_tag(base_tag: str, flags: Mapping[str, bool]) -> str:
    tag = str(base_tag)
    if not flags["use_trigger"]:
        tag += "_noTrigger"
    if not flags["use_lvds"]:
        tag += "_noLVDS"
    if not flags["include_trigger_config"]:
        tag += "_ignoreTriggerConfig"
    if not flags["include_daq_config"]:
        tag += "_ignoreDAQConfig"
    return tag


def validate_model(cfg: Mapping[str, Any]) -> dict:
    model_cfg = cfg["model"]
    model_dir = Path(model_cfg["directory"])
    reference_path = model_dir / "reference.npz"
    detector_path = model_dir / "detector.pkl"
    metadata_path = model_dir / "training_metadata.json"
    snapshot_path = Path(model_cfg["config_snapshot"])
    for path in (model_dir, reference_path, detector_path, metadata_path, snapshot_path):
        if not path.exists():
            raise FileNotFoundError(f"Required trained-model artifact is missing: {path}")

    metadata = json.loads(metadata_path.read_text())
    expected_flags = {key: bool(value) for key, value in model_cfg["feature_flags"].items()}
    with np.load(reference_path, allow_pickle=True) as reference_npz:
        actual_flags = {
            "use_trigger": _npz_bool(reference_npz, "use_trigger"),
            "use_lvds": _npz_bool(reference_npz, "use_lvds"),
            "include_trigger_config": _npz_bool(reference_npz, "include_trigger_config"),
            "include_daq_config": _npz_bool(reference_npz, "include_daq_config"),
        }
    if actual_flags != expected_flags:
        raise ValueError(f"Configured feature flags {expected_flags} do not match reference.npz {actual_flags}")
    expected_tag = resolved_tag(str(model_cfg["base_tag"]), expected_flags)
    if expected_tag != str(model_cfg["resolved_tag"]):
        raise ValueError(f"Resolved tag should be {expected_tag}, not {model_cfg['resolved_tag']}")
    if model_dir.name != expected_tag:
        raise ValueError(f"Model directory basename {model_dir.name} does not match resolved tag {expected_tag}")

    effective = metadata.get("effective_config", {})
    metadata_flags = {
        "use_trigger": bool(effective.get("use_trigger")),
        "use_lvds": bool(effective.get("use_lvds")),
        "include_trigger_config": bool(effective.get("include_trigger_config")),
        "include_daq_config": bool(effective.get("include_daq_config")),
    }
    if metadata_flags != expected_flags:
        raise ValueError(f"training_metadata.json feature flags {metadata_flags} do not match {expected_flags}")
    expected_alerts = {key: cfg["alert_replay"][key] for key in cfg["alert_replay"]}
    metadata_alerts = {key: effective.get(key) for key in expected_alerts}
    if metadata_alerts != expected_alerts:
        raise ValueError(f"Alert replay settings {expected_alerts} do not match training metadata {metadata_alerts}")

    # This is a real deserialization check, not merely an existence test.
    reference = ReferenceModel.load(str(reference_path))
    detector = AnomalyDetector.load(str(detector_path), reference)
    del detector, reference
    return {
        "model_directory": str(model_dir),
        "base_tag": str(model_cfg["base_tag"]),
        "resolved_tag": expected_tag,
        "config_snapshot": str(snapshot_path),
        "reference_path": str(reference_path),
        "detector_path": str(detector_path),
        "training_metadata_path": str(metadata_path),
        "reference_sha256": sha256(reference_path),
        "detector_sha256": sha256(detector_path),
        "training_metadata_sha256": sha256(metadata_path),
        "config_snapshot_sha256": sha256(snapshot_path),
        "feature_flags": actual_flags,
        "training_metadata": metadata,
    }


def git_value(project_dir: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=project_dir, text=True).strip()


def code_hashes(project_dir: Path) -> dict:
    relative_paths = APPLICATION_CODE_PATHS + [
        "isolation_forest/condor/kb_scan/campaign.py",
        "isolation_forest/condor/kb_scan/run_kb_scan_job.sh",
    ]
    return {relative: sha256(project_dir / relative) for relative in relative_paths}


def prepare(config_path: Path) -> dict:
    config_path = config_path.resolve()
    cfg = load_scan_config(config_path)
    root = campaign_dir(cfg)
    project_dir = Path(cfg["campaign"]["project_dir"])
    model_info = validate_model(cfg)
    current_code_hashes = code_hashes(project_dir)
    application_hashes = {path: current_code_hashes[path] for path in APPLICATION_CODE_PATHS}
    fingerprint = hashlib.sha256(
        (json.dumps(cfg, sort_keys=True) + model_info["reference_sha256"] + model_info["detector_sha256"]).encode()
    ).hexdigest()
    metadata_path = root / "campaign_metadata.json"
    if metadata_path.exists():
        previous = json.loads(metadata_path.read_text())
        if previous.get("campaign_fingerprint") != fingerprint:
            raise RuntimeError(
                f"Campaign tag {cfg['campaign']['tag']} already exists with a different configuration: {root}"
            )
        previous_application_hashes = previous.get("application_code_sha256")
        if previous_application_hashes and previous_application_hashes != application_hashes:
            raise RuntimeError(
                "Application code changed after this campaign was prepared. "
                "Use a new campaign tag instead of mixing detector outputs."
            )

    for directory in (root / "runs", root / "condor" / "logs"):
        directory.mkdir(parents=True, exist_ok=True)
    min_run, max_run = int(cfg["scan"]["min_run"]), int(cfg["scan"]["max_run"])
    runs = list(range(min_run, max_run + 1))
    atomic_text(root / "run_numbers.txt", "".join(f"{run}\n" for run in runs))
    manifest_lines = ["run\trequested_state\n"] + [f"{run}\trequested\n" for run in runs]
    atomic_text(root / "run_manifest.tsv", "".join(manifest_lines))

    wrapper = project_dir / "isolation_forest" / "condor" / "kb_scan" / "run_kb_scan_job.sh"
    submit_text = f"""# Generated by condor/kb_scan/campaign.py prepare
universe   = vanilla
executable = {wrapper}
arguments  = {config_path} $(run)
initialdir = {project_dir / 'isolation_forest'}

output = {root / 'condor' / 'logs'}/$(ClusterId).$(ProcId).run$(run).out
error  = {root / 'condor' / 'logs'}/$(ClusterId).$(ProcId).run$(run).err
log    = {root / 'condor' / 'logs'}/$(ClusterId).campaign.log

request_cpus   = 1
request_memory = 3072
request_disk   = 2048
+JobFlavour = "workday"
+ProjectName = "local"
should_transfer_files = NO
notification = Never
on_exit_hold = (ExitBySignal == True) || (ExitCode != 0)

queue run from {root / 'run_numbers.txt'}
"""
    submit_path = root / "condor" / "submit.sub"
    atomic_text(submit_path, submit_text)
    metadata = {
        "created_at": utc_now(),
        "command": " ".join(sys.argv),
        "campaign_tag": cfg["campaign"]["tag"],
        "campaign_directory": str(root),
        "campaign_fingerprint": fingerprint,
        "config_path": str(config_path),
        "config_sha256": sha256(config_path),
        "git_commit": git_value(project_dir, "rev-parse", "HEAD"),
        "git_branch": git_value(project_dir, "branch", "--show-current"),
        "git_status": git_value(project_dir, "status", "--short", "--branch"),
        "code_sha256": current_code_hashes,
        "application_code_sha256": application_hashes,
        "run_min": min_run,
        "run_max": max_run,
        "n_runs": len(runs),
        "model": model_info,
        "submit_file": str(submit_path),
    }
    atomic_json(metadata_path, metadata)
    atomic_text(root / "config_snapshot.yaml", config_path.read_text())
    return metadata


def _write_run_status(run_dir: Path, payload: Mapping[str, Any]) -> None:
    atomic_json(run_dir / "status.json", dict(payload))


def _input_has_events(path: Path) -> bool:
    """Return whether a Digitizer CSV has at least one event row.

    Header-only CSV files are valid empty detector inputs.  A malformed or
    unreadable file is deliberately not classified as empty: it remains a real
    processing/validation failure.
    """
    try:
        return not pd.read_csv(path, nrows=1).empty
    except Exception as exc:
        raise RuntimeError(f"Cannot validate Digitizer input {path}: {exc}") from exc


def _validate_detector_outputs(run: int, expected_inputs: list, csv_path: Path, paths_path: Path) -> dict:
    """Validate detector publication and account separately for empty inputs."""
    expected_input_strings = [str(Path(path)) for path in expected_inputs]
    if not paths_path.is_file() or paths_path.stat().st_size == 0:
        raise RuntimeError(f"Run {run}: pipeline path manifest is missing or empty: {paths_path}")
    cached = [line.strip() for line in paths_path.read_text().splitlines() if line.strip()]
    if len(cached) != len(set(cached)):
        raise RuntimeError(f"Run {run}: pipeline path manifest contains duplicates")
    if len(cached) != len(expected_input_strings) or set(cached) != set(expected_input_strings):
        raise RuntimeError(f"Run {run}: pipeline path manifest differs from the preflight input manifest")

    expected_by_name = {Path(path).name: Path(path) for path in expected_input_strings}
    if len(expected_by_name) != len(expected_input_strings):
        raise RuntimeError(f"Run {run}: input files do not have unique basenames")

    filenames = set()
    if csv_path.is_file() and csv_path.stat().st_size > 0:
        with csv_path.open(newline="") as handle:
            rows = csv.DictReader(handle)
            if not rows.fieldnames or "filename" not in rows.fieldnames:
                raise RuntimeError(f"Run {run}: anomaly log has no filename column: {csv_path}")
            filenames = {row["filename"] for row in rows if row.get("filename")}

    unexpected = sorted(filenames - set(expected_by_name))
    if unexpected:
        raise RuntimeError(f"Run {run}: anomaly log contains unexpected inputs: {unexpected}")

    missing_names = sorted(set(expected_by_name) - filenames, key=run_subrun_sort_key)
    empty_paths = []
    nonempty_missing = []
    for name in missing_names:
        path = expected_by_name[name]
        if _input_has_events(path):
            nonempty_missing.append(path)
        else:
            empty_paths.append(path)
    if nonempty_missing:
        raise RuntimeError(
            f"Run {run}: detector output is missing for {len(nonempty_missing)} non-empty input(s): "
            + ", ".join(path.name for path in nonempty_missing[:10])
        )

    parsed = {parse_run_subrun(name)[0] for name in filenames}
    if filenames and parsed != {run}:
        raise RuntimeError(f"Run {run}: anomaly log contains run numbers {sorted(parsed)}")

    valid_subruns = sorted(parse_run_subrun(name)[1] for name in filenames)
    empty_subruns = sorted(parse_run_subrun(path.name)[1] for path in empty_paths)
    if any(value is None for value in valid_subruns + empty_subruns):
        raise RuntimeError(f"Run {run}: an input filename could not be parsed into a subrun")
    if len(valid_subruns) != len(set(valid_subruns)):
        raise RuntimeError(f"Run {run}: detector output contains duplicate subrun numbers")
    if len(empty_subruns) != len(set(empty_subruns)):
        raise RuntimeError(f"Run {run}: empty inputs contain duplicate subrun numbers")
    if set(valid_subruns) & set(empty_subruns):
        raise RuntimeError(f"Run {run}: a subrun was classified as both valid and empty")
    if len(valid_subruns) + len(empty_subruns) != len(expected_input_strings):
        raise RuntimeError(f"Run {run}: detector accounting does not cover every input")

    return {
        "n_input_subruns": len(expected_input_strings),
        "n_valid_subruns": len(valid_subruns),
        "n_empty_subruns": len(empty_subruns),
        "valid_subruns": valid_subruns,
        "empty_subruns": empty_subruns,
    }


def _successful_scan_status(accounting: Mapping[str, Any]) -> str:
    return "completed" if int(accounting["n_valid_subruns"]) > 0 else "no_valid_data"


def run_job(
    config_path: Path,
    run: int,
    force: bool = False,
) -> dict:
    config_path = config_path.resolve()
    cfg = load_scan_config(config_path)
    root = campaign_dir(cfg)
    metadata_path = root / "campaign_metadata.json"
    if not metadata_path.exists():
        raise RuntimeError(f"Campaign is not prepared: {metadata_path}")
    campaign_metadata = json.loads(metadata_path.read_text())
    project_dir = Path(cfg["campaign"]["project_dir"])
    current_application_hashes = {
        path: sha256(project_dir / path) for path in APPLICATION_CODE_PATHS
    }
    if current_application_hashes != campaign_metadata.get("application_code_sha256"):
        raise RuntimeError(
            "Application code does not match the prepared campaign snapshot. "
            "Do not mix detector outputs; choose a new campaign tag for changed code."
        )
    min_run, max_run = int(cfg["scan"]["min_run"]), int(cfg["scan"]["max_run"])
    if run < min_run or run > max_run:
        raise ValueError(f"Run {run} is outside configured range {min_run}-{max_run}")
    run_dir = root / "runs" / f"run{run}"
    run_dir.mkdir(parents=True, exist_ok=True)
    status_path = run_dir / "status.json"
    if status_path.exists() and not force:
        previous = json.loads(status_path.read_text())
        if (
            previous.get("campaign_fingerprint") == campaign_metadata["campaign_fingerprint"]
            and previous.get("scan_status") == "completed"
            and Path(previous.get("anomaly_log", "")).is_file()
        ):
            print(f"[SKIP] Run {run} already completed and validated.")
            return previous
        if (
            previous.get("campaign_fingerprint") == campaign_metadata["campaign_fingerprint"]
            and previous.get("scan_status") in {"no_data", "no_valid_data"}
        ):
            print(f"[SKIP] Run {run} already recorded as {previous['scan_status']}. Use --force to rescan.")
            return previous

    started_at = utc_now()
    slab_dir = str(cfg["campaign"]["slab_dir"])
    input_paths = sorted(resolve_run_files(slab_dir, run), key=run_subrun_sort_key)
    input_manifest = run_dir / "input_paths.txt"
    atomic_text(input_manifest, "".join(f"{path}\n" for path in input_paths))
    base_status = {
        "run": run,
        "started_at": started_at,
        "campaign_tag": cfg["campaign"]["tag"],
        "campaign_fingerprint": campaign_metadata["campaign_fingerprint"],
        "model_resolved_tag": cfg["model"]["resolved_tag"],
        "input_manifest": str(input_manifest),
        "n_input_files": len(input_paths),
        "n_input_subruns": len(input_paths),
    }
    if not input_paths:
        result = {
            **base_status,
            "finished_at": utc_now(),
            "scan_status": "no_data",
            "n_valid_subruns": 0,
            "n_empty_subruns": 0,
            "valid_subruns": [],
            "empty_subruns": [],
        }
        _write_run_status(run_dir, result)
        print(f"[NO DATA] Run {run}: no Digitizer files found under {slab_dir}")
        return result

    project_if = Path(cfg["campaign"]["project_dir"]) / "isolation_forest"
    model_cfg = cfg["model"]
    flags = list(model_cfg.get("pipeline_flags", []))
    command = [
        sys.executable, "-m", "src.pipeline",
        "--config", str(model_cfg["config_snapshot"]),
        "--model-tag", str(model_cfg["base_tag"]),
        "--models-dir", str(Path(model_cfg["directory"]).parent),
        "--skip-train",
        "--apply-specific-run", str(run),
        "--skip-evaluate", "--skip-report", "--skip-all-plots",
    ]
    try:
        with tempfile.TemporaryDirectory(prefix=f"autodqm_kb_run{run}_") as tmp_name:
            tmp_root = Path(tmp_name)
            logs_dir = tmp_root / "logs"
            command.extend(["--logs-dir", str(logs_dir), *flags])
            print("[COMMAND] " + " ".join(command), flush=True)
            completed = subprocess.run(command, cwd=project_if, check=False)
            if completed.returncode != 0:
                raise RuntimeError(f"Pipeline exited with status {completed.returncode}")
            tag = str(model_cfg["resolved_tag"])
            generated_dir = logs_dir / tag
            generated_csv = generated_dir / f"{tag}_run{run}.csv"
            generated_paths = generated_dir / f"{tag}_run{run}_paths.txt"
            accounting = _validate_detector_outputs(run, input_paths, generated_csv, generated_paths)
            final_csv = run_dir / "anomaly_log.csv"
            publish_paths = run_dir / f".pipeline_input_paths.txt.tmp.{os.getpid()}"
            shutil.copy2(generated_paths, publish_paths)
            os.replace(publish_paths, run_dir / "pipeline_input_paths.txt")
            if accounting["n_valid_subruns"]:
                publish_csv = run_dir / f".anomaly_log.csv.tmp.{os.getpid()}"
                shutil.copy2(generated_csv, publish_csv)
                os.replace(publish_csv, final_csv)
        scan_status = _successful_scan_status(accounting)
        result = {
            **base_status,
            **accounting,
            "finished_at": utc_now(),
            "scan_status": scan_status,
            "command": command,
            "return_code": 0,
        }
        if accounting["n_valid_subruns"]:
            result.update({
                "anomaly_log": str(final_csv),
                "anomaly_log_sha256": sha256(final_csv),
            })
        else:
            result["data_state_reason"] = "all discovered Digitizer inputs contained zero detector events"
        _write_run_status(run_dir, result)
        print(
            f"[{scan_status.upper()}] Run {run}: {accounting['n_input_subruns']} input, "
            f"{accounting['n_valid_subruns']} valid, {accounting['n_empty_subruns']} empty"
            + (f" -> {final_csv}" if accounting["n_valid_subruns"] else "")
        )
        return result
    except Exception as exc:
        result = {
            **base_status,
            "finished_at": utc_now(),
            "scan_status": "failed",
            "command": command,
            "error": str(exc),
        }
        _write_run_status(run_dir, result)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare", help="Validate the model and generate manifests/submit file")
    prepare_parser.add_argument("--config", required=True, type=Path)
    run_parser = subparsers.add_parser("run-job", help="Apply the frozen model to exactly one run")
    run_parser.add_argument("--config", required=True, type=Path)
    run_parser.add_argument("--run", required=True, type=int)
    run_parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        print(json.dumps(prepare(args.config), indent=2, sort_keys=True))
    else:
        print(json.dumps(run_job(args.config, args.run, args.force), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
