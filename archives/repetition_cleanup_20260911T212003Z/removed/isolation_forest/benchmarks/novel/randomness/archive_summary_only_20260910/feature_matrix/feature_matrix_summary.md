# Phase 1: observed matrices and LLM-mentioned evidence

Offline visualization from the frozen campaign model and existing five responses per run. Mentions are deterministic text matches, not internal model attribution. No new API calls or ground truth are used.

| Run | Main observed signature | Repeated LLM-mentioned evidence | Cause stability |
|---|---|---|---|
| 1620 | 259/259 subruns have defined z values; 0 missing/empty/no-z. 0 cells exceed |z|>8 in at least 80% of their valid subruns. Most persistent cells (not a cause ranking):   ch9 / nPulses_median: 2.7%; max 9.32; n=259.   ch65 / nPulses_median: 1.2%; max 13.1; n=259.   ch20 / nPulses_median: 1.2%; max 11.2; n=259. | restart (proposed or hypothesized): 5/5; board matching: 5/5; trigger rate: 5/5; LVDS: 5/5 | DAQ transient/restart direction recurs; the concrete cause remains unknown. |
| 1640 | 741/741 subruns have defined z values; 0 missing/empty/no-z. 3 cells exceed |z|>8 in at least 80% of their valid subruns. Most persistent cells (not a cause ranking):   ch32 / occupancy: 99.8%; max 54.2; n=519.   ch32 / pulseHeight_max_std: 81.7%; max 15.2; n=519.   ch33 / occupancy: 81.1%; max 47.4; n=519. | configuration: 5/5; readout failure/dropout (hypothesis or check): 3/5; trigger mask: 5/5; missing-channel behavior: 5/5; restart (proposed or hypothesized): 3/5; LVDS: 5/5; board matching: 5/5 | Trials 1/3 emphasize channel-pair readout faults; trial 2 retains suppression/readout alternatives; trials 4/5 emphasize mask/config mismatch. |
| 1642 | 202/202 subruns have defined z values; 0 missing/empty/no-z. 10 cells exceed |z|>8 in at least 80% of their valid subruns. Most persistent cells (not a cause ranking):   ch32 / nPulses_median: 100.0%; max 179; n=2.   ch32 / nPulses_mean: 100.0%; max 154; n=2.   ch32 / nPulses_std: 100.0%; max 79.9; n=2. | LVDS: 5/5; LVDS pin16: 5/5; missing-channel behavior: 5/5; trigger mask: 5/5; configuration: 5/5; trigger rate: 5/5; board matching: 5/5 | All five categories describe localized LVDS signal loss; the physical root cause remains qualified. |
| 1702 | 129/129 subruns have defined z values; 0 missing/empty/no-z. 186 cells exceed |z|>8 in at least 80% of their valid subruns. Most persistent cells (not a cause ranking):   ch78 / pulseHeight_max_median: 100.0%; max 376; n=129.   ch93 / pulseHeight_min_median: 100.0%; max 342; n=129.   ch93 / pulseHeight_max_median: 100.0%; max 303; n=129. | trigger rate: 5/5; LVDS: 5/5; configuration: 5/5; board matching: 5/5; readout failure/dropout (hypothesis or check): 3/5; restart (proposed or hypothesized): 5/5; missing-channel behavior: 3/5 | Broad digitizer/processing/configuration/reference hypotheses recur, without one resolved mechanism. |
| 1703 | 627/627 subruns have defined z values; 0 missing/empty/no-z. 191 cells exceed |z|>8 in at least 80% of their valid subruns. Most persistent cells (not a cause ranking):   ch93 / pulseHeight_min_median: 100.0%; max 1.74e+03; n=627.   ch93 / pulseHeight_max_median: 100.0%; max 491; n=627.   ch78 / pulseHeight_max_median: 100.0%; max 437; n=627. | configuration: 5/5; board matching: 5/5; restart (proposed or hypothesized): 5/5; LVDS: 5/5; trigger rate: 5/5 | A global waveform-feature/configuration/reference interpretation recurs; the mechanism remains unresolved. |
| 2126 | 86/86 subruns have defined z values; 0 missing/empty/no-z. 0 cells exceed |z|>8 in at least 80% of their valid subruns. Most persistent cells (not a cause ranking):   ch15 / nPulses_median: 15.1%; max 19.7; n=86.   ch9 / nPulses_median: 14.1%; max 9.32; n=85.   ch69 / nPulses_median: 14.0%; max 1e+06; n=86. | readout failure/dropout (hypothesis or check): 5/5; configuration: 4/5; missing-channel behavior: 5/5; restart (proposed or hypothesized): 5/5; trigger rate: 5/5; LVDS: 5/5 | All five categories favor digitizer/DAQ readout loss, with the concrete cause left uncertain. |

## Matrix definition and coverage

The original model contains 96 digitizer channels and 29 ordered features. Trigger/LVDS and trigger-config normalization/masking are disabled in this campaign. No pseudochannels are added. The z threshold is read from detector.pkl and checked against frozen training metadata (8 here; strict >). The reference's original standard-deviation floor of 1e-6 is retained, so very large z values remain possible.

Max |z| is computed without clipping. Anomaly frequency divides cell exceedances by that cell's finite-z subruns, not by all run files. Undefined cells are blank in numeric CSVs and grey in figures. Per-cell denominators, exceedance counts, channel-presence coverage and all per-subrun z arrays are exported.

Run2126 saved Trigger/LVDS context covers subruns 1-40, whereas its IF report covers 86 subruns. The matrices use all available detector subruns. Coverage limitations must not be interpreted as proof of globally normal telemetry.

## Reading the text markers

Orange channel/feature labels show per-trial explicit mentions, excluding sentences containing explicit historical-run references. These text counts may include inferred hypotheses and proposed checks; the quote CSV preserves field, scope, trial and verbatim text. Observed-only counts are separate. Cell borders require direct exact feature/channel syntax in target OBSERVED text. Mere sentence co-occurrence, generic pulse statistics, pin-to-channel inference and feature-only/channel-only references never produce a cell overlay. A zero cell-link count means no unambiguous link was extracted, not that the model ignored the feature.

Observed-section counts are lexical mentions within the saved OBSERVED section, not a positivity or correctness judgment: negated statements and unavailable telemetry are retained as quoted. Category underscores are treated as word separators for context phrases only. Recognized cell bindings include direct adjacency, feature-on-channel, and single-channel has/shows/exhibits/across constructions with an exact feature name and no intervening channel.

Missing-channel behavior is a separate detector state, not a z-matrix feature. Cause stability text summarizes the existing saved categories; no new physics taxonomy or automatic semantic classifier is introduced.

## Files and regeneration

Each run directory contains the requested PNG/PDF, maximum/frequency/mention CSVs, plus valid-subrun and exceedance matrices, subrun/channel coverage, signed-z NPZ, quoted mentions, copied saved predictions and metadata.

```bash
cd /afs/cern.ch/user/p/pengy/autoDQM/isolation_forest
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/novel/randomness/feature_matrix/build_feature_matrices.py --workers 2
```

For layout-only regeneration from saved matrices, append `--stage render`.
