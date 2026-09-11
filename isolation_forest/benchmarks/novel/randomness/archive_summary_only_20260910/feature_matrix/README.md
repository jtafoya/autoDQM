# Phase 1 offline feature-matrix supplement

This supplement visualizes **observed signature** and **LLM-mentioned evidence**.
It does not diagnose new data, infer internal model attribution, use ground truth,
or call an LLM. See [feature_matrix_summary.md](feature_matrix_summary.md) and
[validation.md](validation.md).

## Regenerate

```bash
cd /afs/cern.ch/user/p/pengy/autoDQM/isolation_forest
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/novel/randomness/feature_matrix/build_feature_matrices.py --workers 2
```

The default regenerates all six runs in this supplement directory. To regenerate
only layout, use `--stage render`. To re-extract deterministic text mentions and
redraw without recomputing detector matrices, use `--stage mentions`. To collect
only detector matrices and text records, use `--stage collect`.
`--runs 1640` limits work to that run; omit `--runs` for the final six-run summary.
`--workers` is restricted to 1-4 and defaults to 2.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s benchmarks/novel/randomness/feature_matrix -p test_feature_matrices.py -v
```

Python IPv4/IPv6 socket connections are blocked during the generator. Mounted
AFS/EOS files are read normally. The generator never imports an LLM adapter,
loads KB annotations or submits a job to an LLM service. All source Phase 1
files and manifests are hashed before/after processing and must remain unchanged.

## Source fidelity

The source campaign is `kb_task1_runs1500_3000_juan_v1`; model/reference paths and
SHA256 come from its `campaign_metadata.json`. The source implementation hashes
for features, reference, detector and plotting must match that campaign.
The saved detector supplies the threshold and the saved reference supplies all
feature extraction flags. `src.features.extract_features()` and
`ReferenceModel.z_score()` are called directly with the exact production argument
list. `src.plot._channel_order()` supplies channel order; `_feat_cols` supplies
feature order. No feature matrix formula is reimplemented.

For this particular campaign: 96 digitizer channels, 29 features, `ignore_features`
contains `TDC*`, Trigger/LVDS features OFF, trigger-config normalization/masking
OFF, DAQ-config flag ON (the existing extractor applies no DAQ normalization).
There are consequently no pseudochannels in this model's matrix. They must not
be added merely because the LLM received separate contextual summaries.
Threshold is **strict |z| > 8**, read from the saved detector, not hard-coded.

All declared detector subruns plus any additional matching subruns in the same
source directories are considered. Subruns found in frozen logs but missing from
the manifest are also accounted for. Duplicate run/subrun paths are rejected.
Each input file's SHA256/status is preserved. Read errors, missing files and
empty/all-undefined inputs are listed rather than turned into zero matrices.

The signed z cube is stored before aggregation. Maximum absolute z remains
unclipped; frequency uses a separate finite-value count for each cell. NaN cells
remain NaN in both outputs. Missing-channel counts are separate from z, because
the original detector treats missing channels as their own state. These figures
show the statistical feature matrix, not isolation-forest feature importance.

## Mention rules

The exact saved study is `study_20260906T044011Z_7ac63c5a`. Each of its 30 parsed
responses is checked against text extracted from its saved raw response.

- Exact channel IDs and exact known feature names receive separate lexical
  mention records. A response contributes at most one count per item.
- Quote records retain the original field, trial, verbatim sentence, and scope:
  observed section, inference/unknown, recommended check, or unscoped hypothesis.
- Sentences explicitly referencing historical runs/history are preserved but
  excluded from target-specific labels and cell overlays. This is a conservative
  textual filter, not a semantic resolver; inspect quotes for ambiguous cases.
- Context terms are deterministic patterns defined in `CONTEXT_TERMS`. The
  `trigger mask` item accepts explicit mask/masked/masking language. The readout
  item requires readout plus fault/failure/loss/dropout/disruption/interruption.
  Category underscores are word separators for these context phrases. Generic
  restart language is labeled as proposed/hypothesized restart, not automatically
  as a DAQ restart.
- Cell borders require an exact feature and a directly related single channel
  in the target OBSERVED section: adjacency, feature on/for/in channel, or
  channel has/shows/exhibits/across a feature list. Intervening channel references
  and contrast markers prevent a binding. Generic pulse-count/height language is
  not expanded into specific features. Channel lists are not cross-multiplied
  with feature lists. Ambiguous text remains a note or axis label.
- Observed-section counts do not assert that a statement is positive or correct:
  negation and unavailable measurements remain verbatim. Other-field mentions
  can be hypotheses or proposed checks, not supplied observations.

Orange `[n]` on a row/column label denotes a text mention in n of five trials.
Orange cell borders denote an explicit linked target observation. The CSV gives
its exact 0-5 trial count. Neither symbol claims that the model internally used
that feature. No new physics classifier, taxonomy, or semantic consistency rate
is generated; cause-stability prose summarizes the saved categories.

## Exact output inventory

Top-level files:

- `build_feature_matrices.py`
- `render_feature_matrices.py`
- `test_feature_matrices.py`
- `README.md`
- `feature_matrix_summary.md`
- `validation.md`
- `provenance.json`

For each N in **1620, 1640, 1642, 1702, 1703, 2126**, directory `runN/` contains:

- `runN_feature_matrix.png`
- `runN_feature_matrix.pdf`
- `runN_matrix_max_abs_z.csv`
- `runN_matrix_anomaly_frequency.csv`
- `runN_matrix_valid_subrun_count.csv`
- `runN_matrix_exceedance_count.csv`
- `runN_llm_mentions.csv`
- `llm_mention_quotes.csv`
- `subrun_coverage.csv`
- `channel_coverage.csv`
- `subrun_z_matrices.npz`
- `phase1_predictions.json`
- `phase1_source_hashes.json`
- `metadata.json`

Additional selected-subrun validation files:

- `run1640/validation/canonical_subrun_zscore_heatmap.png`
- `run1640/validation/canonical_subrun_signed_z.csv`

PNG is a 4800 x 4000 pixel presentation figure; PDF preserves selectable text
and vector labels/markers. Both use the same full matrix, feature ordering, and
shared nonlinear maximum-z color scale. The maximum CSV is not display-clipped.

Regeneration overwrites only this supplement's generated outputs. Existing
Phase 1 request/response files, KB, manifests and production source are unchanged.
