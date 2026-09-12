# Frozen input bundle prepared on 2026-09-10

Absolute lxplus bundle directory:

`/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/benchmarks/novel/raw_consistency/inputs/bundle_20260910T230921Z`

All paths below are relative to that directory. Each run has the same file layout.

| Run | Raw CSV files | Raw rows | Summary subdirectory | Serialized request UTF-8 bytes* |
| --- | ---: | ---: | --- | ---: |
| 1620 | 259 | 2,557,872 | `run1620/` | 857,777 |
| 1640 | 741 | 7,144,357 | `run1640/` | 875,128 |
| 1642 | 202 | 1,959,578 | `run1642/` | 853,621 |
| 1702 | 129 | 479,078 | `run1702/` | 869,142 |
| 1703 | 627 | 2,327,600 | `run1703/` | 938,147 |
| 2126 | 86 | 422,227 | `run2126/` | 858,857 |
| Total | 2,044 | 14,890,712 | | |

*Conservative size check, NOT measured token usage. These sizes include the
structured-output schema and all evidence. Use the explicit 950000 guard in the
validated command. No original CSV rows are uploaded directly.

For example, run1640:

- Exact raw-derived model evidence plus other evidence:
  `run1640/evidence.jsonl` (R/P records are raw-derived).
- Definitions, histogram boundaries, temporal bins:
  `run1640/summary_header.json`.
- All-subrun channel/metric numerical detail: `run1640/raw_detail.npz`.
- Every original source path and hash: `run1640/raw_inventory.json`.
- Full aggregate anomaly summary: `run1640/anomaly_summary.json`.
- Full original anomaly log for audit: `run1640/anomaly_log.csv`.
- Context / filtered KB: `run1640/context.json`, `run1640/filtered_kb.json`.
- Artifact/source hashes and exclusions: `run1640/manifest.json`.

The bundle is 122 MiB on disk. The original inputs total 1,412,709,688 bytes.
Do not edit the frozen bundle to revise the experiment. Generate a new bundle.

## Ready-to-run command on lxplus

With your API key already set privately in the terminal:

```bash
cd /afs/cern.ch/user/p/pengy/autoDQM/isolation_forest
AUTOFLAME_SOL_MODEL=gpt-5.6-sol python3 benchmarks/novel/raw_consistency/run_study.py \
  --inputs /afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/benchmarks/novel/raw_consistency/inputs/bundle_20260910T230921Z \
  --model-alias sol --trials 3 --max-input-tokens 950000 --execute
```

Remove `--execute` for a no-network dry-run. Preparation has already finished;
there is no need to reread/rebuild the raw summaries for this test.

The command prints the results directory under
`/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/benchmarks/novel/raw_consistency/results/`.
Each completed trial has `diagnosis_report.md`, `diagnosis.json`,
`signature_records.json`, `signature_audit.json` and `signature_images/`.
See README.md for human semantic grouping and the offline report-only command.

## Legacy results

Remote recoverable archive:

`/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/benchmarks/novel/randomness/archive_summary_only_20260910`

Local recoverable archive:

`/Users/branchinpyjamas/Documents/AutoFLAME/artifacts/archive_summary_only_20260910`

794 remote and 100 local files were moved and their SHA-256 values verified.
No permanent deletion. The archive manifest maps old paths to new paths.
