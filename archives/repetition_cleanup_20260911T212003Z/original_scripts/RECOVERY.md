# Resume the interrupted raw-summary study

The run1640 trial2 request in `study_20260910T233752Z_e8027ad4` received HTTP 520
after 16.96 seconds. The saved Cloudflare JSON reports `unknown_origin_error`,
`retryable: true`, `retry_after: 60`, and an upstream response it could not parse.
It is not a model diagnosis or a reported context-limit/schema failure. Whether
the upstream request incurred usage cannot be determined from this response.

Four completed diagnoses are retained: run1620 trials1–3 and run1640 trial1.
There are 14 remaining successful-diagnosis slots. The original runner intentionally
stopped with no retries, but lacked a resume entry point. A separate recovery
module now adds that entry point without editing the original runner or prompt.

## User-executed recovery

After the suggested 60-second backoff, with OPENAI_API_KEY set privately:

```bash
cd /afs/cern.ch/user/p/pengy/autoDQM/isolation_forest
python3 benchmarks/novel/raw_consistency/resume_study.py \
  --study benchmarks/novel/raw_consistency/results/study_20260910T233752Z_e8027ad4 \
  --execute
```

Model, input bundle and settings are read from the original study. No model or
input overrides are accepted. Remove `--execute` for a read-only recovery plan
with network-blocking SDK serialization in temporary directories.

- Verify original code hashes, frozen bundle/artifact hashes, existing request
  content and wire hashes before any new paid request.
- Skip completed trials. Verify their saved diagnoses match saved model output.
- Before retrying an explicit retryable HTTP failure, move that failed attempt
  into `recovery_attempts/<UTC_id>/run<run>/trial_<n>/`, verify its hashes, and
  record the move in `recovery.json`. Never overwrite/drop the failed evidence.
- Reuse exactly the same request body for that run, checked before transmission.
- Run the previously unstarted slots and generate their signature figures.
- No automatic retry loop. Another failure stops; rerun this recovery command
  after inspection/backoff. Concurrent recovery processes are locked out.
- Ambiguous partial attempts, authentication errors, parse failures or attempts
  that already contain output are not automatically retried.

The study directory remains unchanged. The final three diagnoses per run refer
to three completed responses, while all failed HTTP attempts are disclosed
separately. This is transport-error recovery, not selection by diagnosis content.

## Validation

The actual interrupted study passed read-only recovery preflight: skip four,
retry one explicit 520, start thirteen; all six SDK requests matched frozen
content, including existing wire hashes. No paid requests or study writes were
made during this inspection. Recovery tests use temporary synthetic fixtures.

The service-error reference is
https://developers.openai.com/api/docs/guides/error-codes ; the specific 520
details above come from the preserved `run1640/trial_2/raw_response_body.bin`.
