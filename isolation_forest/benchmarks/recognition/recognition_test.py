#!/usr/bin/env python3
"""Known-failure recognition benchmark for AutoFLAME.

The hidden target annotation never enters the model-visible prompt. Detector
summaries and historical-case formatting are imported from the production LLM
module, while this wrapper handles filtering, masking, structured output,
retries, resume, scoring, and reproducible reports.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.kb_schema import parse_kb_run, validate_kb_entries  # noqa: E402
from src.llm import (  # noqa: E402
    _SYSTEM as PRODUCTION_SYSTEM_PROMPT,
    _format_historical_case,
    _historical_snapshot,
)


MANIFEST_PATH = Path(__file__).with_name("recognition_manifest.yaml")
EXPECTED_TARGETS = [1500, 1604, 1637, 1640, 1642, 1702, 1703, 2068, 2126]
EXPECTED_PEERS = {
    1500: [1604],
    1604: [1500],
    1637: [1640, 1642],
    1640: [1637, 1642],
    1642: [1637, 1640],
    1702: [1703],
    1703: [1702],
    2068: [2126],
    2126: [2068],
}
EXPECTED_BAD_DATA = {2071, 2268, 2402}
MODEL_ALIAS_ENV = {"luna": "AUTOFLAME_LUNA_MODEL", "sol": "AUTOFLAME_SOL_MODEL"}

RECOGNITION_TASK = """
---
## Task

Diagnose this test case by comparing its detector evidence with the resolved
historical cases. This benchmark tests recognition of a previously observed
failure family. Use historical cases as evidence, but do not invent facts that
are not supplied. If a field cannot be determined, return "unknown".

Return the requested structured JSON fields only. The reasoning_summary must
be a concise evidence-based rationale, not hidden chain-of-thought. The
supporting_historical_runs list may contain only source runs visible in the
historical reference cases.
"""


class RecognitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    cause: str
    action: str
    recovery: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_historical_runs: list[int]
    reasoning_summary: str


@dataclass
class PreparedCase:
    target_run: int
    family: str
    family_name: str
    canonical_category: str
    accepted_aliases: list[str]
    expected_peers: list[int]
    ground_truth: dict[str, Any]
    filtered_kb: list[dict[str, Any]]
    system_prompt: str
    user_prompt: str
    serialized_prompt: str
    prompt_sha256: str
    target_evidence_source: str
    historical_evidence_sources: list[str]


class ApiCallFailure(RuntimeError):
    def __init__(self, message: str, attempts: int, kind: str):
        super().__init__(message)
        self.attempts = attempts
        self.kind = kind


class ResponseParsingError(ValueError):
    """The API returned content, but it did not satisfy the required schema."""

    def __init__(self, message: str, raw_response: Any = None):
        super().__init__(message)
        self.raw_response = raw_response


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_secrets(value: Any) -> str:
    text = str(value)
    secret = os.environ.get("OPENAI_API_KEY")
    return text.replace(secret, "[REDACTED]") if secret else text


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: dict[str, Any]) -> None:
    targets = manifest.get("targets", [])
    runs = [item.get("run") for item in targets]
    if runs != EXPECTED_TARGETS:
        raise ValueError(f"manifest targets must be exactly {EXPECTED_TARGETS}; found {runs}")
    peers = {item["run"]: item.get("expected_peers") for item in targets}
    if peers != EXPECTED_PEERS:
        raise ValueError(f"manifest peer sets changed: {peers}")
    excluded = set(manifest.get("excluded_bad_data_runs", []))
    if excluded != EXPECTED_BAD_DATA:
        raise ValueError(f"excluded bad-data runs must be {sorted(EXPECTED_BAD_DATA)}")
    if excluded & set(runs):
        raise ValueError("a target is also marked as bad data")
    families = manifest.get("families", {})
    for item in targets:
        family = families.get(item["family"])
        if not family:
            raise ValueError(f"target {item['run']} has undefined family {item['family']}")
        if not family.get("canonical_category") or not family.get("accepted_category_aliases"):
            raise ValueError(f"family {item['family']} lacks category definition")


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def load_kb(path: Path) -> list[dict[str, Any]]:
    return validate_kb_entries(yaml.safe_load(path.read_text(encoding="utf-8")) or [])


def singleton_run(entry: dict[str, Any]) -> int:
    start, end = parse_kb_run(entry["run"])
    if start != end:
        raise ValueError(f"recognition benchmark requires singleton KB entries: {entry['run']}")
    return start


def filter_kb(
    entries: list[dict[str, Any]], target_run: int, excluded_runs: Iterable[int]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    excluded = set(excluded_runs)
    matches = [entry for entry in entries if singleton_run(entry) == target_run]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one ground-truth KB entry for run {target_run}")
    filtered = [
        dict(entry)
        for entry in entries
        if singleton_run(entry) != target_run and singleton_run(entry) not in excluded
    ]
    return dict(matches[0]), filtered


def run_token_pattern(run: int) -> re.Pattern[str]:
    return re.compile(rf"(?<!\d){run}(?!\d)")


def sanitize_target_identifier(text: str, target_run: int) -> str:
    return run_token_pattern(target_run).sub("<TARGET_RUN>", text)


def exact_prompt_serialization(system_prompt: str, user_prompt: str) -> str:
    return json.dumps(
        {"system": system_prompt, "user": user_prompt},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def evidence_path(manifest: dict[str, Any], run: int) -> Path:
    campaign = resolve_path(manifest["campaign_root"])
    return campaign / manifest["evidence_pattern"].format(run=run)


def prepare_case(
    manifest: dict[str, Any],
    target_spec: dict[str, Any],
    kb_entries: list[dict[str, Any]],
    snapshot_loader: Callable[[str, int], str] = _historical_snapshot,
) -> PreparedCase:
    target = int(target_spec["run"])
    excluded = set(manifest["excluded_bad_data_runs"])
    ground_truth, filtered = filter_kb(kb_entries, target, excluded)
    filtered_runs = [singleton_run(entry) for entry in filtered]
    expected_peers = list(target_spec["expected_peers"])

    if target in filtered_runs:
        raise AssertionError(f"target {target} remained in temporary KB")
    if excluded & set(filtered_runs):
        raise AssertionError(f"bad-data entries remained for target {target}")
    missing_peers = set(expected_peers) - set(filtered_runs)
    if missing_peers:
        raise AssertionError(f"target {target} is missing expected peers {sorted(missing_peers)}")

    target_source = evidence_path(manifest, target)
    if not target_source.is_file():
        raise FileNotFoundError(f"target evidence does not exist: {target_source}")
    target_snapshot = snapshot_loader(str(target_source), target)

    case_blocks: list[str] = []
    historical_sources: list[str] = []
    for entry in filtered:
        historical_run = singleton_run(entry)
        source = evidence_path(manifest, historical_run)
        if not source.is_file():
            raise FileNotFoundError(f"historical evidence does not exist: {source}")
        historical_sources.append(str(source))
        snapshot = snapshot_loader(str(source), historical_run)
        case_blocks.append(_format_historical_case(entry, snapshot))

    user_prompt = (
        "## Current test case\n\n"
        "Case ID: CASE_TARGET\n"
        "Detector evidence (production run-level anomaly snapshot):\n"
        + target_snapshot
        + "\n\n---\n\n## Historical reference cases\n\n"
        + "\n\n".join(case_blocks)
        + RECOGNITION_TASK
    )
    system_prompt = sanitize_target_identifier(PRODUCTION_SYSTEM_PROMPT, target)
    user_prompt = sanitize_target_identifier(user_prompt, target)
    serialized = exact_prompt_serialization(system_prompt, user_prompt)

    if run_token_pattern(target).search(serialized):
        raise AssertionError(f"target run {target} leaked into serialized prompt")
    for bad_run in excluded:
        if run_token_pattern(bad_run).search(serialized):
            raise AssertionError(f"bad-data run {bad_run} leaked into target {target} prompt")
    visible_peers = [peer for peer in expected_peers if run_token_pattern(peer).search(serialized)]
    if not visible_peers:
        raise AssertionError(f"no same-family peer is visible for target {target}")
    # Ground truth is deliberately not used above; only the independent copy is returned.
    family = manifest["families"][target_spec["family"]]
    if normalize_category(ground_truth["category"]) != normalize_category(family["canonical_category"]):
        raise AssertionError(f"KB category disagrees with manifest for target {target}")

    return PreparedCase(
        target_run=target,
        family=target_spec["family"],
        family_name=family["display_name"],
        canonical_category=family["canonical_category"],
        accepted_aliases=list(family["accepted_category_aliases"]),
        expected_peers=expected_peers,
        ground_truth=ground_truth,
        filtered_kb=filtered,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        serialized_prompt=serialized,
        prompt_sha256=sha256_text(serialized),
        target_evidence_source=str(target_source),
        historical_evidence_sources=historical_sources,
    )


def parse_response_text(raw_text: str) -> RecognitionResponse:
    text = raw_text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ResponseParsingError(f"response is not valid JSON: {exc}", raw_text) from exc
    try:
        return RecognitionResponse.model_validate(payload)
    except ValidationError as exc:
        raise ResponseParsingError(f"response does not match recognition schema: {exc}", raw_text) from exc


def normalize_category(value: str) -> str:
    normalized = re.sub(r"[\s-]+", "_", str(value).strip().lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def category_is_correct(predicted: str, accepted_aliases: Iterable[str]) -> bool:
    return normalize_category(predicted) in {normalize_category(item) for item in accepted_aliases}


def ground_truth_field_status(value: Any) -> str:
    return "not_scorable" if str(value).strip().lower() == "unknown" else "ground_truth_available"


def git_metadata() -> dict[str, Any]:
    def command(*args: str) -> str:
        result = subprocess.run(
            args, cwd=REPO_ROOT, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.stdout.strip()

    try:
        commit = command("git", "rev-parse", "HEAD")
        status = command("git", "status", "--porcelain")
        return {"commit": commit, "dirty": bool(status)}
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"commit": None, "dirty": None, "error": str(exc)}


def make_result_dir(prefix: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(__file__).with_name("results") / f"{prefix}_{stamp}"


def initialise_result_dir(result_dir: Path) -> None:
    for name in ("prompts", "contexts", "responses", "parsed", "metadata"):
        (result_dir / name).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def save_preflight(case: PreparedCase, result_dir: Path) -> None:
    (result_dir / "prompts" / f"target_{case.target_run}.txt").write_text(
        case.serialized_prompt + "\n", encoding="utf-8"
    )
    (result_dir / "contexts" / f"target_{case.target_run}_kb.yaml").write_text(
        yaml.safe_dump(case.filtered_kb, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    write_json(
        result_dir / "metadata" / f"target_{case.target_run}_preflight.json",
        {
            "target_test_id": case.target_run,
            "family": case.family,
            "peer_runs_available": case.expected_peers,
            "prompt_sha256": case.prompt_sha256,
            "target_identifier_masked": True,
            "target_kb_entry_absent": True,
            "bad_data_entries_absent": True,
            "expected_peer_visible": True,
            "target_evidence_source": case.target_evidence_source,
            "historical_evidence_sources": case.historical_evidence_sources,
        },
    )


def prepare_all_cases(manifest: dict[str, Any]) -> tuple[list[PreparedCase], Path, str]:
    kb_path = resolve_path(manifest["ground_truth_kb"])
    if not kb_path.is_file():
        raise FileNotFoundError(f"ground-truth KB does not exist: {kb_path}")
    kb_entries = load_kb(kb_path)
    # The same immutable per-run log is reused in many leave-one-out contexts.
    # Cache its production summary so one dry-run reads each CSV only once.
    snapshot_cache: dict[tuple[str, int], str] = {}

    def cached_snapshot(path: str, run: int) -> str:
        key = (path, run)
        if key not in snapshot_cache:
            snapshot_cache[key] = _historical_snapshot(path, run)
        return snapshot_cache[key]

    cases = [
        prepare_case(manifest, spec, kb_entries, snapshot_loader=cached_snapshot)
        for spec in manifest["targets"]
    ]
    return cases, kb_path, sha256_file(kb_path)


def dry_run(result_dir: Path | None = None) -> Path:
    manifest = load_manifest()
    cases, kb_path, kb_hash = prepare_all_cases(manifest)
    output = result_dir or make_result_dir("dry_run")
    initialise_result_dir(output)
    for case in cases:
        save_preflight(case, output)
    config = {
        "mode": "dry-run",
        "benchmark_id": manifest["benchmark_id"],
        "created_at": utc_now(),
        "target_runs": EXPECTED_TARGETS,
        "ground_truth_kb": str(kb_path),
        "kb_sha256": kb_hash,
        "git": git_metadata(),
        "api_calls": 0,
    }
    write_json(output / "run_config.json", config)
    records = [preflight_record(case) for case in cases]
    write_results(output, records, mode="dry-run")
    print(f"Dry-run passed for {len(cases)} cases; 0 API calls. Results: {output}")
    for case in cases:
        print(f"  {case.target_run}: peers={case.expected_peers} leakage=PASS")
    return output


def preflight_record(case: PreparedCase) -> dict[str, Any]:
    return {
        "target_run": case.target_run,
        "family": case.family,
        "family_name": case.family_name,
        "expected_peers": case.expected_peers,
        "canonical_category": case.canonical_category,
        "prompt_sha256": case.prompt_sha256,
        "status": "preflight_passed",
        "leakage_check": "passed",
    }


def resolve_model(model: str | None, alias: str | None) -> tuple[str, str | None]:
    if bool(model) == bool(alias):
        raise ValueError("specify exactly one of --model or --model-alias")
    if model:
        return model, None
    env_name = MODEL_ALIAS_ENV[alias]
    resolved = os.environ.get(env_name)
    if not resolved:
        raise ValueError(f"--model-alias {alias} requires environment variable {env_name}")
    return resolved, alias


def openai_call(system_prompt: str, user_prompt: str, model: str) -> tuple[Any, RecognitionResponse]:
    from openai import OpenAI

    response = OpenAI().responses.create(
        model=model,
        instructions=system_prompt,
        input=user_prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": "autoflame_recognition_response",
                "schema": RecognitionResponse.model_json_schema(),
                "strict": True,
            }
        },
    )
    try:
        parsed = parse_response_text(getattr(response, "output_text", ""))
    except ResponseParsingError as exc:
        exc.raw_response = response
        raise
    return response, parsed


def raw_response_payload(response: Any) -> Any:
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    if isinstance(response, (dict, list, str, int, float, bool)) or response is None:
        return response
    return {"representation": repr(response)}


def token_usage(response: Any) -> Any:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if hasattr(usage, "model_dump"):
        return usage.model_dump(mode="json")
    return usage


def call_with_retries(
    case: PreparedCase,
    model: str,
    response_dir: Path,
    api_call: Callable[[str, str, str], tuple[Any, RecognitionResponse]],
    max_attempts: int = 3,
    sleep_fn: Callable[[float], None] = time.sleep,
    metadata_dir: Path | None = None,
    call_metadata: dict[str, Any] | None = None,
) -> tuple[RecognitionResponse, Any, int, float]:
    started = time.monotonic()
    errors: list[str] = []
    failure_kinds: list[str] = []
    for attempt in range(1, max_attempts + 1):
        # Recreate and recheck the exact strings immediately before every paid
        # attempt, including retries. Model metadata is not part of this hash.
        serialized = exact_prompt_serialization(case.system_prompt, case.user_prompt)
        if serialized != case.serialized_prompt or sha256_text(serialized) != case.prompt_sha256:
            raise AssertionError(f"prompt changed after preflight for target {case.target_run}")
        if run_token_pattern(case.target_run).search(serialized):
            raise AssertionError(f"target run {case.target_run} leaked before API attempt {attempt}")
        attempt_started = time.monotonic()
        attempt_record = {
            **(call_metadata or {}),
            "attempt": attempt,
            "timestamp": utc_now(),
            "sanitized_prompt_sha256": case.prompt_sha256,
        }
        try:
            response, parsed = api_call(case.system_prompt, case.user_prompt, model)
            write_json(
                response_dir / f"target_{case.target_run}_attempt_{attempt}_raw.json",
                raw_response_payload(response),
            )
            if metadata_dir is not None:
                write_json(metadata_dir / f"target_{case.target_run}_attempt_{attempt}.json", {
                    **attempt_record,
                    "status": "completed",
                    "response_latency_seconds": time.monotonic() - attempt_started,
                    "token_usage": token_usage(response),
                    "api_error_retry_count": attempt - 1,
                })
            return parsed, response, attempt - 1, time.monotonic() - started
        except Exception as exc:  # preserve every failed attempt; retry both API and parse failures
            safe_message = redact_secrets(exc)
            errors.append(f"{type(exc).__name__}: {safe_message}")
            failure_kinds.append("parsing_failed" if isinstance(exc, ResponseParsingError) else "api_failed")
            raw = getattr(exc, "raw_response", None)
            if raw is not None:
                write_json(
                    response_dir / f"target_{case.target_run}_attempt_{attempt}_raw.json",
                    raw_response_payload(raw),
                )
            write_json(response_dir / f"target_{case.target_run}_attempt_{attempt}_error.json", {
                "attempt": attempt,
                "error_type": type(exc).__name__,
                "error": safe_message,
                "failure_kind": failure_kinds[-1],
            })
            if metadata_dir is not None:
                write_json(metadata_dir / f"target_{case.target_run}_attempt_{attempt}.json", {
                    **attempt_record,
                    "status": failure_kinds[-1],
                    "response_latency_seconds": time.monotonic() - attempt_started,
                    "token_usage": token_usage(raw) if raw is not None else None,
                    "api_error_retry_count": attempt - 1,
                    "error_type": type(exc).__name__,
                    "error": safe_message,
                })
            if attempt < max_attempts:
                sleep_fn(float(2 ** (attempt - 1)))
    kind = "parsing_failed" if set(failure_kinds) == {"parsing_failed"} else "api_failed"
    raise ApiCallFailure("; ".join(errors), max_attempts, kind)


def completed_record(case: PreparedCase, parsed: RecognitionResponse, metadata: dict[str, Any]) -> dict[str, Any]:
    prediction = parsed.model_dump(mode="json")
    return {
        "target_run": case.target_run,
        "family": case.family,
        "family_name": case.family_name,
        "expected_peers": case.expected_peers,
        "canonical_category": case.canonical_category,
        "accepted_category_aliases": case.accepted_aliases,
        "ground_truth": case.ground_truth,
        "prediction": prediction,
        "field_status": {
            "category": "correct" if category_is_correct(prediction["category"], case.accepted_aliases) else "incorrect",
            "cause": ground_truth_field_status(case.ground_truth["cause"]),
            "action": ground_truth_field_status(case.ground_truth["action"]),
            "recovery": ground_truth_field_status(case.ground_truth["recovery"]),
        },
        "prompt_sha256": case.prompt_sha256,
        "status": "completed",
        "metadata": metadata,
    }


def failure_record(case: PreparedCase, error: Exception, kind: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_run": case.target_run,
        "family": case.family,
        "family_name": case.family_name,
        "expected_peers": case.expected_peers,
        "canonical_category": case.canonical_category,
        "ground_truth": case.ground_truth,
        "prompt_sha256": case.prompt_sha256,
        "status": kind,
        "error": f"{type(error).__name__}: {error}",
        "metadata": metadata,
    }


def run_benchmark(
    model: str,
    model_alias: str | None,
    result_dir: Path,
    force: bool = False,
    api_call: Callable[[str, str, str], tuple[Any, RecognitionResponse]] = openai_call,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Path:
    if api_call is openai_call and not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set")
    manifest = load_manifest()
    cases, kb_path, kb_hash = prepare_all_cases(manifest)
    initialise_result_dir(result_dir)
    config_path = result_dir / "run_config.json"
    if config_path.exists():
        existing_config = json.loads(config_path.read_text(encoding="utf-8"))
        if existing_config.get("model_id") != model:
            raise ValueError("result directory belongs to a different model ID")
        if existing_config.get("kb_sha256") != kb_hash:
            raise ValueError("KB changed since this result directory was created")
    else:
        write_json(
            config_path,
            {
                "mode": "run",
                "benchmark_id": manifest["benchmark_id"],
                "created_at": utc_now(),
                "model_id": model,
                "model_alias": model_alias,
                "target_runs": EXPECTED_TARGETS,
                "ground_truth_kb": str(kb_path),
                "kb_sha256": kb_hash,
                "git": git_metadata(),
            },
        )

    records_by_run: dict[int, dict[str, Any]] = {}
    results_path = result_dir / "results.json"
    if results_path.exists():
        prior = json.loads(results_path.read_text(encoding="utf-8"))
        records_by_run = {int(item["target_run"]): item for item in prior.get("tests", [])}

    git_info = git_metadata()
    for case in cases:
        save_preflight(case, result_dir)
        previous = records_by_run.get(case.target_run)
        if previous and previous.get("status") == "completed" and not force:
            print(f"Skipping completed target {case.target_run}")
            continue
        base_metadata = {
            "model_id": model,
            "target_test_id": case.target_run,
            "family": case.family,
            "peer_runs_available": case.expected_peers,
            "timestamp": utc_now(),
            "sanitized_prompt_sha256": case.prompt_sha256,
            "kb_sha256": kb_hash,
            "detector_evidence_source_files": [case.target_evidence_source] + case.historical_evidence_sources,
            "benchmark_code_git_commit": git_info.get("commit"),
            "git_dirty": git_info.get("dirty"),
        }
        try:
            parsed, raw, retry_count, latency = call_with_retries(
                case,
                model,
                result_dir / "responses",
                api_call,
                sleep_fn=sleep_fn,
                metadata_dir=result_dir / "metadata",
                call_metadata=base_metadata,
            )
            metadata = {
                **base_metadata,
                "response_latency_seconds": latency,
                "token_usage": token_usage(raw),
                "api_error_retry_count": retry_count,
            }
            write_json(result_dir / "parsed" / f"target_{case.target_run}.json", parsed.model_dump(mode="json"))
            write_json(result_dir / "metadata" / f"target_{case.target_run}_call.json", metadata)
            records_by_run[case.target_run] = completed_record(case, parsed, metadata)
        except ApiCallFailure as exc:
            metadata = {**base_metadata, "api_error_retry_count": exc.attempts - 1}
            records_by_run[case.target_run] = failure_record(case, exc, exc.kind, metadata)
        write_results(result_dir, [records_by_run[r] for r in EXPECTED_TARGETS if r in records_by_run])

    ordered = [records_by_run[r] for r in EXPECTED_TARGETS if r in records_by_run]
    write_results(result_dir, ordered)
    return result_dir


def accuracy_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [item for item in records if item.get("status") == "completed"]
    correct = sum(item.get("field_status", {}).get("category") == "correct" for item in completed)
    complete = len(completed) == len(EXPECTED_TARGETS)
    return {
        "correct": correct,
        "completed": len(completed),
        "total": len(EXPECTED_TARGETS),
        "complete": complete,
        "display": f"{correct}/9" if complete else f"{correct}/{len(completed)} completed (incomplete)",
        "accuracy": correct / len(completed) if completed else None,
    }


def family_summaries(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in records:
        family = item["family"]
        summary = output.setdefault(family, {"name": item["family_name"], "correct": 0, "completed": 0, "total": 0})
        summary["total"] += 1
        if item.get("status") == "completed":
            summary["completed"] += 1
            summary["correct"] += item.get("field_status", {}).get("category") == "correct"
    return output


def markdown_value(value: Any) -> str:
    return str(value).replace("\n", " ").strip()


def render_report(records: list[dict[str, Any]], mode: str = "run") -> str:
    if mode == "dry-run":
        lines = ["# AutoFLAME recognition benchmark dry-run", "", "No API calls were made.", "", "| Target | Family | Expected peers | Leakage |", "| ---: | --- | --- | --- |"]
        for item in records:
            lines.append(f"| {item['target_run']} | {item['family_name']} | {item['expected_peers']} | PASS |")
        return "\n".join(lines) + "\n"

    overall = accuracy_summary(records)
    lines = [
        "# AutoFLAME known-failure recognition report",
        "",
        f"Category recognition accuracy: **{overall['display']}**",
        "",
    ]
    if not overall["complete"]:
        lines.append("The benchmark is incomplete; failed or missing API calls are not counted as wrong predictions.\n")
    lines += ["## Per-family category recognition", "", "| Family | Correct | Completed | Planned |", "| --- | ---: | ---: | ---: |"]
    for summary in family_summaries(records).values():
        lines.append(f"| {summary['name']} | {summary['correct']} | {summary['completed']} | {summary['total']} |")
    lines += ["", "## Per-target details", ""]
    for item in records:
        lines += [f"### Target {item['target_run']} — {item['family_name']}", "", f"- Same-family peers available: {item['expected_peers']}", f"- Status: {item['status']}"]
        gt = item.get("ground_truth", {})
        if gt:
            lines += ["", "| Field | Ground truth | Prediction | Status |", "| --- | --- | --- | --- |"]
            prediction = item.get("prediction", {})
            statuses = item.get("field_status", {})
            for field in ("category", "cause", "action", "recovery"):
                lines.append(f"| {field} | {markdown_value(gt.get(field, ''))} | {markdown_value(prediction.get(field, ''))} | {statuses.get(field, 'not_completed')} |")
            if prediction:
                lines += ["", f"- Confidence: {prediction['confidence']}", f"- Supporting historical runs: {prediction['supporting_historical_runs']}", f"- Reasoning summary: {prediction['reasoning_summary']}"]
        if item.get("error"):
            lines += ["", f"- Error: {item['error']}"]
        lines.append("")
    return "\n".join(lines)


def write_results(result_dir: Path, records: list[dict[str, Any]], mode: str = "run") -> None:
    payload = {"summary": accuracy_summary(records) if mode == "run" else {"preflight_passed": len(records)}, "tests": records}
    write_json(result_dir / "results.json", payload)
    (result_dir / "report.md").write_text(render_report(records, mode), encoding="utf-8")
    fields = ["target_run", "family", "family_name", "expected_peers", "status", "canonical_category", "predicted_category", "category_status", "prompt_sha256"]
    with (result_dir / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in records:
            writer.writerow({
                "target_run": item["target_run"],
                "family": item["family"],
                "family_name": item["family_name"],
                "expected_peers": json.dumps(item["expected_peers"]),
                "status": item["status"],
                "canonical_category": item["canonical_category"],
                "predicted_category": item.get("prediction", {}).get("category", ""),
                "category_status": item.get("field_status", {}).get("category", ""),
                "prompt_sha256": item["prompt_sha256"],
            })


def load_completed_results(path: Path) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    result_dir = path.resolve()
    config = json.loads((result_dir / "run_config.json").read_text(encoding="utf-8"))
    payload = json.loads((result_dir / "results.json").read_text(encoding="utf-8"))
    by_run = {int(item["target_run"]): item for item in payload["tests"]}
    if set(by_run) != set(EXPECTED_TARGETS):
        raise ValueError(f"comparison requires all nine target records in {result_dir}")
    return config, by_run


def render_model_section(label: str, item: dict[str, Any]) -> list[str]:
    if item.get("status") != "completed":
        return [f"#### {label}", "", f"- Status: {item.get('status')}", f"- Error: {item.get('error', 'not completed')}", ""]
    pred = item["prediction"]
    return [
        f"#### {label}", "",
        f"- Predicted category: {pred['category']}",
        f"- Predicted cause: {markdown_value(pred['cause'])}",
        f"- Predicted action: {markdown_value(pred['action'])}",
        f"- Predicted recovery: {markdown_value(pred['recovery'])}",
        f"- Confidence: {pred['confidence']}",
        f"- Supporting historical runs: {pred['supporting_historical_runs']}",
        f"- Category: {item['field_status']['category']}", "",
    ]


def compare_results(luna_dir: Path, sol_dir: Path, output: Path | None = None) -> Path:
    luna_config, luna = load_completed_results(luna_dir)
    sol_config, sol = load_completed_results(sol_dir)
    for run in EXPECTED_TARGETS:
        if luna[run]["prompt_sha256"] != sol[run]["prompt_sha256"]:
            raise ValueError(f"model-visible prompts differ for target {run}")
    luna_records = [luna[run] for run in EXPECTED_TARGETS]
    sol_records = [sol[run] for run in EXPECTED_TARGETS]
    ls, ss = accuracy_summary(luna_records), accuracy_summary(sol_records)
    lines = [
        "# AutoFLAME Luna vs Sol recognition comparison", "",
        f"Luna model ID: `{luna_config.get('model_id')}`  ",
        f"Sol model ID: `{sol_config.get('model_id')}`", "",
        "## Overall", "", "| Model | Category correct | Accuracy |", "| --- | ---: | ---: |",
        f"| Luna | {ls['display']} | {ls['accuracy']:.1%} |" if ls["accuracy"] is not None else "| Luna | 0/0 completed (incomplete) | n/a |",
        f"| Sol | {ss['display']} | {ss['accuracy']:.1%} |" if ss["accuracy"] is not None else "| Sol | 0/0 completed (incomplete) | n/a |",
        "", "## Per family", "", "| Family | Luna | Sol |", "| --- | ---: | ---: |",
    ]
    lf, sf = family_summaries(luna_records), family_summaries(sol_records)
    for family in lf:
        a, b = lf[family], sf[family]
        lines.append(f"| {a['name']} | {a['correct']}/{a['completed']} completed (planned {a['total']}) | {b['correct']}/{b['completed']} completed (planned {b['total']}) |")
    lines += ["", "## Per target", ""]
    for run in EXPECTED_TARGETS:
        left, right = luna[run], sol[run]
        gt = left["ground_truth"]
        lines += [
            f"### Target {run} — {left['family_name']}", "",
            f"- Same-family peers available: {left['expected_peers']}",
            f"- Ground-truth category: {gt['category']}",
            f"- Ground-truth cause: {markdown_value(gt['cause'])}",
            f"- Ground-truth action: {markdown_value(gt['action'])}",
            f"- Ground-truth recovery: {markdown_value(gt['recovery'])}", "",
        ]
        lines += render_model_section("Luna", left)
        lines += render_model_section("Sol", right)
    destination = output or Path.cwd() / "recognition_model_comparison.md"
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    dry = subparsers.add_parser("dry-run", help="build and validate all prompts without API calls")
    dry.add_argument("--result-dir", type=Path)
    run = subparsers.add_parser("run", help="run or resume one model")
    group = run.add_mutually_exclusive_group(required=True)
    group.add_argument("--model")
    group.add_argument("--model-alias", choices=sorted(MODEL_ALIAS_ENV))
    run.add_argument("--result-dir", type=Path, help="reuse this directory to resume")
    run.add_argument("--force", action="store_true", help="rerun completed targets")
    compare = subparsers.add_parser("compare", help="compare completed Luna and Sol result directories")
    compare.add_argument("--luna", type=Path, required=True)
    compare.add_argument("--sol", type=Path, required=True)
    compare.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "dry-run":
            dry_run(args.result_dir)
        elif args.command == "run":
            model, alias = resolve_model(args.model, args.model_alias)
            output = args.result_dir or make_result_dir(alias or re.sub(r"[^a-zA-Z0-9_.-]+", "_", model))
            print(f"Running model {model}; results: {output}")
            run_benchmark(model, alias, output, force=args.force)
        else:
            output = compare_results(args.luna, args.sol, args.output)
            print(f"Comparison report: {output}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
