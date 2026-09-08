# AutoFLAME known-failure recognition benchmark

This benchmark evaluates whether one OpenAI model can recognize nine manually
defined, previously seen detector-failure cases. It uses the frozen campaign's
per-run `anomaly_log.csv` outputs and imports the production system prompt,
run-level anomaly summary, and historical-case formatting from `src/llm.py`.
It does not rerun the Isolation Forest or modify the production knowledge base.

## Commands

Run the no-cost preflight first:

```bash
python3 benchmarks/recognition/recognition_test.py dry-run
```

Then set `OPENAI_API_KEY` and the real model IDs supplied for your account:

```bash
export AUTOFLAME_LUNA_MODEL='<actual Luna API model id>'
export AUTOFLAME_SOL_MODEL='<actual Sol API model id>'

python3 benchmarks/recognition/recognition_test.py run --model-alias luna
python3 benchmarks/recognition/recognition_test.py run --model-alias sol
```

To resume, pass the original output directory using `--result-dir`. Successfully
completed targets are skipped unless `--force` is supplied.

Compare the two completed directories:

```bash
python3 benchmarks/recognition/recognition_test.py compare \
  --luna benchmarks/recognition/results/<luna-result-dir> \
  --sol benchmarks/recognition/results/<sol-result-dir>
```

The model-visible prompt is saved as an exact JSON serialization of the system
and user strings. A digit-boundary-aware check masks the hidden target ID and
verifies that expected peers remain visible. Ground truth is added only to
evaluator result records after a response has been received.

## Production-interface limitation

The repository currently has no `src/kb_scan.py`. The production `src/llm.py`
path is alert/subrun-oriented, whereas this benchmark requires deterministic
run-level cases. The wrapper therefore reuses its `_SYSTEM`,
`_historical_snapshot`, and `_format_historical_case` helpers and changes only
the current-case wrapper and response schema. Every run-level snapshot includes
all anomalous subruns in its counts and deterministic detector ranking.
