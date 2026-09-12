# Raw-summary consistency study (six runs, three trials)

This supersedes the summary-only five-trial study for the new experiment. It does
not make the old observations false: those results used a different, compressed
input and cannot answer the expanded-input question. Old results are archived,
not used as input, and must not be mixed into this study.

## What is fixed

For each of 1620, 1640, 1642, 1702, 1703 and 2126, prepare one immutable bundle:

1. **Complete aggregate anomaly evidence:** every frozen anomaly-log row is
   counted; every logged channel, method and triggered feature is retained,
   including IF-only and missing-channel observations. There is no top-five filter.
   The original full log is saved alongside its aggregate summary. Full log row
   text is not itself sent to the model.
2. **Trigger / LVDS / DAQ configuration summaries:** existing context builders,
   without their character cutoff, retain source coverage and unknowns. These
   are still summaries, with the existing dominant-bit/detail selection rules,
   not complete telemetry rows. Static configuration does not prove within-run
   configuration stability. Partial coverage does not establish whole-run health.
3. **Filtered historical KB:** same target/family removal and provenance
   sanitization as the existing full-context novel benchmark. All surviving KB
   entries are serialized in full. No target diagnosis, ground truth, prior
   prediction, old randomness result or old highlight is included.
4. **Summaries calculated from every raw Digitizer CSV:** no channel selection,
   anomaly-only selection or random event sampling. Raw files are read-only.

The source pattern is
`/eos/experiment/milliqan/run3_MilliMon/slab/{run//100*100}/Digitizer_run{run}_subrun*.csv`.
For run1640 the directory is `1600`; run1702/1703 use `1700`; run2126 uses `2100`.

Raw compression includes every numeric measurement column (including TDC and
TDCRollovers), all 96 channels, finite counts, pooled mean/population standard
deviation, min/max, zero/negative fractions, exact 32-bin distribution counts,
channel presence, event occupancy, geometry values, subrun-median quantiles,
eight chronological subrun-bin means and largest adjacent mean change.
Histograms use shared per-metric asinh-spaced edges, spanning all observed values.
All file-level channel/metric statistics, including q05/q25/median/q75/q95,
remain in `raw_detail.npz` at float64 precision. They are not all sent to the LLM.

These are **lossy summaries, not raw event rows or waveforms**. They can miss
event-order effects, correlations and narrow distribution details. Prompt
numbers are rounded to six significant figures. Numeric subrun order is not
elapsed time. No good-run raw reference is added. No cause labels are hardcoded.

## Frozen input locations

Each preparation creates a new, non-overwriting directory:

`benchmarks/novel/raw_consistency/inputs/bundle_<UTC>/`

Each `run<run>/` contains:

- `raw_inventory.json`: absolute paths, SHA-256 and sizes of **every original
  CSV**, row/event counts, duplicate counts, definitions, bins and summary path.
- `raw_detail.npz`: all-subrun numerical detail; arrays `stats`, `subruns`,
  `channels`, `metrics`, `statistic_names`, `channel_events`, `total_events`,
  `rows`, `zero_pulse_events`, `histograms`, `histogram_edges`.
- `evidence.jsonl`: the exact evidence records sent to the model. IDs beginning
  R/P are raw-derived, A is anomaly evidence, C is context, H is historical KB.
- `summary_header.json`: definitions, coverage, common histogram edges and time bins.
- `anomaly_summary.json`, `anomaly_log.csv`, `context.json`, `filtered_kb.json`.
- `manifest.json`: source/artifact hashes, family exclusions, visible historical
  runs, frozen production system prompt. Source paths and excluded-case metadata
  are provenance, not model input.

`bundle.json` is written only after all requested preparations succeed. Incomplete
directories without it are not executable inputs. Once prepared, execution uses
the frozen bundle, not changing live CSVs. Keep the entire bundle with the study.

## Commands (from the isolation_forest repository)

Offline preparation, no API key/network needed:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python3 benchmarks/novel/raw_consistency/prepare_inputs.py --workers 2
```

The command prints the exact bundle directory. Substitute that path below:

```bash
AUTOFLAME_SOL_MODEL=gpt-5.6-sol \
python3 benchmarks/novel/raw_consistency/run_study.py \
  --inputs /absolute/path/to/bundle --model-alias sol --trials 3 --max-input-tokens 950000
```

This is a **dry-run**: 18 requests are serialized through a network-blocking mock
transport; no diagnoses or claimed LLM evidence are fabricated. Review its
`study_config.json` and per-run `prompt.txt` / `request_payload.json`.

Only the user executes the paid run, with OPENAI_API_KEY already set privately:

```bash
AUTOFLAME_SOL_MODEL=gpt-5.6-sol \
python3 benchmarks/novel/raw_consistency/run_study.py \
  --inputs /absolute/path/to/bundle --model-alias sol --trials 3 --max-input-tokens 950000 --execute
```

Exactly one diagnostic request per trial; no agent tools, conversation history,
response reuse, automatic retries or extra LLM judge calls. The three requests
for one run have identical model, prompt, schema and sampling configuration.
The first request's wire hash is checked before later transmissions. The model
defaults to gpt-5.6-sol; the named environment variable can explicitly override it.
Reasoning is medium, max_output_tokens 24000, truncation disabled, store false;
temperature/top_p/seed are not sent. Returned model identity and usage are saved.

Before the first paid request ALL six inputs must pass the conservative context
guard: serialized UTF-8 bytes <= the explicit guard (default 900000; 950000 for
the validated six-run bundle), an upper bound on byte-tokenizer input
tokens, not an exact token estimate. The model window must still accommodate
output and provider overhead. The API rejects oversized context rather than
truncating. A failed/incomplete request stops the study and is retained, without
retry. Do not count that run as having three complete diagnoses or rerun into the
same result directory. A new command creates a new independent study.

## The two outputs per trial

`results/study_<UTC>_<id>/run<run>/trial_<1..3>/` contains:

1. `diagnosis.json` and `diagnosis_report.md`: category, cause, action, confidence,
   concise justification, free-text semantic descriptors and missing information.
2. `signature_records.json`, `signature_audit.json`, `signature_images/`:
   model-stated observations, exact input citations, stated cause/action links,
   an overview image, per-signature evidence/link images, and distribution/time
   plots for **every cited raw numeric/presence record**. A signature can require
   multiple images. Context/KB citations are shown as text, not invented raw plots.

Every citation identifies an evidence ID, field path and exact supplied value.
The validator checks identity/value equality and flags bad references. It does
NOT claim that a correct citation proves the prose interpretation or cause.
Figures visualize **LLM-cited evidence**, not hidden reasoning or internal feature
importance. No retrospective global zmax heatmap substitutes for these citations.
Plots use the same rounded summary records the LLM saw, not undisclosed detail.

Complete raw response bytes (including errors), parsed response, output text,
request bytes/hash, IDs, model and token usage are also retained.

## Meaning-based consistency, not wording identity

`consistency.md` / `consistency.json` compare category/cause/action side by side.
Normalized wording equality is a separate descriptive field, **not the semantic
verdict**. Different phrases meaning the same cause must be grouped together.
Arbitrary free-text semantics are not reliably judged with string similarity.
To avoid extra paid calls or misleading automatic judgments, semantic verdicts
remain `pending_human_review` until a reviewer fills `semantic_review.json`:

- For each field, assign the same group label to trials with the same meaning.
  Example: three paraphrases of a base failure receive `["A","A","A"]`.
- Different primary mechanisms receive different labels. Preserve unknown vs
  specific causes and conditional vs incompatible actions.
- Fill `reviewer` and `rationale`. No ground truth is needed or scored.

Regenerate the semantic verdict and figures **offline**:

```bash
python3 benchmarks/novel/raw_consistency/run_study.py \
  --report-only /absolute/path/to/results/study_<UTC>_<id>
```

Three completed reports, with identical request bytes, are required for a complete
run comparison. Signature variation is descriptive, not a failure criterion.
Consistency says nothing by itself about diagnostic accuracy.

## Offline tests

```bash
cd benchmarks/novel/raw_consistency
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_raw_consistency
```

Tests use synthetic data and mocked HTTP responses. Any mock figure is clearly
marked as a pipeline test and must not be reported as a real LLM diagnosis.

Implementation uses the existing lxplus Python scientific stack; no production
pipeline, KB or raw source is overwritten. OpenAI interface reference:
https://developers.openai.com/api/reference/cli/resources/responses/methods/create
