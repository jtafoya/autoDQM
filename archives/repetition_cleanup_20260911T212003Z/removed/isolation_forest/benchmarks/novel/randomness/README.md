# Phase 1 — Sol randomness / reproducibility

> **Archived / superseded for the expanded-input study (2026-09-10).**
> Use [../raw_consistency/README.md](../raw_consistency/README.md) for the new
> all-file raw-summary, three-trial consistency experiment. Do not use the old
> commands below for the new experiment. Legacy results, dry-runs and the
> post-hoc feature-matrix supplement are preserved under
> `archive_summary_only_20260910/`; `archive_manifest.json` records original
> locations and verified SHA-256 values. They are not inputs to the new study.
> The remainder of this document is historical documentation, not current status.

Uses only the existing full-context novel test and its original six runs. Read
[input_inventory.md](input_inventory.md) for exact inputs, request settings,
exclusions, schema and caching audit.
See [validation.md](validation.md) for the completed 30-input dry-run and eight
passing offline tests. No paid study has been run as part of this implementation.

From the lxplus repository:

```bash
cd /afs/cern.ch/user/p/pengy/autoDQM/isolation_forest
export AUTOFLAME_SOL_MODEL=gpt-5.6-sol

# Default mode: 30 full trial input builds and SDK request captures, NO network.
python3 benchmarks/novel/randomness/randomness_check.py --model-alias sol --trials 5 --dry-run

# Offline integration tests, including mocked HTTP success/error/parse failure.
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s benchmarks/novel/randomness -p 'test_randomness.py' -v

# REAL execution: OPENAI_API_KEY must already be configured in this shell.
python3 benchmarks/novel/randomness/randomness_check.py --model-alias sol --trials 5 --execute
```

Every invocation creates a unique output directory under this directory:
`dry_run_<UTC>_<suffix>/` or `study_<UTC>_<suffix>/`. An explicit `--result-dir`
must be a new subdirectory here. Existing directories are refused; there is no
force, resume, response cache or overwrite option. Existing novel results remain
untouched. No real API requests run unless `--execute` is passed.

Each output contains `study_config.json`, `preflight/runNNNN/`, all
`runNNNN/trial_1/` through `trial_5/`, `results.json`, `randomness_summary.csv` and
`randomness_summary.md`. Trial files include exact input and component hashes,
request body/payload, prompt, context, filtered KB, audit and metadata. Real calls
also retain full HTTP bytes and decoded response, SDK response, output text and
parsed structured output where available.

All six preflight prompt hashes must match the original added-context Sol study.
Every trial rebuilds input through existing functions, then checks the full
serialized request and component hashes before sending. Any input mismatch aborts
the study with a nonzero exit code and explicit incomplete/mismatch reporting.
Anomaly snapshot rendering is memoized by source content SHA256 in memory only;
this avoids repeatedly parsing identical large frozen logs, not LLM calls.

Real mode makes one HTTP attempt per trial, 30 total when preparation stays valid.
SDK and benchmark retries are disabled so an error does not become extra paid
generations. A failed request or parse is saved and counts as a failed trial;
the remaining scheduled trials continue. Thirty attempts are not necessarily
thirty successful diagnoses. A transport interruption can leave the server's
completion state unknown; request timestamps/IDs and saved files support auditing.

Exit codes: 0 = all 30 dry captures or all 30 real parsed predictions completed;
1 = scheduled study contains failed trials; 2 = configuration/preflight/input error.
Interruptions abort and save the available partial summary.

Summary exact counts are case-sensitive string comparisons of cause/action/category,
plus distinct complete structured responses. The five unabridged diagnoses and
actions are shown together for manual semantic review. All fields are free text;
no semantic categories or LLM judge are added and no consistency rate is inferred.
Dry-run reports intentionally show no diagnoses and support no randomness conclusion.
