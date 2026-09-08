#!/usr/bin/env python3
"""Novel-failure generation benchmark with explicit family removal."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


REPO_ROOT = Path(__file__).resolve().parents[2]
RECOGNITION_DIR = REPO_ROOT / "benchmarks" / "recognition"
for import_path in (REPO_ROOT, RECOGNITION_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import recognition_test as recognition  # noqa: E402
import context_builders as contextual  # noqa: E402
from src.llm import (  # noqa: E402
    _SYSTEM as PRODUCTION_SYSTEM_PROMPT,
    _format_historical_case,
    _historical_snapshot,
)


MANIFEST_PATH = Path(__file__).with_name("novel_manifest.yaml")
CONTEXT_MANIFEST_PATH = Path(__file__).with_name("context_manifest.yaml")
EXPECTED_TARGETS = [1620, 1640, 1642, 1702, 1703, 2126]
EXPECTED_EXCLUSIONS = {
    1620: [1620],
    1640: [1640, 1642],
    1642: [1642, 1640],
    1702: [1702, 1703],
    1703: [1703, 1702],
    2126: [2126],
}
CONTEXT_EXPECTED_EXCLUSIONS = {
    1620: [1620],
    1640: [1640, 1642, 1637],
    1642: [1642, 1640, 1637],
    1702: [1702, 1703],
    1703: [1703, 1702],
    2126: [2126],
}
CONTEXT_MODES = ("baseline", "full")
MODEL_ALIAS_ENV = {"luna": "AUTOFLAME_LUNA_MODEL", "sol": "AUTOFLAME_SOL_MODEL"}

NOVEL_TASK = """
---
## Task

Infer the most plausible detector problem using only the current AutoDQM anomaly
evidence and the remaining historical reference cases. The target's recognition
family has been removed. Historical cases are non-exhaustive analogies, not a
closed category list. Use "unknown" when the evidence does not support a field,
and do not invent unavailable measurements.

Return only the requested structured JSON. `action` is a proposed diagnostic or
corrective action conditional on the diagnosis. `confidence` is a number from
0.0 to 1.0. `supporting_historical_runs` may contain only source runs visible in
the historical reference cases. `reasoning_summary` must be concise and
evidence-based; do not provide hidden chain-of-thought. Do not predict recovery.
"""

DIRECT_CONTEXT_COMPONENTS = (
    "raw_digitizer_data",
    "triggerboard_data",
    "lvds_counts",
    "daq_status",
    "cpu_data",
    "board_matching",
    "queue_state",
    "trigger_configuration",
    "elog_or_provenance",
    "target_ground_truth",
)


class NovelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    cause: str
    action: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_historical_runs: list[int]
    reasoning_summary: str


class ResponseParsingError(recognition.ResponseParsingError):
    """Novel-schema parsing failure recognized by the shared retry helper."""


@dataclass
class PreparedNovelCase:
    target_run: int
    context_mode: str
    exclude_runs: list[int]
    filtered_kb: list[dict[str, Any]]
    visible_historical_runs: list[int]
    system_prompt: str
    user_prompt: str
    serialized_prompt: str
    prompt_sha256: str
    target_evidence_source: str
    historical_evidence_sources: list[str]
    context_source_paths: dict[str, list[str]]
    anomaly_summary: str
    trigger_summary: str
    lvds_summary: str
    daq_config_summary: str
    context_availability: dict[str, bool]
    forbidden_target_texts: dict[str, str]
    audit: dict[str, Any]


def manifest_path_for(context_mode: str) -> Path:
    if context_mode not in CONTEXT_MODES:
        raise ValueError(f"unsupported context mode: {context_mode}")
    return CONTEXT_MANIFEST_PATH if context_mode == "full" else MANIFEST_PATH


def load_manifest(path: Path | None = None, context_mode: str = "baseline") -> dict[str, Any]:
    path = path or manifest_path_for(context_mode)
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate_manifest(manifest, context_mode=context_mode)
    return manifest


def validate_manifest(manifest: dict[str, Any], context_mode: str = "baseline") -> None:
    if manifest.get("expected_case_count") != len(EXPECTED_TARGETS):
        raise ValueError("expected_case_count must be 6")
    targets = manifest.get("targets")
    if not isinstance(targets, dict) or list(targets) != EXPECTED_TARGETS:
        raise ValueError(f"manifest targets must be exactly {EXPECTED_TARGETS}")
    actual = {int(run): spec.get("exclude_runs") for run, spec in targets.items()}
    expected_exclusions = (
        CONTEXT_EXPECTED_EXCLUSIONS if context_mode == "full" else EXPECTED_EXCLUSIONS
    )
    if actual != expected_exclusions:
        raise ValueError(f"explicit exclusion sets changed: {actual}")
    for key in ("production_kb", "frozen_campaign", "evidence_pattern", "evidence_source_type"):
        if not manifest.get(key):
            raise ValueError(f"manifest is missing {key}")
    if context_mode == "full":
        sources = manifest.get("context_sources")
        if not isinstance(sources, dict):
            raise ValueError("contextual manifest is missing context_sources")
        for key in ("input_paths_pattern", "run_configs_dir", "thresholds_json_path"):
            if not sources.get(key):
                raise ValueError(f"contextual manifest is missing context_sources.{key}")


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def evidence_path(manifest: dict[str, Any], run: int) -> Path:
    return resolve_path(manifest["frozen_campaign"]) / manifest["evidence_pattern"].format(run=run)


def split_kb(
    entries: list[dict[str, Any]], target_run: int, exclude_runs: list[int]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    excluded = set(exclude_runs)
    if target_run not in excluded:
        raise ValueError(f"target {target_run} must exclude itself")
    matches = [entry for entry in entries if recognition.singleton_run(entry) == target_run]
    if len(matches) != 1:
        raise ValueError(f"expected one KB entry for target {target_run}")
    filtered = [
        dict(entry) for entry in entries if recognition.singleton_run(entry) not in excluded
    ]
    return dict(matches[0]), filtered


def normalized_text(value: Any) -> str:
    return " ".join(str(value).split())


def sanitize_contextual_kb(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Remove sentences explicitly attributed to eLog while retaining every case.

    YAML provenance comments are never loaded.  A few production KB values contain
    explicit eLog-attributed sentences; the contextual benchmark must not expose
    those sentences, so they are removed without category-based case filtering.
    """
    cleaned: list[dict[str, Any]] = []
    redactions = 0
    for entry in entries:
        item = dict(entry)
        for field in ("cause", "action", "recovery"):
            value = item.get(field)
            if not isinstance(value, str):
                continue
            sentences = re.split(r"(?<=[.!?])\s+", normalized_text(value))
            kept = []
            for sentence in sentences:
                if re.search(r"\belog\b|run log message|provenance", sentence, re.IGNORECASE):
                    redactions += 1
                elif sentence:
                    kept.append(sentence)
            item[field] = " ".join(kept) or "unknown"
        cleaned.append(item)
    return cleaned, redactions


def target_field_audit(
    serialized_prompt: str,
    target_entry: dict[str, Any],
    filtered_kb: list[dict[str, Any]],
) -> tuple[dict[str, bool], dict[str, bool], dict[str, bool]]:
    prompt = normalized_text(serialized_prompt)
    literal_absence: dict[str, bool] = {}
    independent_collision: dict[str, bool] = {}
    provenance_absence: dict[str, bool] = {}
    for field in ("category", "cause", "action", "recovery"):
        target_value = normalized_text(target_entry.get(field, ""))
        literal_absence[field] = bool(target_value) and target_value not in prompt
        independent_collision[field] = bool(target_value) and any(
            normalized_text(entry.get(field, "")) == target_value for entry in filtered_kb
        )
        # A shared category label supplied by a retained historical case is not
        # target provenance.  The target entry and its annotation remain absent.
        provenance_absence[field] = literal_absence[field] or independent_collision[field]
    return provenance_absence, literal_absence, independent_collision


def build_audit(
    target: int,
    exclusions: list[int],
    target_entry: dict[str, Any],
    filtered_kb: list[dict[str, Any]],
    system_prompt: str,
    user_prompt: str,
    serialized_prompt: str,
    target_source: Path,
    context_mode: str,
    context_source_paths: dict[str, list[str]],
    context_availability: dict[str, bool],
    context_summaries: dict[str, str],
    kb_provenance_redactions: int,
) -> dict[str, Any]:
    visible_runs = [recognition.singleton_run(entry) for entry in filtered_kb]
    fields_absent, literal_absence, independent_collisions = target_field_audit(
        serialized_prompt, target_entry, filtered_kb
    )
    excluded_absent = {
        str(run): recognition.run_token_pattern(run).search(serialized_prompt) is None
        for run in exclusions
    }
    exact_serialization = recognition.exact_prompt_serialization(system_prompt, user_prompt)
    all_context_paths = [path for paths in context_source_paths.values() for path in paths]
    source_tokens_absent = all(
        path not in serialized_prompt and Path(path).name not in serialized_prompt
        for path in [str(target_source), *all_context_paths]
    ) and all(token not in serialized_prompt for token in ("/afs/", "/eos/"))
    no_elog_or_provenance = re.search(
        r"\belog\b|run log message|provenance comment", serialized_prompt, re.IGNORECASE
    ) is None
    full_mode = context_mode == "full"
    model_visible_components = [
        "production_system_instruction",
        "target_frozen_if_autodqm_anomaly_summary",
    ]
    if full_mode:
        model_visible_components.extend(
            ["trigger_summary", "lvds_summary", "daq_config_summary"]
        )
    model_visible_components.append("filtered_historical_kb_with_frozen_autodqm_snapshots")
    return {
        "target_test_id": target,
        "context_mode": context_mode,
        "exclude_runs": exclusions,
        "model_visible_components": model_visible_components,
        "direct_context_not_added": {
            name: not (
                full_mode
                and name in {"triggerboard_data", "lvds_counts", "trigger_configuration"}
            )
            for name in DIRECT_CONTEXT_COMPONENTS
        },
        "context_sources_included": context_availability,
        "context_source_types": (
            {
                "trigger": "TriggerBoard detector telemetry CSV",
                "lvds": "LVDS detector telemetry CSV",
                "daq_config": "MilliDAQ run configuration through repository parsers",
            }
            if full_mode
            else {}
        ),
        "context_summaries_compact": all(
            len(summary) <= contextual.MAX_SECTION_CHARS for summary in context_summaries.values()
        ),
        "kb_elog_sentences_redacted": kb_provenance_redactions,
        "no_elog_or_provenance_text_present": no_elog_or_provenance,
        "audit_note": (
            "Full mode adds compact detector/DAQ/config summaries from allowlisted sources."
            if full_mode
            else "Baseline mode appends no separate direct detector context."
        ),
        "exact_serialized_prompt_inspected": exact_serialization == serialized_prompt,
        "prompt_only_allowlisted_components": True,
        "target_identifier_masked": recognition.run_token_pattern(target).search(serialized_prompt) is None,
        "excluded_run_identifiers_absent": excluded_absent,
        "target_kb_entry_absent": target not in visible_runs,
        "required_family_entries_absent": set(exclusions).isdisjoint(visible_runs),
        "target_ground_truth_fields_absent": fields_absent,
        "target_ground_truth_literal_absent": literal_absence,
        "target_ground_truth_independent_historical_collision": independent_collisions,
        "target_source_path_and_filename_absent": source_tokens_absent,
        "prompt_sha256": recognition.sha256_text(serialized_prompt),
    }


def assert_case_safe(case: PreparedNovelCase) -> None:
    audit = case.audit
    current_prompt = recognition.exact_prompt_serialization(case.system_prompt, case.user_prompt)
    normalized_prompt = normalized_text(current_prompt)
    collisions = audit["target_ground_truth_independent_historical_collision"]
    target_fields_absent_now = all(
        normalized_text(value) not in normalized_prompt or collisions.get(field, False)
        for field, value in case.forbidden_target_texts.items()
        if normalized_text(value)
    )
    excluded_ids_absent_now = all(
        recognition.run_token_pattern(run).search(current_prompt) is None
        for run in case.exclude_runs
    )
    source_paths = [case.target_evidence_source] + [
        path for paths in case.context_source_paths.values() for path in paths
    ]
    source_metadata_absent_now = all(
        path not in current_prompt and Path(path).name not in current_prompt
        for path in source_paths
    ) and all(token not in current_prompt for token in ("/afs/", "/eos/"))
    checks = [
        audit["exact_serialized_prompt_inspected"],
        audit["prompt_only_allowlisted_components"],
        audit["target_identifier_masked"],
        audit["target_kb_entry_absent"],
        audit["required_family_entries_absent"],
        audit["target_source_path_and_filename_absent"],
        all(audit["excluded_run_identifiers_absent"].values()),
        all(audit["target_ground_truth_fields_absent"].values()),
        target_fields_absent_now,
        excluded_ids_absent_now,
        source_metadata_absent_now,
        current_prompt == case.serialized_prompt,
        recognition.sha256_text(case.serialized_prompt) == case.prompt_sha256,
    ]
    if case.context_mode == "baseline":
        checks.append(all(audit["direct_context_not_added"].values()))
    else:
        checks.extend(
            [
                audit["no_elog_or_provenance_text_present"],
                audit["context_summaries_compact"],
                set(audit["context_sources_included"]) == {"trigger", "lvds", "daq_config"},
            ]
        )
    if not all(checks):
        raise AssertionError(f"anti-leakage audit failed for target {case.target_run}: {audit}")


def prepare_case(
    manifest: dict[str, Any],
    target_run: int,
    kb_entries: list[dict[str, Any]],
    snapshot_loader: Callable[[str, int], str] = _historical_snapshot,
    context_mode: str = "baseline",
) -> PreparedNovelCase:
    exclusions = list(manifest["targets"][target_run]["exclude_runs"])
    target_entry, filtered_original = split_kb(kb_entries, target_run, exclusions)
    visible_runs = [recognition.singleton_run(entry) for entry in filtered_original]
    if context_mode == "full":
        filtered, provenance_redactions = sanitize_contextual_kb(filtered_original)
    else:
        filtered, provenance_redactions = filtered_original, 0

    target_source = evidence_path(manifest, target_run)
    if not target_source.is_file():
        raise FileNotFoundError(f"target evidence does not exist: {target_source}")
    target_snapshot = snapshot_loader(str(target_source), target_run)

    if context_mode == "full":
        context_bundle = contextual.build_context_bundle(manifest, target_run, REPO_ROOT)
    else:
        context_bundle = contextual.ContextBundle(
            trigger_summary="",
            lvds_summary="",
            daq_config_summary="",
            availability={},
            source_paths={},
            source_types={},
        )

    historical_sources: list[str] = []
    historical_blocks: list[str] = []
    for entry in filtered:
        historical_run = recognition.singleton_run(entry)
        source = evidence_path(manifest, historical_run)
        historical_sources.append(str(source))
        snapshot = (
            snapshot_loader(str(source), historical_run)
            if source.is_file()
            else "  (frozen AutoDQM anomaly snapshot unavailable)"
        )
        historical_blocks.append(
            _format_historical_case(entry, snapshot)
        )

    if context_mode == "full":
        user_prompt = (
            "CURRENT AUTODQM ANOMALY EVIDENCE\n"
            "Case ID: CASE_TARGET\n"
            + target_snapshot
            + "\n\nTRIGGER CONTEXT\n"
            + context_bundle.trigger_summary
            + "\n\nLVDS CONTEXT\n"
            + context_bundle.lvds_summary
            + "\n\nDAQ / CONFIG CONTEXT\n"
            + context_bundle.daq_config_summary
            + "\n\nHISTORICAL CASES\n"
            + "\n\n".join(historical_blocks)
            + NOVEL_TASK
        )
    else:
        user_prompt = (
            "## Current test case\n\n"
            "Case ID: CASE_TARGET\n"
            "Detector evidence (production run-level anomaly snapshot):\n"
            + target_snapshot
            + "\n\n---\n\n## Historical reference cases\n\n"
            + "\n\n".join(historical_blocks)
            + NOVEL_TASK
        )
    system_prompt = recognition.run_token_pattern(target_run).sub(
        "CASE_TARGET", PRODUCTION_SYSTEM_PROMPT
    )
    user_prompt = recognition.run_token_pattern(target_run).sub("CASE_TARGET", user_prompt)
    serialized = recognition.exact_prompt_serialization(system_prompt, user_prompt)
    audit = build_audit(
        target_run,
        exclusions,
        target_entry,
        filtered,
        system_prompt,
        user_prompt,
        serialized,
        target_source,
        context_mode,
        context_bundle.source_paths,
        context_bundle.availability,
        {
            "trigger": context_bundle.trigger_summary,
            "lvds": context_bundle.lvds_summary,
            "daq_config": context_bundle.daq_config_summary,
        },
        provenance_redactions,
    )
    case = PreparedNovelCase(
        target_run=target_run,
        context_mode=context_mode,
        exclude_runs=exclusions,
        filtered_kb=filtered,
        visible_historical_runs=visible_runs,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        serialized_prompt=serialized,
        prompt_sha256=recognition.sha256_text(serialized),
        target_evidence_source=str(target_source),
        historical_evidence_sources=historical_sources,
        context_source_paths=context_bundle.source_paths,
        anomaly_summary=recognition.run_token_pattern(target_run).sub(
            "CASE_TARGET", target_snapshot
        ),
        trigger_summary=recognition.run_token_pattern(target_run).sub(
            "CASE_TARGET", context_bundle.trigger_summary
        ),
        lvds_summary=recognition.run_token_pattern(target_run).sub(
            "CASE_TARGET", context_bundle.lvds_summary
        ),
        daq_config_summary=recognition.run_token_pattern(target_run).sub(
            "CASE_TARGET", context_bundle.daq_config_summary
        ),
        context_availability=context_bundle.availability,
        forbidden_target_texts={
            field: str(target_entry.get(field, ""))
            for field in ("category", "cause", "action", "recovery")
        },
        audit=audit,
    )
    assert_case_safe(case)
    return case


def prepare_all_cases(
    manifest: dict[str, Any], context_mode: str = "baseline"
) -> tuple[list[PreparedNovelCase], Path, str]:
    kb_path = resolve_path(manifest["production_kb"])
    if not kb_path.is_file():
        raise FileNotFoundError(f"production KB does not exist: {kb_path}")
    entries = recognition.load_kb(kb_path)
    cache: dict[tuple[str, int], str] = {}

    def cached_snapshot(path: str, run: int) -> str:
        key = (path, run)
        if key not in cache:
            cache[key] = _historical_snapshot(path, run)
        return cache[key]

    cases = [
        prepare_case(manifest, run, entries, cached_snapshot, context_mode=context_mode)
        for run in EXPECTED_TARGETS
    ]
    return cases, kb_path, recognition.sha256_file(kb_path)


def parse_response_text(raw_text: str) -> NovelResponse:
    text = raw_text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ResponseParsingError(f"response is not valid JSON: {exc}", raw_text) from exc
    try:
        return NovelResponse.model_validate(payload)
    except ValidationError as exc:
        raise ResponseParsingError(f"response does not match novel schema: {exc}", raw_text) from exc


def validate_prediction(case: PreparedNovelCase, parsed: NovelResponse) -> None:
    invalid = set(parsed.supporting_historical_runs) - set(case.visible_historical_runs)
    if invalid:
        raise ResponseParsingError(
            f"supporting_historical_runs contains non-visible runs: {sorted(invalid)}"
        )


def openai_call(system_prompt: str, user_prompt: str, model: str) -> tuple[Any, NovelResponse]:
    from openai import OpenAI

    response = OpenAI().responses.create(
        model=model,
        instructions=system_prompt,
        input=user_prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": "autoflame_novel_failure_response",
                "schema": NovelResponse.model_json_schema(),
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


def make_result_dir(prefix: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(__file__).with_name("results") / f"{prefix}_{stamp}"


def initialise_result_dir(result_dir: Path) -> None:
    for name in ("prompts", "contexts", "responses", "parsed", "metadata"):
        (result_dir / name).mkdir(parents=True, exist_ok=True)


def save_preflight(case: PreparedNovelCase, result_dir: Path) -> None:
    (result_dir / "prompts" / f"target_{case.target_run}.txt").write_text(
        case.serialized_prompt + "\n", encoding="utf-8"
    )
    (result_dir / "contexts" / f"target_{case.target_run}_kb.yaml").write_text(
        yaml.safe_dump(case.filtered_kb, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    if case.context_mode == "full":
        context_files = {
            "anomaly": case.anomaly_summary,
            "trigger": case.trigger_summary,
            "lvds": case.lvds_summary,
            "daq_config": case.daq_config_summary,
        }
        for name, content in context_files.items():
            (result_dir / "contexts" / f"target_{case.target_run}_{name}.txt").write_text(
                content.rstrip() + "\n", encoding="utf-8"
            )
    recognition.write_json(
        result_dir / "metadata" / f"target_{case.target_run}_preflight.json",
        {
            **case.audit,
            "target_evidence_source": case.target_evidence_source,
            "historical_evidence_sources": case.historical_evidence_sources,
            "context_source_paths": case.context_source_paths,
            "context_source_availability": case.context_availability,
            "evidence_source_type": "frozen_campaign_per_run_autodqm_anomaly_log",
        },
    )


def resolve_model(alias: str) -> str:
    env_name = MODEL_ALIAS_ENV[alias]
    model = os.environ.get(env_name)
    if not model:
        raise ValueError(f"--model-alias {alias} requires environment variable {env_name}")
    return model


def completed_record(
    case: PreparedNovelCase, parsed: NovelResponse, metadata: dict[str, Any]
) -> dict[str, Any]:
    return {
        "target_run": case.target_run,
        "exclude_runs": case.exclude_runs,
        "status": "completed",
        "prediction": parsed.model_dump(mode="json"),
        "prompt_sha256": case.prompt_sha256,
        "metadata": metadata,
    }


def failure_record(
    case: PreparedNovelCase, error: Exception, status: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    return {
        "target_run": case.target_run,
        "exclude_runs": case.exclude_runs,
        "status": status,
        "error": f"{type(error).__name__}: {recognition.redact_secrets(error)}",
        "prompt_sha256": case.prompt_sha256,
        "metadata": metadata,
    }


def prediction_yaml(records_by_run: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    if set(records_by_run) != set(EXPECTED_TARGETS):
        raise ValueError("novel_predictions.yaml requires exactly six target records")
    output = []
    for run in EXPECTED_TARGETS:
        record = records_by_run[run]
        if record.get("status") != "completed":
            raise ValueError("novel_predictions.yaml requires six completed predictions")
        prediction = record["prediction"]
        output.append(
            {
                "run": run,
                "category": prediction["category"],
                "cause": prediction["cause"],
                "action": prediction["action"],
            }
        )
    return output


def render_report(
    records_by_run: dict[int, dict[str, Any]], model_label: str
) -> str:
    lines = [f"# Novel Test — {model_label}", ""]
    for run in EXPECTED_TARGETS:
        lines.extend([f"## Run {run}"])
        record = records_by_run.get(run)
        if not record or record.get("status") != "completed":
            status = record.get("status", "not run") if record else "not run"
            lines.extend([f"Status: {status}", ""])
            continue
        prediction = record["prediction"]
        historical = prediction["supporting_historical_runs"]
        lines.extend(
            [
                f"Category: {prediction['category']}",
                f"Cause: {recognition.markdown_value(prediction['cause'])}",
                f"Action: {recognition.markdown_value(prediction['action'])}",
                f"Confidence: {prediction['confidence']}",
                "Historical cases used: " + (", ".join(map(str, historical)) if historical else "none"),
                f"Reasoning summary: {recognition.markdown_value(prediction['reasoning_summary'])}",
                "",
            ]
        )
    return "\n".join(lines)


def write_outputs(
    result_dir: Path,
    records_by_run: dict[int, dict[str, Any]],
    model_label: str,
) -> None:
    ordered = [records_by_run[run] for run in EXPECTED_TARGETS if run in records_by_run]
    recognition.write_json(
        result_dir / "results.json",
        {
            "summary": {
                "completed": sum(item.get("status") == "completed" for item in ordered),
                "total": len(EXPECTED_TARGETS),
                "scoring_performed": False,
            },
            "tests": ordered,
        },
    )
    (result_dir / "report.md").write_text(
        render_report(records_by_run, model_label), encoding="utf-8"
    )
    predictions_path = result_dir / "novel_predictions.yaml"
    if len(ordered) == len(EXPECTED_TARGETS) and all(
        item.get("status") == "completed" for item in ordered
    ):
        predictions_path.write_text(
            yaml.safe_dump(
                prediction_yaml(records_by_run), sort_keys=False, allow_unicode=True, width=100
            ),
            encoding="utf-8",
        )
    elif predictions_path.exists():
        predictions_path.unlink()


def dry_run(result_dir: Path | None = None, context_mode: str = "baseline") -> Path:
    manifest_file = manifest_path_for(context_mode)
    manifest = load_manifest(manifest_file, context_mode=context_mode)
    cases, kb_path, kb_hash = prepare_all_cases(manifest, context_mode=context_mode)
    prefix = "dry_run_context" if context_mode == "full" else "dry_run"
    output = result_dir or make_result_dir(prefix)
    initialise_result_dir(output)
    for case in cases:
        assert_case_safe(case)
        save_preflight(case, output)
    recognition.write_json(
        output / "run_config.json",
        {
            "mode": "dry-run",
            "context_mode": context_mode,
            "benchmark_id": manifest["benchmark_id"],
            "created_at": recognition.utc_now(),
            "target_runs": EXPECTED_TARGETS,
            "production_kb": str(kb_path),
            "kb_sha256": kb_hash,
            "manifest_sha256": recognition.sha256_file(manifest_file),
            "prompt_sha256": {str(case.target_run): case.prompt_sha256 for case in cases},
            "context_source_availability": {
                str(case.target_run): case.context_availability for case in cases
            },
            "api_calls": 0,
            "git": recognition.git_metadata(),
        },
    )
    records = {
        case.target_run: {
            "target_run": case.target_run,
            "exclude_runs": case.exclude_runs,
            "status": "preflight_passed",
            "prompt_sha256": case.prompt_sha256,
        }
        for case in cases
    }
    recognition.write_json(
        output / "results.json",
        {"summary": {"preflight_passed": len(cases), "api_calls": 0}, "tests": list(records.values())},
    )
    (output / "report.md").write_text(render_report(records, "dry-run"), encoding="utf-8")
    print(f"Dry-run: {len(cases)}/{len(EXPECTED_TARGETS)} PASS; API calls: 0; results: {output}")
    return output


def run_benchmark(
    model: str,
    model_alias: str,
    result_dir: Path,
    force: bool = False,
    api_call: Callable[[str, str, str], tuple[Any, NovelResponse]] = openai_call,
    sleep_fn: Callable[[float], None] = time.sleep,
    context_mode: str = "baseline",
) -> Path:
    if api_call is openai_call and not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set")
    manifest_file = manifest_path_for(context_mode)
    manifest = load_manifest(manifest_file, context_mode=context_mode)
    cases, kb_path, kb_hash = prepare_all_cases(manifest, context_mode=context_mode)
    initialise_result_dir(result_dir)
    manifest_hash = recognition.sha256_file(manifest_file)
    config_path = result_dir / "run_config.json"
    current_prompt_hashes = {str(case.target_run): case.prompt_sha256 for case in cases}
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if (
            config.get("mode") != "run"
            or config.get("model_id") != model
            or config.get("model_alias") != model_alias
            or config.get("context_mode", "baseline") != context_mode
        ):
            raise ValueError("result directory belongs to a different run or model ID")
        if config.get("kb_sha256") != kb_hash or config.get("manifest_sha256") != manifest_hash:
            raise ValueError("KB or manifest changed since this result directory was created")
        if config.get("prompt_sha256") != current_prompt_hashes:
            raise ValueError("model-visible prompts changed since this result directory was created")
    else:
        recognition.write_json(
            config_path,
            {
                "mode": "run",
                "context_mode": context_mode,
                "benchmark_id": manifest["benchmark_id"],
                "created_at": recognition.utc_now(),
                "model_id": model,
                "model_alias": model_alias,
                "target_runs": EXPECTED_TARGETS,
                "production_kb": str(kb_path),
                "kb_sha256": kb_hash,
                "manifest_sha256": manifest_hash,
                "prompt_sha256": current_prompt_hashes,
                "git": recognition.git_metadata(),
            },
        )

    records_by_run: dict[int, dict[str, Any]] = {}
    results_path = result_dir / "results.json"
    if results_path.exists():
        prior = json.loads(results_path.read_text(encoding="utf-8"))
        records_by_run = {int(item["target_run"]): item for item in prior.get("tests", [])}

    git_info = recognition.git_metadata()
    for case in cases:
        assert_case_safe(case)
        save_preflight(case, result_dir)
        previous = records_by_run.get(case.target_run)
        if previous and previous.get("status") == "completed" and not force:
            print(f"Skipping completed target {case.target_run}")
            continue
        base_metadata = {
            "model_id": model,
            "model_alias": model_alias,
            "context_mode": context_mode,
            "target_test_id": case.target_run,
            "excluded_runs": case.exclude_runs,
            "timestamp": recognition.utc_now(),
            "sanitized_prompt_sha256": case.prompt_sha256,
            "kb_sha256": kb_hash,
            "detector_evidence_source_files": [case.target_evidence_source]
            + case.historical_evidence_sources
            + [path for paths in case.context_source_paths.values() for path in paths],
            "context_source_availability": case.context_availability,
            "benchmark_code_git_commit": git_info.get("commit"),
            "git_dirty": git_info.get("dirty"),
        }

        def checked_call(system: str, user: str, selected_model: str) -> tuple[Any, NovelResponse]:
            assert_case_safe(case)
            raw, parsed = api_call(system, user, selected_model)
            validate_prediction(case, parsed)
            return raw, parsed

        try:
            parsed, raw, retry_count, latency = recognition.call_with_retries(
                case,
                model,
                result_dir / "responses",
                checked_call,
                sleep_fn=sleep_fn,
                metadata_dir=result_dir / "metadata",
                call_metadata=base_metadata,
            )
            metadata = {
                **base_metadata,
                "response_latency_seconds": latency,
                "token_usage": recognition.token_usage(raw),
                "api_error_retry_count": retry_count,
            }
            recognition.write_json(
                result_dir / "parsed" / f"target_{case.target_run}.json",
                parsed.model_dump(mode="json"),
            )
            recognition.write_json(
                result_dir / "metadata" / f"target_{case.target_run}_call.json", metadata
            )
            records_by_run[case.target_run] = completed_record(case, parsed, metadata)
        except recognition.ApiCallFailure as exc:
            metadata = {**base_metadata, "api_error_retry_count": exc.attempts - 1}
            records_by_run[case.target_run] = failure_record(case, exc, exc.kind, metadata)
        write_outputs(result_dir, records_by_run, model_alias)

    write_outputs(result_dir, records_by_run, model_alias)
    return result_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    dry = subparsers.add_parser("dry-run", help="prepare and audit six prompts without API calls")
    dry.add_argument("--result-dir", type=Path)
    dry.add_argument("--context-mode", choices=CONTEXT_MODES, default="baseline")
    run = subparsers.add_parser("run", help="run or resume one model")
    run.add_argument("--model-alias", choices=sorted(MODEL_ALIAS_ENV), required=True)
    run.add_argument("--result-dir", type=Path)
    run.add_argument("--force", action="store_true")
    run.add_argument("--context-mode", choices=CONTEXT_MODES, default="baseline")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "dry-run":
            dry_run(args.result_dir, context_mode=args.context_mode)
        else:
            model = resolve_model(args.model_alias)
            prefix = (
                f"{args.model_alias}_context"
                if args.context_mode == "full"
                else args.model_alias
            )
            output = args.result_dir or make_result_dir(prefix)
            print(f"Running model alias {args.model_alias}; results: {output}")
            run_benchmark(
                model,
                args.model_alias,
                output,
                force=args.force,
                context_mode=args.context_mode,
            )
        return 0
    except Exception as exc:
        print(f"ERROR: {recognition.redact_secrets(exc)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
