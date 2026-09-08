# AutoFLAME novel-failure generation benchmark

This benchmark tests diagnosis when the target's explicitly defined recognition
family is absent from the historical KB. It reuses the production system prompt,
historical-case formatter, run-level AutoDQM snapshot, and the recognition
benchmark's OpenAI/retry helpers. It does not score predictions or expose target
ground truth.

Manifest exclusions remove only the declared family members. If another retained
KB entry has no frozen anomaly log, its historical annotation remains visible and
the snapshot is marked unavailable without exposing a filesystem path.

The model-visible input is limited to the production instruction, the target's
frozen `anomaly_log.csv` summary, and the explicitly filtered historical KB
(including its normal frozen snapshots). Audit JSON records the exact serialized
prompt hash and confirms that no direct Digitizer, TriggerBoard, LVDS-counter,
DAQ/CPU, board-matching, queue, trigger-configuration, eLog/provenance, or target
ground-truth context was appended. Words about those systems can still occur in
allowed historical KB annotations; the audit concerns input provenance, not a
keyword ban.

## Validate without network access

```bash
python3 -m unittest discover -s tests -p 'test_novel_benchmark.py' -v
python3 benchmarks/novel/novel_test.py dry-run
```

The dry-run prepares and audits all six real prompts and makes zero API calls.

## Run Luna and Sol

```bash
export OPENAI_API_KEY='...'
export AUTOFLAME_LUNA_MODEL='<actual Luna API model id>'
export AUTOFLAME_SOL_MODEL='<actual Sol API model id>'

python3 benchmarks/novel/novel_test.py run --model-alias luna
python3 benchmarks/novel/novel_test.py run --model-alias sol
```

Resume a result directory with `--result-dir`; completed cases are skipped unless
`--force` is supplied. Each completed model run writes six predictions to
`novel_predictions.yaml` and a six-section `report.md`. Prompt hashes are saved in
the per-case preflight metadata and `run_config.json` so Luna/Sol inputs can be
checked for equality without comparing model outputs.

## Context-enriched ablation

`--context-mode full` keeps the baseline target task, production system prompt,
frozen anomaly evidence, KB, structured response, API adapter, and retry/resume
behavior while adding compact TriggerBoard, LVDS, and MilliDAQ/config summaries.
It uses `context_manifest.yaml`, whose explicit exclusions additionally hide run
1637 for targets 1640 and 1642. The baseline manifest and default command behavior
remain unchanged.

The context builders reuse the repository's TriggerBoard CSV reader and MilliDAQ
configuration parsers. Missing telemetry is serialized as unavailable; raw CSVs,
paths, target identifiers, eLog-attributed sentences, and target annotations are
not model-visible. Per-case prompts, individual summaries, filtered KB snapshots,
source availability, source paths (audit metadata only), and prompt hashes are
saved before any API call.

```bash
python3 -m unittest discover -s tests -p 'test_context_novel_benchmark.py' -v
python3 benchmarks/novel/novel_test.py dry-run --context-mode full

python3 benchmarks/novel/novel_test.py run --model-alias luna --context-mode full
python3 benchmarks/novel/novel_test.py run --model-alias sol --context-mode full
```

Default contextual result directories are named `luna_context_<timestamp>` and
`sol_context_<timestamp>` under `benchmarks/novel/results/`.
