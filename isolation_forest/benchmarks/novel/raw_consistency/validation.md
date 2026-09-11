# Offline validation — 2026-09-10

No real diagnosis API calls were made. Paid execution is left to the user.

## Input preparation

Bundle: `inputs/bundle_20260910T230921Z/`.
All 2,044 CSVs / 14,890,712 rows were processed, with two full read passes and
matching per-file hashes. All 96 channels and all 11 measurement columns are
represented for each run, including absent channels and nonfinite values.
The empty interrupted development bundle is isolated under
`validation_artifacts/development_archive/`, not accepted as a prepared bundle.

Independent validation (not just comparing a table to itself):

- Direct pandas calculations from each run's first, middle and last CSV,
  channels 0/32/33/95, every metric: mean, median, rows and unique events agree
  with saved detail arrays (numerical tolerance 1e-12).
- Raw detail row totals equal the source inventory row counts.
- Histogram counts reconcile with finite raw counts for every channel/metric.
- Presence counts reconcile with every file's channel rows.
- Anomaly overview counts agree with the original frozen anomaly-log flags.
- No top-N channel filter; existing semicolon-delimited feature names are
  individually counted. Unit fixture covers the delimiter.
- Established KB family exclusions and context provenance sanitization reused.
  Ground truth and legacy predictions are absent from the model input.

Representative presence checks: run1640 channel32/33 occur in 519/741 files;
run1642 channel32/33 occur in 2/202; run2126 in 85/86. Absence is distinct from a
zero-valued measurement. No missing subrun is interpolated into measurements.

`validation_artifacts/validation_results.json` records each run's counts and
conservative input bounds. `INPUT_LOCATIONS.md` identifies all generated files.

## Requests and tests

Final dry-run: `results/dry_run_20260910T232003Z_b035e27f/`.

- 18/18 requests serialized through the SDK with network-blocking MockTransport.
- Every run's three wire request bodies have the same SHA-256.
- Network attempts: zero. No fabricated diagnosis reports in the dry-run.
- All six inputs pass the explicit 950000 UTF-8 byte upper-bound guard. The
  original default 900000 guard correctly stopped run1703 during an earlier
  preflight, before creating a study or attempting any request. No truncation.
- An intentionally wrong expected wire hash stopped before network transmission.
- 10 unittest tests passed: statistics/NaN/zero, all-file histogram/presence,
  numeric subrun order, all-channel anomaly aggregation, exact citation checks,
  guard rejection, dry-run isolation, mocked success/error/no-retry, semantic
  grouping versus wording, and distribution/presence/link rendering.
- Mock response tests use a dummy key and HTTP mock transport, not an API.

The renderer was adjusted for the existing lxplus Matplotlib coordinate-label
API and retested. This was a rendering-only compatibility patch; frozen input
artifacts and request content did not change. Input manifests record the source
snapshot at preparation time; the final dry-run study_config records the final
runner/renderer/test code hashes. These snapshots need not be identical for
rendering-only code, but the three actual requests within each run are identical.

## Figures

`validation_artifacts/SYNTHETIC_ONLY_run1640_trial1/` is a deliberately synthetic
pipeline fixture using real supplied evidence values. It is NOT a model result.
Its overview, evidence-link, histogram/time and presence/occupancy images were
rendered and visually checked. Each image title labels the synthetic test.
The figures have readable labels, preserve no-data gaps and show no unrelated
zmax attribution matrix. All cited raw R/P records are plotted, not a selected
cross product. The exact references and stated links also remain machine-readable.

Citation validation establishes that IDs/fields/values match the input, not
that a causal interpretation is correct. Semantic consistency remains pending
human review until the reviewer groups equivalent meanings; wording differences
are not automatically counted as inconsistent diagnoses. No accuracy scoring.

## Scope and archive

No production pipeline, KB, configuration, anomaly source or original raw CSV
was edited. New study code/artifacts are under `benchmarks/novel/raw_consistency/`.
Legacy result/visualization directories were moved to a recoverable archive and
the legacy README was marked superseded. Every archived file hash was verified.
No git commit, push, new LLM study, or permanent deletion was performed.
