#!/usr/bin/env python3
"""Three independent, byte-identical requests per run; default is offline dry-run."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from common import HERE, RUNS, canonical, digest, sha, read, write, at_path, verify_files, source_hashes


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Citation(Strict):
    evidence_id: str
    field: str
    value_json: str


class Signature(Strict):
    signature_id: str
    observation: str
    role: Literal['supports', 'contradicts', 'limitation']
    citations: list[Citation]
    cause_link: str
    action_link: str


class SemanticDescription(Strict):
    component: str
    failure_mechanism: str
    action_intent: str


class Diagnosis(Strict):
    category: str
    cause: str
    action: str
    confidence: float = Field(ge=0, le=1)
    supporting_historical_runs: list[int]
    reasoning_summary: str
    semantic_description: SemanticDescription
    signatures: list[Signature]
    missing_information: list[str]


TASK = '''
Diagnose CASE_TARGET using all the supplied evidence. Return category, cause and
action as before, plus a concise, auditable signature record. This is not a closed
failure taxonomy. Do not infer the answer from a run identifier or invent measurements.
Historical KB cases are filtered analogies, never observations of the target.
Raw-derived summaries cover all supplied files but are lossy, not original event rows.
No tool or raw-file access is available in this request. Use only the supplied records.

Identify the primary cause, distinguish mechanism from observable symptom, and
state unknown when the evidence is insufficient. Actions are proposed checks or
conditional fixes, not observed events. The schema requires numeric confidence 0..1
(overriding any earlier low/medium/high wording). semantic_description is a short,
free-text description of component, failure mechanism and action intent, not a
predefined label list. It aids later human comparison; there are no forced cause keys.

For every important signature you explicitly rely on, provide a signature_id,
observation, role (supports/contradicts/limitation), citations, cause_link and
action_link. Explain briefly what the observation supports or fails to distinguish.
These are concise evidence justifications, NOT hidden chain-of-thought or feature
importance. Include contrary evidence and unavailable discriminating information.
Each signature must cite at least one exact supplied evidence record. A citation
contains evidence_id, a dot-separated field path (array indices permitted), and
value_json: the exact JSON serialization of that field's supplied value. For example
field mean with value_json "1.25", or field text with value_json containing a JSON
quoted string. Never cite a field or value absent from the evidence. R/P records
are raw-derived observations; C may describe unavailable data; H is historical only.
Use separate signatures when observations or links differ; there is no required
fixed number. Only cite supporting_historical_runs that appear in H records.
Return only the requested structured JSON.
'''.strip()


def make_payload(run_dir, model):
    manifest = read(run_dir / 'manifest.json')
    verify_files(manifest['artifact_hashes'])
    header = read(run_dir / 'summary_header.json')
    user = ('CURRENT CASE: CASE_TARGET\nSUMMARY DEFINITIONS\n' + canonical(header)
            + '\nEVIDENCE RECORDS (JSONL)\n' + (run_dir / 'evidence.jsonl').read_text()
            + '\nTASK\n' + TASK)
    return {'model': model, 'instructions': manifest['production_system_prompt'],
            'input': user, 'truncation': 'disabled', 'store': False,
            'max_output_tokens': 24000, 'reasoning': {'effort': 'medium'},
            'text': {'format': {'type': 'json_schema', 'name': 'autoflame_raw_consistency',
                               'schema': Diagnosis.model_json_schema(), 'strict': True}}}


def token_check(payload, limit):
    # UTF-8 byte count is a conservative upper bound, not a token estimate.
    # Optional tokenizer never downloads data in this code path.
    size = len(canonical(payload).encode())
    return {'utf8_bytes_upper_bound_tokens': size, 'max_input_tokens_guard': limit,
            'within_conservative_guard': size <= limit,
            'note': 'Conservative bound, not exact tokenizer count. Refuse oversized input; never truncate.'}


def validate_citations(prediction, records, visible_runs):
    index = {r['id']: r for r in records}
    issues, checked = [], []
    ids = [s['signature_id'] for s in prediction['signatures']]
    if len(ids) != len(set(ids)): issues.append('duplicate signature_id')
    if not ids: issues.append('no signatures: no evidence explanation supplied')
    if not set(prediction['supporting_historical_runs']).issubset(set(visible_runs)):
        issues.append('supporting_historical_runs includes excluded or non-visible run')
    for s in prediction['signatures']:
        errors = []
        if not s['citations']: errors.append('no citations')
        for c in s['citations']:
            try:
                actual = at_path(index[c['evidence_id']], c['field'])
                cited = json.loads(c['value_json'])
                if canonical(cited) != canonical(actual):
                    # Permit JSON 1 vs 1.0 but no tolerance silently broadening the claim.
                    if type(cited) not in (int, float) or type(actual) not in (int, float) or cited != actual:
                        raise ValueError('cited value does not equal supplied value')
            except (KeyError, ValueError, IndexError, TypeError) as exc:
                errors.append(f'{c["evidence_id"]}:{c["field"]}: {exc}')
        checked.append({'signature_id': s['signature_id'], 'references_valid': not errors, 'errors': errors})
        issues.extend(f'{s["signature_id"]}: {e}' for e in errors)
    return {'all_references_valid': not issues, 'issues': issues, 'signatures': checked,
            'scope': 'Checks reference identity and values only. Does not verify that prose interpretation or causal conclusion is scientifically correct.'}


class StopOffline(BaseException): pass
class RequestChanged(BaseException): pass


def invoke(payload, directory, execute=False, transport=None, expected_wire=None):
    import httpx
    import openai
    directory.mkdir(parents=True, exist_ok=False)
    expected = digest(payload)
    metadata = {'status': 'preparing', 'input_sha256': expected, 'automatic_retries': 0,
                'network_attempts': 0, 'sdk_version': openai.__version__}
    started = time.monotonic()
    seen = []
    def request_hook(request):
        body = request.read()
        wire = json.loads(body)
        if seen or digest(wire) != expected or not request.url.path.endswith('/responses'):
            raise RequestChanged('Effective request differs from frozen request, or repeated attempt')
        if expected_wire is not None and hashlib.sha256(body).hexdigest() != expected_wire:
            raise RequestChanged('Wire bytes changed; stopped BEFORE network transmission')
        seen.append(1)
        (directory / 'request_body.json').write_bytes(body)
        metadata['request_body_sha256'] = hashlib.sha256(body).hexdigest()
        metadata['endpoint'] = str(request.url.copy_with(query=None))
        metadata['network_attempts'] = int(execute)
    def response_hook(response):
        body = response.read()
        (directory / 'raw_response_body.bin').write_bytes(body)
        metadata.update(http_status=response.status_code, request_id=response.headers.get('x-request-id'))
    def stop(request): raise StopOffline()
    opts = {'event_hooks': {'request': [request_hook], 'response': [response_hook]}}
    if not execute: opts['transport'] = httpx.MockTransport(stop)
    elif transport is not None: opts['transport'] = transport
    client_args = {'max_retries': 0, 'timeout': 1800, 'http_client': openai.DefaultHttpxClient(**opts)}
    if not execute: client_args['api_key'] = 'offline-placeholder'
    try:
        with openai.OpenAI(**client_args) as client:
            response = client.responses.create(**payload)
        write(directory / 'raw_response.json', response.model_dump(mode='json'))
        (directory / 'output_text.txt').write_text(response.output_text)
        metadata.update(response_id=response.id, response_model=response.model,
                        usage=response.usage.model_dump() if response.usage else None,
                        response_status=response.status)
        if response.status != 'completed': raise ValueError('Response incomplete or failed; retained without retry')
        result = Diagnosis.model_validate_json(response.output_text).model_dump(mode='json')
        write(directory / 'diagnosis.json', result)
        metadata['status'] = 'completed'
    except StopOffline:
        metadata['status'] = 'dry_run'
    except RequestChanged as exc:
        metadata.update(status='request_changed', error=str(exc))
    except Exception as exc:
        # Do not serialize exceptions containing request credentials/headers.
        metadata.update(status='failed', error_type=type(exc).__name__,
                        error='Request or response validation failed; inspect saved HTTP body locally.')
    finally:
        metadata['elapsed_seconds'] = time.monotonic() - started
        write(directory / 'metadata.json', metadata)
    return metadata


def normalize(text):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', text.casefold().replace('_', ' '))).strip()


def compare(study):
    config = read(study / 'study_config.json')
    review_path = study / 'semantic_review.json'
    review = read(review_path) if review_path.exists() else {'instructions':
        'Human semantic review only. Give trials with the same meaning the same group label for each field. Ignore wording/order; distinguish different primary mechanisms and incompatible actions. No ground truth or accuracy scoring. Populate reviewer and rationale. Do not overwrite diagnosis text.', 'runs': {}}
    comparison = []
    for run in config['runs']:
        trials = []
        for t in range(1, config['trials'] + 1):
            folder = study / f'run{run}' / f'trial_{t}'
            meta = read(folder / 'metadata.json') if (folder / 'metadata.json').exists() else {'status': 'not_started'}
            diagnosis = read(folder / 'diagnosis.json') if (folder / 'diagnosis.json').exists() else None
            trials.append({'trial': t, 'status': meta['status'], 'diagnosis': diagnosis,
                           'input_sha256': meta.get('input_sha256'), 'request_body_sha256': meta.get('request_body_sha256')})
        entry = review['runs'].setdefault(str(run), {'reviewer': '', 'rationale': '',
            'category_groups': ['', '', ''], 'cause_groups': ['', '', ''], 'action_groups': ['', '', '']})
        result = {'run': run, 'trials': trials, 'fields': {}}
        complete = all(t['status'] == 'completed' and t['diagnosis'] for t in trials)
        result['all_diagnoses_completed'] = bool(complete)
        result['identical_request_bytes'] = len({t['request_body_sha256'] for t in trials}) == 1 and all(t['request_body_sha256'] for t in trials)
        for field in ['category', 'cause', 'action']:
            texts = [t['diagnosis'][field] if t['diagnosis'] else None for t in trials]
            groups = entry.get(field + '_groups', [])
            reviewed = complete and entry.get('reviewer') and entry.get('rationale') and len(groups) == 3 and all(isinstance(x, str) and x.strip() for x in groups)
            result['fields'][field] = {'texts': texts,
                'normalized_wording_identical': complete and len({normalize(x) for x in texts}) == 1,
                'semantic_consistency': ('consistent' if len(set(g.strip() for g in groups)) == 1 else 'inconsistent') if reviewed else 'pending_human_review'}
        comparison.append(result)
    if not review_path.exists(): write(review_path, review)
    write(study / 'consistency.json', comparison)
    lines = ['# Semantic consistency review', '', 'Wording differences are NOT counted as diagnostic inconsistency. No accuracy/ground-truth score.',
             'Fill semantic_review.json and rerun --report-only to record a human semantic verdict.', '']
    for r in comparison:
        lines.extend([f'## Run {r["run"]}', '', f'Identical request bytes: {r["identical_request_bytes"]}', ''])
        for f, v in r['fields'].items():
            lines.extend([f'### {f}: {v["semantic_consistency"]}', ''])
            lines.extend(f'- Trial {i+1}: {text if text is not None else "NO COMPLETED DIAGNOSIS"}' for i, text in enumerate(v['texts']))
            lines.append('')
    (study / 'consistency.md').write_text('\n'.join(lines))
    return comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--model-alias', choices=['sol'], default='sol')
    parser.add_argument('--trials', type=int, choices=[3], default=3)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--max-input-tokens', type=int, default=900000,
                        help='Conservative UTF-8 byte upper-bound guard. Never silently truncate.')
    parser.add_argument('--report-only', type=Path)
    args = parser.parse_args()
    if args.report_only:
        if args.execute: parser.error('--report-only cannot be combined with --execute')
        compare(args.report_only.resolve())
        from render_signatures import render_study
        render_study(args.report_only.resolve())
        return
    if args.inputs is None: parser.error('--inputs must name the frozen bundle')
    if args.max_input_tokens <= 0 or args.max_input_tokens > 1_000_000:
        parser.error('Input guard must be 1..1000000; leave context space for output')
    bundle = args.inputs.resolve()
    config = read(bundle / 'bundle.json')
    if config['status'] != 'prepared': raise ValueError('Bundle not complete')
    if sorted(r['run'] for r in config['runs']) != RUNS: raise ValueError('Expected all six runs exactly once')
    model = os.environ.get('AUTOFLAME_SOL_MODEL', 'gpt-5.6-sol')
    if args.execute and not os.environ.get('OPENAI_API_KEY'): raise ValueError('Set OPENAI_API_KEY in your terminal; do not put it in files or command arguments')
    payloads, checks = {}, {}
    # Check EVERY case before the first paid request. No diagnosis or judge calls in preflight.
    for entry in config['runs']:
        run = entry['run']
        directory = bundle / f'run{run}'
        if sha(directory / 'manifest.json') != entry['manifest_sha256']: raise ValueError('Input manifest changed')
        payloads[run] = make_payload(directory, model)
        checks[run] = token_check(payloads[run], args.max_input_tokens)
        if not checks[run]['within_conservative_guard']:
            raise ValueError(f'run {run}: input exceeds conservative guard ({checks[run]}); no API calls made. Revise explicit compression, never truncate.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    study = HERE / 'results' / f'{"study" if args.execute else "dry_run"}_{stamp}_{uuid.uuid4().hex[:8]}'
    study.mkdir(parents=True, exist_ok=False)
    write(study / 'study_config.json', {'inputs': str(bundle), 'runs': RUNS, 'trials': args.trials,
        'execute': args.execute, 'model': model, 'preflight': checks,
        'bundle_sha256': sha(bundle / 'bundle.json'), 'code_sha256': source_hashes(),
        'semantic_review': 'Human grouping of diagnosis meanings; no extra LLM judge calls.'})
    from render_signatures import render_trial
    for run in RUNS:
        run_dir = bundle / f'run{run}'
        payload = payloads[run]
        folder = study / f'run{run}'
        folder.mkdir()
        write(folder / 'request_payload.json', payload)
        (folder / 'prompt.txt').write_text(payload['instructions'] + '\n\n' + payload['input'])
        records = [json.loads(line) for line in (run_dir / 'evidence.jsonl').read_text().splitlines()]
        manifest = read(run_dir / 'manifest.json')
        first_wire = None
        for trial in range(1, 4):
            directory = folder / f'trial_{trial}'
            result = invoke(payload, directory, execute=args.execute, expected_wire=first_wire)
            wire = result.get('request_body_sha256')
            if first_wire is None: first_wire = wire
            elif wire != first_wire: raise ValueError('Request wire bytes changed: stop study')
            if result['status'] == 'completed':
                prediction = read(directory / 'diagnosis.json')
                audit = validate_citations(prediction, records, manifest['visible_historical_runs'])
                write(directory / 'signature_audit.json', audit)
                render_trial(directory, run_dir, run, trial)
            print(f'run {run} trial {trial}: {result["status"]}', flush=True)
            compare(study)
            if result['status'] in ('failed', 'request_changed'):
                raise RuntimeError(f'Stopped after failed attempt (no retries). Results: {study}')
    compare(study)
    print(f'Results: {study}', flush=True)


if __name__ == '__main__': main()
