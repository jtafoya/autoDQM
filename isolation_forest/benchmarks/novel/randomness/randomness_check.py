#!/usr/bin/env python3
"""Phase 1 only: repeat the unchanged added-context novel request (Sol only)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
import uuid
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import novel_test as novel

REFERENCE = HERE.parent / "results/sol_context_20260827T170906Z/run_config.json"
SAMPLING_KEYS = (
    "temperature", "top_p", "seed", "max_output_tokens", "reasoning",
    "frequency_penalty", "presence_penalty", "service_tier", "truncation",
    "prompt_cache_key", "prompt_cache_retention",
)
SOURCE_FILES = (
    "benchmarks/novel/novel_test.py", "benchmarks/novel/context_builders.py",
    "benchmarks/novel/novel_manifest.yaml", "benchmarks/novel/context_manifest.yaml",
    "benchmarks/recognition/recognition_test.py", "src/llm.py", "src/features.py",
    "src/run_config.py", "src/kb_schema.py", "src/run_list.py",
)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def code_hashes():
    return {name: novel.recognition.sha256_file(novel.REPO_ROOT / name) for name in SOURCE_FILES}


def load_reference(model):
    reference = read_json(REFERENCE)
    if (reference.get("context_mode") != "full" or reference.get("model_alias") != "sol"
            or reference.get("model_id") != model
            or reference.get("target_runs") != novel.EXPECTED_TARGETS):
        raise ValueError("model or reference is not the original six-run Sol added-context study")
    return reference


@lru_cache(maxsize=256)
def _snapshot_by_content(path, run, file_sha256):
    # Input-only memoization, like prepare_all_cases(), with content invalidation.
    # Never stores, loads, or reuses an LLM response.
    return novel._historical_snapshot(path, run)


def snapshot_loader(path, run):
    return _snapshot_by_content(path, run, novel.recognition.sha256_file(Path(path)))


def load_case(run, reference):
    # Both existing manifests are authoritative; only the full manifest builds input.
    novel.load_manifest(context_mode="baseline")
    manifest = novel.load_manifest(context_mode="full")
    kb_path = novel.resolve_path(manifest["production_kb"])
    if novel.recognition.sha256_file(kb_path) != reference["kb_sha256"]:
        raise ValueError("KB changed from the original added-context study")
    if novel.recognition.sha256_file(novel.CONTEXT_MANIFEST_PATH) != reference["manifest_sha256"]:
        raise ValueError("context manifest changed from the original added-context study")
    case = novel.prepare_case(manifest, run, novel.recognition.load_kb(kb_path),
                              snapshot_loader=snapshot_loader, context_mode="full")
    novel.assert_case_safe(case)
    if case.prompt_sha256 != reference["prompt_sha256"][str(run)]:
        raise ValueError(f"run {run}: prompt differs from the original added-context study")
    return case


def components(case, model):
    context = {"trigger": case.trigger_summary, "lvds": case.lvds_summary,
               "daq_config": case.daq_config_summary}
    return {
        "prompt_sha256": case.prompt_sha256,
        "filtered_kb_sha256": digest(case.filtered_kb),
        "context_sha256": digest(context),
        "anomaly_sha256": novel.recognition.sha256_text(case.anomaly_summary),
        "model_id": model, "model_id_sha256": novel.recognition.sha256_text(model),
    }


class CapturedWithoutNetwork(BaseException):
    """Escape the SDK's Exception retry wrapper before any network access."""


class InputChanged(BaseException):
    """Stop before sending a different request; do not let the SDK retry it."""


def invoke(case, model, directory, *, execute=False, expected=None, transport=None):
    """Call the ORIGINAL adapter; observe the exact SDK request/response bytes.

    A scoped client injection adds recording hooks, not prompt/schema/request logic.
    Dry-run uses MockTransport and cannot reach the network. Transport injection is
    also used by the offline tests; the CLI never supplies it for paid execution.
    """
    import httpx
    import openai

    directory.mkdir(parents=True, exist_ok=False)
    context = {"trigger": case.trigger_summary, "lvds": case.lvds_summary,
               "daq_config": case.daq_config_summary}
    write_json(directory / "filtered_kb.json", case.filtered_kb)
    write_json(directory / "context.json", context)
    write_json(directory / "audit.json", case.audit)
    (directory / "prompt.txt").write_text(case.serialized_prompt, encoding="utf-8")
    record = {
        "run": case.target_run, "model_alias": "sol", "context_mode": "full",
        "trial": int(directory.name.removeprefix("trial_")) if directory.name.startswith("trial_") else None,
        "timestamp": novel.recognition.utc_now(), "status": "preparing",
        **components(case, model), "network_attempts": 0,
        "automatic_retries": 0, "sdk_version": openai.__version__,
        "request_matches_reference": False,
    }
    captured = []

    def request_hook(request):
        novel.assert_case_safe(case)
        body = request.read()
        payload = json.loads(body)
        if captured:
            raise InputChanged("more than one HTTP request attempted in one trial")
        captured.append(payload)
        (directory / "request_body.json").write_bytes(body)
        write_json(directory / "request_payload.json", payload)
        record.update(
            input_sha256=digest(payload),
            request_body_sha256=hashlib.sha256(body).hexdigest(),
            sampling_parameters={key: {"sent": key in payload, "value": payload.get(key)}
                                 for key in SAMPLING_KEYS},
            request_keys=sorted(payload),
            endpoint=str(request.url.copy_with(query=None)),
        )
        if request.method != "POST" or not request.url.path.endswith("/responses"):
            raise InputChanged("unexpected API method or endpoint")
        if (payload.get("instructions") != case.system_prompt
                or payload.get("input") != case.user_prompt or payload.get("model") != model):
            raise InputChanged("wire payload does not match the prepared novel case")
        if expected is not None:
            keys = (*components(case, model), "input_sha256", "request_body_sha256", "endpoint")
            changed = [key for key in keys if record.get(key) != expected.get(key)]
            if changed:
                raise InputChanged("effective input changed: " + ", ".join(changed))
        record["request_matches_reference"] = True
        record["status"] = "request_prepared"
        if execute:
            record["network_attempts"] = 1
        write_json(directory / "metadata.json", record)

    def response_hook(response):
        # Save even refusals, invalid structured JSON, and HTTP error bodies.
        body = response.read()
        (directory / "raw_response_body.bin").write_bytes(body)
        record.update(http_status=response.status_code, request_id=response.headers.get("x-request-id"))
        try:
            write_json(directory / "raw_response.json", json.loads(body))
        except (ValueError, UnicodeDecodeError):
            pass  # The complete original bytes remain available.

    def stop_before_network(request):
        raise CapturedWithoutNetwork()

    http_options = {"event_hooks": {"request": [request_hook], "response": [response_hook]}}
    if not execute:
        http_options["transport"] = httpx.MockTransport(stop_before_network)
    elif transport is not None:
        http_options["transport"] = transport
    client_options = {"max_retries": 0, "http_client": openai.DefaultHttpxClient(**http_options)}
    if not execute:
        client_options["api_key"] = "offline-placeholder-not-a-real-key"
    started = time.monotonic()
    try:
        with openai.OpenAI(**client_options) as client:
            with patch("openai.OpenAI", return_value=client):
                raw, parsed = novel.openai_call(case.system_prompt, case.user_prompt, model)
            write_json(directory / "sdk_response.json", novel.recognition.raw_response_payload(raw))
            (directory / "output_text.txt").write_text(raw.output_text, encoding="utf-8")
            write_json(directory / "parsed_response.json", parsed.model_dump(mode="json"))
            novel.validate_prediction(case, parsed)
            record.update(status="completed", prediction=parsed.model_dump(mode="json"),
                          response_model_id=getattr(raw, "model", None),
                          response_id=getattr(raw, "id", None), token_usage=novel.recognition.token_usage(raw))
    except CapturedWithoutNetwork:
        record["status"] = "dry_run"
    except InputChanged as exc:
        record.update(status="input_changed", request_matches_reference=False, error=str(exc))
    except KeyboardInterrupt:
        record["status"] = "interrupted"
        raise
    except Exception as exc:
        record.update(status="failed", error=novel.recognition.redact_secrets(exc), error_type=type(exc).__name__)
        raw = getattr(exc, "raw_response", None)
        if raw is not None:
            write_json(directory / "sdk_response.json", novel.recognition.raw_response_payload(raw))
            text = getattr(raw, "output_text", None)
            if text is not None:
                (directory / "output_text.txt").write_text(text, encoding="utf-8")
    finally:
        record["latency_seconds"] = time.monotonic() - started
        write_json(directory / "metadata.json", record)
    return record


def md(value):
    import html
    return html.escape(str(value)).replace("|", "&#124;").replace("\r", "").replace("\n", "<br>")


def summarize(output, records, trials, model):
    lines = ["# Sol added-context randomness check", "",
             f"Model: `{model}`. Planned: 6 × {trials} = {6 * trials} fresh requests.",
             f"HTTP attempts: {sum(r.get('network_attempts', 0) for r in records)}; "
             f"completed: {sum(r['status'] == 'completed' for r in records)}.",
             "Sampling parameters remain exactly as emitted by the existing adapter. "
             "Current adapter omits temperature, top_p, seed, reasoning effort and output-token limits; "
             "omitted means provider default, not zero or a fixed seed.",
             "`category`, `cause`, and `action` are free text, with no discrete diagnosis enum. "
             "No dominant semantic diagnosis or consistency rate is inferred. Exact string variation "
             "is not evidence of different physical diagnoses. Review the full strings below.", "",
             "| Run | " + " | ".join(f"Trial {i}" for i in range(1, trials + 1))
             + " | Exact unique causes | Exact unique actions | Exact unique structured outputs | Input hashes |",
             "|---|" + "---|" * (trials + 4)]
    rows = []
    for run in novel.EXPECTED_TARGETS:
        by_trial = {r["trial"]: r for r in records if r["run"] == run}
        ordered = [by_trial.get(i, {}) for i in range(1, trials + 1)]
        complete = [r for r in ordered if r.get("status") == "completed"]
        hashes = [r.get("input_sha256") for r in ordered]
        matched = (all(hashes) and len(set(hashes)) == 1
                   and all(r.get("request_matches_reference") for r in ordered))
        cells = []
        for i, r in enumerate(ordered, 1):
            p = r.get("prediction")
            if p is None:
                cells.append(md(r.get("status", "not run")))
            else:
                cells.append("Category: " + md(p["category"]) + "<br>Cause: " + md(p["cause"])
                             + "<br>Action: " + md(p["action"])
                             + f"<br>[parsed](run{run}/trial_{i}/parsed_response.json)"
                             + f" · [raw](run{run}/trial_{i}/raw_response_body.bin)")
        unique = lambda field: len({r["prediction"][field] for r in complete}) if complete else None
        full_unique = len({canonical(r["prediction"]) for r in complete}) if complete else None
        row = {"run": run, "completed_trials": len(complete), "planned_trials": trials,
               "n_unique_exact_diagnoses": unique("cause"), "n_unique_exact_actions": unique("action"),
               "n_unique_exact_categories": unique("category"), "n_unique_exact_outputs": full_unique,
               "all_input_hashes_match": bool(matched), "model_id": model,
               "sampling_parameters": canonical(next((r["sampling_parameters"] for r in ordered
                                                        if "sampling_parameters" in r), {})),
               "dominant_diagnosis": "", "dominant_count": "", "consistency_rate": ""}
        for i, r in enumerate(ordered, 1):
            row[f"trial_{i}_status"] = r.get("status", "not run")
            row[f"trial_{i}_input_sha256"] = r.get("input_sha256", "")
            for field in ("category", "cause", "action"):
                row[f"trial_{i}_{field}"] = r.get("prediction", {}).get(field, "")
        rows.append(row)
        counts = [unique("cause"), unique("action"), full_unique]
        lines.append(f"| {run} | " + " | ".join(cells)
                     + " | " + " | ".join("—" if n is None else str(n) for n in counts)
                     + " | " + ("MATCH" if matched else "INCOMPLETE / MISMATCH") + " |")
    lines.extend(["", "Counts use completed trials only; failures are not diagnoses. "
                  "A full study requires every trial completed and every run's hashes matched. "
                  "Dry-run contains no model output and supports no diagnosis conclusion.",
                  "`input_sha256` hashes the complete canonical JSON request including model and schema. "
                  "Per-trial metadata also records exact wire-body, prompt, filtered KB and context hashes.", ""])
    (output / "randomness_summary.md").write_text("\n".join(lines), encoding="utf-8")
    with (output / "randomness_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_json(output / "results.json", {"trials": records, "runs": rows})


def run_study(model, output, trials=5, execute=False):
    if trials != 5:
        raise ValueError("Phase 1 requires exactly five trials per run")
    if execute and not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is not set; no calls made")
    reference = load_reference(model)
    output = output.resolve()
    if HERE not in output.parents:
        raise ValueError("all output must be in a new subdirectory of benchmarks/novel/randomness")
    output.mkdir(parents=True, exist_ok=False)  # Never resume/overwrite/reuse prior outputs.
    fingerprints = code_hashes()
    config = {"mode": "execute" if execute else "dry-run", "model_alias": "sol", "model_id": model,
              "created_at": novel.recognition.utc_now(), "trials": trials,
              "target_runs": novel.EXPECTED_TARGETS, "planned_api_calls": 30 if execute else 0,
              "reference": str(REFERENCE), "reference_sha256": novel.recognition.sha256_file(REFERENCE),
              "source_sha256": fingerprints, "git": novel.recognition.git_metadata(),
              "input_cache": "in-memory anomaly summaries keyed by source-file SHA256; no response cache",
              "retry_policy": "one attempt per trial; no SDK or benchmark retries", "status": "preflight"}
    write_json(output / "study_config.json", config)
    records = []
    try:
        # Audit all six inputs against the prior Sol study before the first paid call.
        expected = {}
        for run in novel.EXPECTED_TARGETS:
            case = load_case(run, reference)
            expected[run] = invoke(case, model, output / "preflight" / f"run{run}")
            if expected[run]["status"] != "dry_run":
                raise ValueError(f"run {run}: offline request preflight failed")
        for run in novel.EXPECTED_TARGETS:
            for trial in range(1, trials + 1):
                if code_hashes() != fingerprints:
                    raise ValueError("source code or manifest changed during the study")
                case = load_case(run, reference)  # Rebuild using the existing functions for EVERY trial.
                record = invoke(case, model, output / f"run{run}" / f"trial_{trial}",
                                execute=execute, expected=expected[run])
                record["trial"] = trial
                write_json(output / f"run{run}" / f"trial_{trial}" / "metadata.json", record)
                records.append(record)
                summarize(output, records, trials, model)
                print(f"run {run} trial {trial}: {record['status']}", flush=True)
                if record["status"] == "input_changed":
                    raise ValueError("input mismatch: study stopped before sending changed request")
        wanted = "completed" if execute else "dry_run"
        ok = len(records) == 30 and all(r["status"] == wanted for r in records)
        config["status"] = "completed" if ok and execute else "dry_run_passed" if ok else "incomplete"
        return 0 if ok else 1
    except (Exception, KeyboardInterrupt) as exc:
        config.update(status="aborted", error=novel.recognition.redact_secrets(exc))
        raise
    finally:
        # Include a request that was interrupted after sending but before returning.
        persisted = []
        for run in novel.EXPECTED_TARGETS:
            for trial in range(1, trials + 1):
                path = output / f"run{run}" / f"trial_{trial}" / "metadata.json"
                if path.is_file():
                    persisted.append(read_json(path))
        records = persisted
        config.update(finished_at=novel.recognition.utc_now(),
                      network_attempts=sum(r.get("network_attempts", 0) for r in records))
        write_json(output / "study_config.json", config)
        summarize(output, records, trials, model)
        print(f"Results: {output}", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-alias", choices=["sol"], default="sol")
    parser.add_argument("--trials", type=int, choices=[5], default=5)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true", help="send 30 fresh API requests (paid)")
    mode.add_argument("--dry-run", action="store_true", help="offline request audit (default)")
    parser.add_argument("--result-dir", type=Path, help="new directory under randomness/; never overwritten")
    args = parser.parse_args(argv)
    try:
        model = novel.resolve_model(args.model_alias)
        stamp = novel.datetime.now(novel.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        label = "study" if args.execute else "dry_run"
        output = args.result_dir or HERE / f"{label}_{stamp}_{uuid.uuid4().hex[:8]}"
        return run_study(model, output, args.trials, args.execute)
    except Exception as exc:
        print(f"ERROR: {novel.recognition.redact_secrets(exc)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
