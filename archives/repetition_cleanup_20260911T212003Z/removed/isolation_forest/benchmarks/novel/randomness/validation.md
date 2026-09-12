# Phase 1 validation

Validated on lxplus949, 2026-09-05 UTC, using the installed Python 3.9.25,
OpenAI SDK 2.48.0 and Pydantic 2.13.4. **Real API calls: 0.**

## Completed real-input dry-run

Output: [dry_run_20260905T002507Z_fc2cc95c](dry_run_20260905T002507Z_fc2cc95c/).
The six preflight prompts matched the original added-context Sol configuration
`../results/sol_context_20260827T170906Z/run_config.json`. All 30 trial inputs were
rebuilt/captured through the existing framework and OpenAI SDK with MockTransport.
Study status: `dry_run_passed`; HTTP attempts: 0.

| Run | Trial 1–5 full-input hashes | Effective input SHA256 |
|---|---|---|
| 1620 | MATCH | f6d470665690588bbd23dbde3bdfb8e5cc91cdb90729b5e70b8de5254e9ad3fb |
| 1640 | MATCH | 09f68dfce57de1bc2a480f4668f18fc98aeaff2b790fcecd77b6e89faa9603f8 |
| 1642 | MATCH | a0f02a64fc408c3c37f37e9625789878a55b1768c2c22ac23db7ccf28955d607 |
| 1702 | MATCH | 8253939555ddb41db8524014831ff714e582b4ed31e0cdfe9be2753f47c705b8 |
| 1703 | MATCH | 06a126155954a471c435c1fcb221bb5a63080e144e825b8fd04a7f92a23992d2 |
| 2126 | MATCH | 7f6f72369ba65bffee32139b0853c08cb98f690f87dbc5f6f5c5ddc2bb978a19 |

Every request contains only `model`, `instructions`, `input`, and `text`.
Model: `gpt-5.6-sol`; temperature/top_p/seed and all other audited sampling
overrides are absent. Prompt, context, filtered-KB and exact request-body hashes
are preserved separately in each trial's metadata.

## Offline integration tests

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s benchmarks/novel/randomness -p test_randomness.py -v
```

Result: **8 tests passed in 38.593 seconds**.

- Exact SDK payload equals arguments captured directly from the original adapter;
  no sampling override added and dry-run makes no network attempt.
- A complete mocked study sends exactly 30 requests, returns 30 distinct fixture
  causes and rebuilds cases 36 times (6 preflight + 30 trials); all within-run
  input hashes match. Raw and parsed outputs are saved for every call.
- Deliberate input-hash drift stops before the HTTP transport runs.
- HTTP 500 is preserved and results in one attempt, without retry.
- Invalid JSON output preserves the complete raw response and output text.
- Target-ID leakage and disagreement with original prompt hashes are rejected.
- Existing directories cannot be overwritten; model and trial-count drift rejected.
- Minor wording differences count as exact variation without a semantic classifier;
  summary strings preserve content and escape Markdown table delimiters.

Fixture outputs were stored in temporary test directories and automatically
cleaned up by unittest fixtures; they are not study results. An earlier development
dry-run was interrupted before completion and is marked aborted; the completed
dry-run named above is the validation artifact.

## Scope verification

Post-validation hashes of `novel_test.py`, `context_builders.py`, both existing
manifests and `src/llm.py` match the pre-edit inventory. Existing project changes
remain in place. All permanent new files and results are under
`benchmarks/novel/randomness/`. No production IF processing, KB edit, raw Digitizer
input, feedback optimization, ground-truth injection or real diagnosis generation
was performed. The real 30-call study remains to be explicitly launched.
