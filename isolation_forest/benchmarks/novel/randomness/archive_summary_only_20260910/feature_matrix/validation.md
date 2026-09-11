# Validation and run1640 reading

Validated on lxplus948, 2026-09-08. This is offline post-processing of the
completed Phase 1 study. New LLM API calls: **0**. Ground-truth annotations
loaded or used for feature selection: **none**.

## Numerical fidelity

Model/reference SHA256 and production `features.py`, `reference.py`,
`detector.py`, `plot.py` hashes match the frozen campaign metadata.
The stored detector and training configuration agree on `z_threshold=8`, with
the same strict `>` test as production.

| Run | Detector subruns available | Valid subruns aggregated | Missing/empty/no-z inputs | Frozen subrun logs compared | Mismatches |
|---|---:|---:|---:|---:|---:|
| 1620 | 259 | 259 | 0 | 259 | 0 |
| 1640 | 741 | 741 | 0 | 741 | 0 |
| 1642 | 202 | 202 | 0 | 202 | 0 |
| 1702 | 129 | 129 | 0 | 129 | 0 |
| 1703 | 627 | 627 | 0 | 627 | 0 |
| 2126 | 86 | 86 | 0 | 86 | 0 |
| Total | 2044 | 2044 | 0 | 2044 | 0 |

For every available subrun, recomputed per-channel maximum z values (at the
frozen log's two-decimal precision) and triggered feature lists match the existing
anomaly log. The full unrounded values remain in the signed-z archives.

For run1640/subrun1, validation actually invokes `src.plot.plot_file()` with the
frozen detector, captures its first heatmap array and compares it against the
same subrun's new z matrix after applying only the existing plot's 50-sigma display
clip. **2,784 cells compared, exact equality, maximum difference 0.0.**
The captured canonical heatmap and unrounded signed-z CSV are retained under
`run1640/validation/`. The old June `plots/local_smoketest` PNG is not used as an
unverified same-model reference; the frozen campaign's values and canonical
plot function are the validated reference.

Every run's stacked-array aggregation was checked against an independent
streaming accumulation: maximum, denominator and exceedance numerator agree
exactly; frequency agrees with numerator/denominator and stays within [0,1].
Zero-denominator cells are NaN in both derived matrices. No maximum clipping
occurs in aggregation or numeric export.

Six focused offline tests pass: NaN denominators and strict threshold, unclipped
maximum, no channel-feature Cartesian expansion, exact target-observation link,
historical/action exclusions for cell overlays, and underscore-separated category
phrase handling. These tests use no network or LLM.

## Manual run1640 mention validation

The five complete saved responses were inspected. Counts below are trial-level
explicit mentions, not hidden attribution or a diagnosis correctness score.

| Item | Text mention trials | Observed-section trials | Handling |
|---|---|---|---|
| channel32 | 1,2,3,4,5 | 1,2,3,4,5 | row label |
| channel33 | 1,2,3,4,5 | 1,2,3,4,5 | row label |
| exact feature occupancy | 1,2,3,4,5 | 1,2,3,4,5 | column label |
| channel32 + occupancy | 1,2,3,4,5 | 1,2,3,4,5 | one cell border, 5/5 |
| trigger mask / masked language | 1,2,3,4,5 | 1,2,3,4,5 | text note; not a matrix feature |
| missing-channel behavior | 1,2,3,4,5 | 1,2,3,4,5 | text note and separate objective coverage |
| readout fault/failure/dropout phrase | 1,2,3 | none | hypothesis/check text note |
| explicit LVDS pin16 | 2 | none | proposed-check note; no inferred cell |

The five direct channel32/occupancy links in `reasoning_summary` are:

1. "channel 32 has extreme baseline, pulse-count, pulse-height, and occupancy deviations"
2. "channel 32 has extreme pulse, occupancy, and sideband deviations"
3. "dominated by channel 32 across baseline, pulse-count, pulse-height, and occupancy features"
4. "channel 32 has extreme deviations in occupancy, pulse count, baseline, and pulse-height features"
5. "channel 32 has repeated extreme deviations in occupancy, pulse count, pulse-height, and sideband features"

Full verbatim sentences and their field/scope/trial remain in
`run1640/llm_mention_quotes.csv`. There is **no inferred channel33/occupancy cell
overlay**: mentioning channel33 elsewhere does not license that binding.
Likewise, general pulse-height language does not become `pulseHeight_max_std`.

## Run1640: observed matrix plus explicit mentions only

Both ch32 and ch33 are absent in **222/741** detector subruns. Their valid-cell
denominator is **519**, rather than 741. In those valid subruns:

| Cell | Max absolute z | Above-threshold / valid | Anomaly frequency |
|---|---:|---:|---:|
| ch32 / occupancy | 54.1585 | 518 / 519 | 99.8073% |
| ch33 / occupancy | 47.4171 | 421 / 519 | 81.1175% |
| ch32 / pulseHeight_max_std | 15.2021 | 424 / 519 | 81.6956% |
| ch33 / pulseHeight_max_std | 15.3364 | 355 / 519 | 68.4008% |
| ch32 / nPulses_median | 39.6874 | 254 / 519 | 48.9403% |

The frequency matrix isolates a persistent channel-pair signature, while the
maximum matrix also displays transient large deviations elsewhere. Repeated
LLM mentions of channels32/33 and occupancy correspond to that visible signature.
The exact occupancy cell link is supported for channel32; other general feature
phrases remain unexpanded notes.

The five categories still differ: trials1/3 emphasize readout faults, trial2
retains suppression/readout alternatives, and trials4/5 emphasize mask/config
mismatch. Mask language is repeated in every response, but is **not proof of
that cause**. This frozen IF model does not apply trigger-config masking at all.
Neither the matrix nor mention frequency establishes a physical root cause.

## Coverage and interpretation limits

All available detector subruns are represented. Saved Phase 1 context is reused
only as coverage metadata: for run2126, Trigger/LVDS spans **subruns1-40**, while
the detector matrices and frozen IF report cover **86 subruns**. The figure calls
this out explicitly. It does not extrapolate those context summaries to all86.

No new telemetry was fed to the LLM. No production code, KB, manifests, saved
Phase 1 responses or prompt was modified. The plots show feature-level statistical
deviations, not isolation-forest attribution and not a validated cause label.

## Artifact checks

All six final PDFs were rendered with Poppler and visually inspected, including
axis-label readability, marked cells, notes, diagnosis text and footer separation.
Each PDF has exactly one page and retains selectable required labels; each PNG
is 4800 x 4000 pixels. A preliminary note/footer collision was corrected before
the final six-file render. The final model/source/manifest/KB hashes are unchanged.
Remote git status shows only the new `benchmarks/novel/randomness/feature_matrix/`
directory. It contains 93 files, enumerated by the exact patterns in README.md.
