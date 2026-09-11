#!/usr/bin/env python3
"""Resume explicit transport failures without changing frozen requests or completed trials.

Default: read-only study inspection plus SDK serialization in temporary directories.
Only --execute moves failed attempts to the audit archive and makes API calls.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
from common import HERE, RUNS, read, write, sha, digest, verify_files
from run_study import make_payload, invoke, token_check, Diagnosis, validate_citations, compare
from render_signatures import render_trial

RETRYABLE_HTTP = {408, 409, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}


def classify(directory):
    if not directory.exists(): return 'not_started'
    if not (directory / 'metadata.json').exists():
        raise ValueError(f'Ambiguous partial attempt (no metadata): {directory}; inspect manually')
    meta = read(directory / 'metadata.json')
    if meta['status'] == 'completed':
        prediction = Diagnosis.model_validate(read(directory / 'diagnosis.json')).model_dump(mode='json')
        response = read(directory / 'raw_response.json')
        if response.get('status') != 'completed': raise ValueError('Completed trial has incomplete server response')
        texts = [c['text'] for item in response.get('output', []) for c in item.get('content', []) if c.get('type') == 'output_text']
        if Diagnosis.model_validate_json(''.join(texts)).model_dump(mode='json') != prediction:
            raise ValueError(f'Saved diagnosis and server output disagree: {directory}')
        if not (directory / 'signature_records.json').exists():
            raise ValueError(f'Completed diagnosis has incomplete postprocessing: {directory}; repair offline, do not call again')
        return 'completed'
    if (directory / 'diagnosis.json').exists() or (directory / 'output_text.txt').exists():
        raise ValueError(f'Attempt already has output; no automatic replacement: {directory}')
    if meta['status'] == 'failed' and meta.get('http_status') in RETRYABLE_HTTP:
        return 'retry_transport_failure'
    raise ValueError(f'Not an explicit retryable HTTP failure: {directory}; inspect before retrying')


def plan(study):
    config = read(study / 'study_config.json')
    if not config.get('execute') or config['runs'] != RUNS or config['trials'] != 3:
        raise ValueError('Expected the original six-run, three-trial paid study')
    # Original runner/schema/rendering code must match. This new recovery module
    # is additional orchestration, not a change to any original request builder.
    verify_files(config['code_sha256'])
    bundle = Path(config['inputs'])
    if sha(bundle / 'bundle.json') != config['bundle_sha256']: raise ValueError('Bundle changed')
    bundle_config = read(bundle / 'bundle.json')
    manifest_hashes = {e['run']: e['manifest_sha256'] for e in bundle_config['runs']}
    payloads, wires, tasks = {}, {}, []
    for run in RUNS:
        inputs = bundle / f'run{run}'
        if sha(inputs / 'manifest.json') != manifest_hashes[run]: raise ValueError('Run manifest changed')
        payload = make_payload(inputs, config['model'])
        guard = config['preflight'][str(run)]['max_input_tokens_guard']
        if not token_check(payload, guard)['within_conservative_guard']: raise ValueError('Input guard changed')
        run_dir = study / f'run{run}'
        if (run_dir / 'request_payload.json').exists() and digest(read(run_dir / 'request_payload.json')) != digest(payload):
            raise ValueError('Saved run payload differs from reconstructed frozen input')
        expected_wire, endpoint = None, None
        for trial in range(1, 4):
            directory = run_dir / f'trial_{trial}'
            state = classify(directory)
            if directory.exists():
                meta = read(directory / 'metadata.json')
                if meta.get('input_sha256') != digest(payload): raise ValueError('Existing trial input differs')
                wire = sha(directory / 'request_body.json')
                if wire != meta.get('request_body_sha256'): raise ValueError('Stored request bytes changed')
                if expected_wire and wire != expected_wire: raise ValueError('Existing trial wire mismatch')
                expected_wire = wire
                endpoint = endpoint or meta.get('endpoint')
                if meta.get('endpoint') != endpoint: raise ValueError('Existing endpoint mismatch')
            tasks.append({'run': run, 'trial': trial, 'state': state})
        # Uses the real SDK serializer but cannot reach the network. This happens
        # for all six runs BEFORE the first new paid request.
        with tempfile.TemporaryDirectory(prefix='autoflame-resume-check-') as tmp:
            check = invoke(payload, Path(tmp) / 'request', expected_wire=expected_wire)
            if check['status'] != 'dry_run' or check['network_attempts'] != 0:
                raise ValueError('SDK request no longer matches original study')
            if endpoint and check['endpoint'] != endpoint: raise ValueError('Endpoint changed')
            wires[run] = check['request_body_sha256']
        payloads[run] = payload
    return config, payloads, wires, tasks


def archive_failure(directory, archive_root):
    """Called only during explicit --execute; never overwrites prior attempts."""
    state = classify(directory)
    if state != 'retry_transport_failure': raise ValueError('Refusing to archive a non-transport failure')
    before = {str(p.relative_to(directory)): sha(p) for p in directory.rglob('*') if p.is_file()}
    destination = archive_root / directory.parent.name / directory.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists(): raise ValueError('Archive collision')
    shutil.move(str(directory), str(destination))
    verify_files({str(destination / name): h for name, h in before.items()})
    return {'original': str(directory), 'archived': str(destination), 'sha256': before}


@contextmanager
def execution_lock(study):
    with (study / '.resume.lock').open('a') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try: yield
        finally: fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def execute(study):
    if not os.environ.get('OPENAI_API_KEY'): raise ValueError('Set OPENAI_API_KEY privately in this terminal')
    with execution_lock(study):
        config, payloads, wires, tasks = plan(study)
        remaining = [t for t in tasks if t['state'] != 'completed']
        if not remaining:
            print('All 18 diagnoses are already completed; no API calls.'); return
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
        recovery = study / 'recovery_attempts' / stamp
        recovery.mkdir(parents=True, exist_ok=False)
        journal = {'protocol': 'Manual transport-error recovery. Failed HTTP attempts are retained and excluded from the three successful diagnoses. No selection by diagnosis content.',
                   'resume_code_sha256': sha(Path(__file__)), 'planned': remaining, 'archived_failures': [], 'new_attempts': []}
        write(recovery / 'recovery.json', journal)
        for task in remaining:
            run, trial = task['run'], task['trial']
            inputs = Path(config['inputs']) / f'run{run}'
            folder = study / f'run{run}'
            directory = folder / f'trial_{trial}'
            if classify(directory) != task['state']: raise ValueError('Trial state changed since preflight')
            if task['state'] == 'retry_transport_failure':
                journal['archived_failures'].append(archive_failure(directory, recovery))
                write(recovery / 'recovery.json', journal)
            folder.mkdir(exist_ok=True)
            payload = payloads[run]
            if not (folder / 'request_payload.json').exists(): write(folder / 'request_payload.json', payload)
            if not (folder / 'prompt.txt').exists():
                (folder / 'prompt.txt').write_text(payload['instructions'] + '\n\n' + payload['input'])
            result = invoke(payload, directory, execute=True, expected_wire=wires[run])
            journal['new_attempts'].append({**task, 'result': result['status']})
            write(recovery / 'recovery.json', journal)
            print(f'run {run} trial {trial}: {result["status"]}', flush=True)
            if result['status'] == 'completed':
                records = [json.loads(line) for line in (inputs / 'evidence.jsonl').read_text().splitlines()]
                audit = validate_citations(read(directory / 'diagnosis.json'), records, read(inputs / 'manifest.json')['visible_historical_runs'])
                write(directory / 'signature_audit.json', audit)
                render_trial(directory, inputs, run, trial)
            compare(study)
            if result['status'] != 'completed':
                raise RuntimeError(f'Stopped after failed attempt; no automatic retries. Prior successes retained. Results: {study}')
        print(f'Results: {study}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', required=True, type=Path)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    study = args.study.resolve()
    if args.execute: execute(study)
    else:
        _, _, _, tasks = plan(study)
        for task in tasks: print(f'run {task["run"]} trial {task["trial"]}: {task["state"]}')
        print(f'Skip {sum(t["state"] == "completed" for t in tasks)} completed trials; {sum(t["state"] != "completed" for t in tasks)} remaining. No API calls or study writes.')


if __name__ == '__main__': main()
