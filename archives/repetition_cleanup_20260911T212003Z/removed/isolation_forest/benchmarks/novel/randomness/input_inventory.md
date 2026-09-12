# Phase 1 input inventory — existing added-context novel test

Audited on lxplus949, 2026-09-05 UTC. Scope: reproduce the six-run Sol
added-context test; no diagnostic improvement, feedback or Phase 2 evidence.
The remote benchmark and the inspected local staging copies have identical SHA256.

## Authoritative workflow and prior experiment

`benchmarks/novel/novel_test.py` selects the manifest using
`manifest_path_for(context_mode)`. `baseline` uses `novel_manifest.yaml`;
**`full` uses `context_manifest.yaml`**, rather than merging both manifests.
Both declare targets 1620, 1640, 1642, 1702, 1703 and 2126, the production KB,
frozen campaign, anomaly-log pattern and explicit exclusions. Full mode additionally
declares context sources and excludes run 1637 for the broken-base family.

The wrapper validates both existing manifests, and builds every trial with
`prepare_case(..., context_mode="full")` using the full manifest. It never uses
the baseline input for a randomness trial.

The existing Sol run configuration is
`benchmarks/novel/results/sol_context_20260827T170906Z/run_config.json`.
It records `model_alias=sol`, `model_id=gpt-5.6-sol`, and six original prompt hashes.
The wrapper checks model, full-manifest hash, production-KB hash and every rebuilt
prompt against this record before any real request. Old responses are never read
or reused. If inputs no longer match, the study aborts instead of silently
measuring a different experiment.

| Target | KB runs removed in full mode |
|---|---|
| 1620 | 1620 |
| 1640 | 1640, 1642, 1637 |
| 1642 | 1642, 1640, 1637 |
| 1702 | 1702, 1703 |
| 1703 | 1703, 1702 |
| 2126 | 2126 |

## IF / AutoDQM anomaly evidence

Both manifests point to campaign
`kb_scan_campaigns/kb_task1_runs1500_3000_juan_v1` and pattern
`runs/run{run}/anomaly_log.csv`. These are existing frozen reports, not a new IF run.
`src.llm._historical_snapshot()` reads that CSV, extracts run/subrun from filename,
selects the requested run and anomalous rows, and reports subrun counts,
subruns with anomalies, total anomalous channel entries and detector-ranked rows.
`_summarise_anomaly_df()` includes channel, method, existing max_z, IF score and
triggered features. It takes up to five statistical rows by decreasing max_z,
five IF rows by increasing IF score, and five other rows; any remainder is counted.
These existing report fields are preserved; no new z-score summary or feature
matrix is introduced. Retained historical cases receive the same frozen-report
snapshot through the existing formatter.

## Context discovery and formatting

`context_builders.build_context_bundle()` reads the full manifest's
`context_sources.input_paths_pattern` (`runs/run{run}/input_paths.txt`) under the
frozen campaign. Its first nonempty path supplies only the directory from which
existing TriggerBoard/LVDS telemetry is located. **It does not open the raw
Digitizer CSV.** File paths stay in local audit metadata, not in the LLM prompt.
The existing `_read_triggerboard()` parser skips repeated CSV header lines and
converts values to numbers. Summaries are bounded to 3,500 characters per section
and missing context is reported as unavailable. No new fields are added.

### Trigger

Source: sibling `TriggerBoard_run{run}.csv`.

- Subrun coverage from `subrunnum`.
- `triggerRate_tot` and `triggerCounts_tot`: median, minimum, maximum and temporal
  behavior. Largest adjacent relative changes use the existing median-based scale;
  transition threshold 0.5, variability thresholds 1.0 and 0.25, and displayed
  relative-change threshold 0.2 are unchanged.
- `triggerRate_bit1` through `triggerRate_bit16`: all available medians; up to six
  dominant nonzero bits; up to six variable/intermittent bits with 95–5 percentile
  spread/median and nonzero fraction (existing thresholds 1.0 and 0.8).
- For enabled paths with usable positive prescales, up to six entries show recorded
  median rate, prescale and recorded/prescale estimated physical rate.
- Digitizer-versus-trigger rate consistency is explicitly unavailable because
  compact processed digitizer-rate telemetry was not used.

### LVDS

Source: sibling `TriggerBoardSlab_run{run}_LVDSCounts.csv`.

- Subrun coverage, and `total` (or `LVDStotal`) median/range/temporal behavior.
- Available `LVDSpin0` through `LVDSpin47` signal-pin median counts; 48 comes from
  the repository's `_N_SIGNAL_LVDS_PINS` constant.
- Persistent zero (at least 80% of present values), missing (at least 50%), low
  (ratio to row-positive-pin median at most 0.1 in at least 80%) and high (ratio
  at least 3 in at least 80%) pins; up to eight per list.
- Up to six strongest pin transitions with adjacent relative change at least 2,
  subrun and existing mapping `pin p -> channels 2p / 2p+1`.
- Non-signal LVDS columns are excluded from abnormal-pin classification.

The existing summarizer is used as-is, including its handling of incomplete pin
columns; this phase does not revise detector interpretation or summary algorithms.

### DAQ / configuration

Full manifest paths: `/eos/experiment/milliqan/run3/slab/configs` and its
`thresholds.json`. Existing `src.run_config.parse_trigger_config()` reads
`Run{run}TriggerDefault.py` through regex/literal parsing, not execution.

Included trigger variables:
`triggerBoard.trigger`, `triggerBoard.prescale`, `triggerBoard.trigger_mask`,
`triggerBoard.dead_time`, `triggerBoard.coincidence_time`,
`triggerBoard.nLayerThreshold`, `triggerBoard.nHitThreshold`,
`triggerBoard.zero_bias`.

The summary shows enabled/disabled paths 1–16, path prescales, masked/unmasked
physical-pin counts and masked pins among 0–63, plus the five scalar settings.
The existing prescale array is reversed to associate its final element with path 1.
Mask bits are interpreted with 1=unmasked and 0=masked.

The only DAQ variable requested is `channel.triggerThreshold`.
`parse_daq_thresholds()` preferentially uses per-channel `thresholds.json`
(`digitizer*16+channel`); otherwise it reads the scalar assignment in
`Run{run}DAQDefault.py` and applies the existing 96-channel fallback. The summary
contains finite-channel count, median, range and number of unique threshold values.
Within-run configuration changes, board matching, synchronization, queue occupancy
and DAQ-state telemetry are explicitly unavailable. No extra DAQ evidence is added.

## Filtered knowledge base and leakage controls

Production KB:
`kb_scan_campaigns/kb_task1_runs1500_3000_juan_v1/postprocess/llm_knowledge_base_expanded.yaml`.
`recognition.load_kb()` validates it; `split_kb()` removes exactly the manifest's
singleton run entries. The production KB is never written.
`sanitize_contextual_kb()` preserves the retained cases while removing sentences
explicitly attributed to eLog/provenance from historical cause/action/recovery.
YAML provenance comments are not loaded.

`src.llm._format_historical_case()` supplies historical case ID, source run,
frozen anomaly snapshot, and that retained historical case's category, cause,
action and recovery. These existing historical annotations are part of the
specified filtered KB. The **target's** annotations and its excluded family entries
are absent. Target run tokens are replaced with `CASE_TARGET`.

The existing anti-leakage checks inspect the exact serialized prompt, exclusions,
target identifier, source paths and target annotation provenance. Target annotations
are read locally by the existing code solely for absence checks; they are never
used to assemble model-visible evidence or to label a trial. A literal value shared
with a retained independent historical entry is handled by the existing audit's
collision rule. No new ground-truth comparison is implemented in Phase 1.

## Prompt and structured schema

System instruction: the unchanged `src.llm._SYSTEM`, imported as
`PRODUCTION_SYSTEM_PROMPT` by `novel_test.py`. User input is the exact full-mode
assembly in `prepare_case()`:

1. `CURRENT AUTODQM ANOMALY EVIDENCE`, masked case ID and frozen snapshot.
2. `TRIGGER CONTEXT`, `LVDS CONTEXT`, `DAQ / CONFIG CONTEXT` with existing summaries.
3. `HISTORICAL CASES` with filtered existing formatted cases.
4. The unchanged `NOVEL_TASK` instruction.

`recognition.exact_prompt_serialization()` serializes system/user roles for the
existing prompt hash. The trial saves this exact string without adding a newline.
The actual API receives the system as `instructions` and user as `input`.

The adapter sends `text.format.type=json_schema`,
`name=autoflame_novel_failure_response`, `strict=true` and
`NovelResponse.model_json_schema()`. Pydantic forbids extra properties and requires:

| Field | Existing type/constraint |
|---|---|
| category | unrestricted string; no enum or fixed taxonomy |
| cause | string |
| action | string |
| confidence | number, 0.0–1.0 |
| supporting_historical_runs | integer array; post-parse validation restricts to visible runs |
| reasoning_summary | string |

The full exact schema is saved in every request payload. The existing system
instruction's low/medium/high confidence wording and novel task/schema's numeric
confidence constraint are preserved; this phase does not revise prompts.

## Model, request settings, retries and caches

- Alias resolution: `novel.resolve_model("sol")` reads `AUTOFLAME_SOL_MODEL`.
  This shell did not initially define it. The verified prior model ID is
  **`gpt-5.6-sol`**; the provided command sets precisely that value and the wrapper
  rejects disagreement with the prior Sol run configuration.
- Existing adapter: `novel.openai_call()` -> `OpenAI().responses.create()`.
  Explicit request keys are only `model`, `instructions`, `input`, `text`.
- **temperature, top_p and seed are NOT SENT. There is no client-sent fixed seed.**
  No reasoning-effort, max-output-tokens, penalty, service-tier or truncation
  override is sent. Omission means server/model defaults, not a known numeric value.
  Full returned provider metadata is preserved for later interpretation.
- Audited runtime: Python 3.9.25, OpenAI SDK 2.48.0, Pydantic 2.13.4.
  Default SDK retries: 2; default timeout: connect 5 seconds, read/write/pool 600.
  Existing benchmark `call_with_retries()` adds up to 3 attempts including parse
  failures. Its result-directory resume logic skips completed targets unless forced.
- Existing `prepare_all_cases()` memoizes anomaly snapshots within a preparation
  batch. It does not cache model responses. Existing result skipping is not used
  by the randomness wrapper.
- For exactly one request attempt per trial, the wrapper bypasses the outer retry
  helper and injects a client with `max_retries=0`; it keeps the SDK's default HTTP
  client/timeouts and calls the original adapter unchanged. This affects transport
  failure handling only, not the effective model request or sampling settings.
- The wrapper's only input cache is in-memory anomaly summaries keyed by source
  path, run and freshly computed file SHA256, delegating rendering to the existing
  `_historical_snapshot()`. Each trial reloads manifests/KB, rebuilds context and
  the full prompt and rechecks all hashes. No generated response is cached or reused.
- No prompt-cache options are explicitly set. Provider-side prefix caching may
  exist outside client control and is not disabled; any returned cache/token-use
  metadata is retained. A fresh request is not a guarantee of no provider-side
  prefix caching or of mathematically independent random samples.

## Request identity and preservation

The isolated wrapper calls the existing adapter with a scoped client injection.
HTTP hooks observe the SDK's actual request body and read the complete response
body. A dry-run uses `httpx.MockTransport` and exits before any network request.
The six preflight requests and 30 dry-run trials therefore spend zero API calls.

`input_sha256` = SHA256 of complete request JSON canonicalized with sorted keys,
compact separators, UTF-8 and no NaN. This includes system/user text, model and
schema. `request_body_sha256` hashes exact transmitted JSON bytes, which are saved
as `request_body.json`. Both hashes, endpoint and component hashes must match the
same run's preflight before transmission. Timestamps/trial IDs are local metadata,
never added to the request. Auth headers and API keys are never saved.

Component hashes: existing serialized-prompt SHA256; canonical filtered-KB JSON
SHA256; canonical `{trigger,lvds,daq_config}` JSON SHA256; anomaly-text SHA256;
model-ID string SHA256. Source-file hashes and the prior experiment identifier
are recorded in `study_config.json`.

Every trial retains request body/payload, prompt, filtered KB, context, leakage
audit, timestamp/run/trial/model/settings/hash metadata. Real calls additionally
retain complete raw HTTP response bytes, JSON body when decodable, SDK response,
output text and parsed `NovelResponse` when parsing succeeds. HTTP and parse
failures are retained and never silently replaced by another generation.

## Exact variation versus physical interpretation

`n_unique_exact_diagnoses` counts distinct **cause strings** among completed trials,
without case folding, trimming, paraphrase merging or judging. Separate exact
counts are supplied for action, category and the entire structured response.
All five complete category/cause/action strings appear side-by-side, with links
to full raw and parsed responses. Failed/missing trials are explicitly marked.
Because no discrete diagnosis field exists, dominant diagnosis/count and semantic
consistency rate are left blank. No classifier, new physics taxonomy or LLM judge
is introduced. No diagnosis accuracy or Phase 2 result is claimed.

## Audited immutable input fingerprints

| Item | SHA256 |
|---|---|
| novel_test.py | a4300475d2a9780b0b009e5d18fad991ebea2bd8277c211555f97bc209409013 |
| context_builders.py | 47985860273d95bf1d7240bd71f4d0c1448117055166f2d7451c3a36df59939c |
| novel_manifest.yaml | ad9e18cfb8f0c4a8122e4c1285a2c408c5ec1f4dca98033e23e653fe51749062 |
| context_manifest.yaml | 782f7ab94d1869c9d70ce23d0ccc6d73dacb205a509bac2ccd9c3d36156bccb3 |
| production KB | 46851b3ca14f78ec39ceee82abd1a2797b9ff4fe13719d3270f3717af9e7c156 |
| src/llm.py | 7811cca61eaada54923e5b38c37340cb4464e224ce6f0fa7fb6fe50992c5a033 |
