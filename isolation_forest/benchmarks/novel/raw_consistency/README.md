# AutoFLAME semantic consistency study: three retained cases

Active cases: **1620, 1640, 1642**, each with **3 completed independent trials**.
Compare the meaning of category, cause and action, not exact wording. Accuracy is
a separate question. No additional paid calls are needed for these nine results.

## Existing results and inputs on lxplus

Repository: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest`

- Results: `benchmarks/novel/raw_consistency/results/study_20260910T233752Z_e8027ad4/run{run}/trial_{1,2,3}/`
- Frozen inputs: `benchmarks/novel/raw_consistency/inputs/bundle_20260910T230921Z/run{run}/`
- Each trial retains diagnosis.json, diagnosis_report.md, signature_records.json,
  signature_audit.json, signature_images, original request bytes and server response.
- Each input retains evidence.jsonl (exact supplied records), summary_header.json,
  raw_inventory.json (every raw-file path and hash), raw_detail.npz, anomaly summary,
  context, filtered KB and the input manifest.
- CSV counts: 1620 = 259, 1640 = 741, 1642 = 202.
- Raw source: `/eos/experiment/milliqan/run3_MilliMon/slab/1600/Digitizer_run{run}_subrun*.csv`.
- Expanded KB: `/afs/cern.ch/user/p/pengy/autoDQM/data/llm_knowledge_base_expanded.yaml`.

The user reduced the scope after the experiment. Historical study_config.json and
bundle.json remain byte-for-byte unchanged as provenance. They still list the
original six cases. retained_scope.json records the three retained cases and the
recoverable archive location. Current scripts select only the retained cases.
Historical KB citations inside completed prompts are not removed or rewritten.
Neither original CSVs nor KBs were deleted. Old dry runs, synthetic images, legacy
five-trial results, excluded case inputs/results and the no-longer-needed resume
utility were moved outside the active benchmark, with SHA-256 verification.

## Necessary scripts

- common.py: active run selection and deterministic serialization/checksums.
- prepare_inputs.py: all-file raw summaries plus anomaly/context/filtered KB.
- run_study.py: independent identical requests and semantic comparison report.
- render_signatures.py: offline reports and figures from cited evidence.
- test_raw_consistency.py: offline tests, synthetic data in temporary directories.

Preparation defaults to the three retained cases. Input compression and the model
request schema are unchanged. Existing diagnoses were not regenerated.

## Offline commands

From the repository directory, run unit tests without a real API request:

```bash
python3 -m unittest discover -s benchmarks/novel/raw_consistency -p 'test_*.py'
```

Inspect serializer compatibility for a new three-case study without API calls:

```bash
python3 benchmarks/novel/raw_consistency/run_study.py \
  --inputs benchmarks/novel/raw_consistency/inputs/bundle_20260910T230921Z \
  --model-alias sol --trials 3 --max-input-tokens 950000
```

To rebuild retained reports/figures offline:

```bash
python3 benchmarks/novel/raw_consistency/run_study.py \
  --report-only benchmarks/novel/raw_consistency/results/study_20260910T233752Z_e8027ad4
```

The report's semantic_review.json supports human grouping. Empty groups mean
pending review, not inconsistency. Existing presentation assessments do not
silently populate human-review fields. The slide notes preserve cited evidence
and distinguish semantic agreement from root-cause correctness.

Adding --execute to a new-study command would make nine new paid requests. Do
not do this just to view existing results. No resume is necessary: 9/9 retained
trials already completed. Archived scripts are audit records, not active entrypoints.
