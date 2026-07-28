# Run 2014 detailed diagnosis

## Scope and authoritative inputs

This analysis uses only the successfully reproduced Juan model, its combined
channel-level log, the successful processed-file cache, and the authoritative
Step-1 classification. It does not retrain, change thresholds, inspect ROOT
waveforms, or analyze runs 2088/2089.

- Model tag: `juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig`
- Channel log: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/logs/juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig.csv`
- Processed order: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/logs/juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig_paths.txt`
- Step-1 classification: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/analysis/juan_bad_run_diagnosis/step1_classification/subrun_classification.csv`
- Model directory: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/models/juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig/`

All new outputs are under:

`/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/analysis/juan_bad_run_diagnosis/run2014/`

## Executive conclusion

Run 2014 is **not primarily a persistence-alert problem**. Of 71 strict ALERTs,
48 (67.6%) involve the extreme-z condition, 25 (35.2%) involve bulk, and only
6 (8.5%) involve persistence. The exclusive decomposition is:

| Alert combination | Count | Fraction of 71 |
| --- | ---: | ---: |
| Extreme only | 40 | 56.3% |
| Bulk only | 18 | 25.4% |
| Persistent only | 5 | 7.0% |
| Bulk + extreme | 7 | 9.9% |
| Persistent + extreme | 1 | 1.4% |
| Persistent + bulk | 0 | 0% |
| Persistent + bulk + extreme | 0 | 0% |

The evidence separates into two related but distinct model-level patterns:

1. **A stable IF-dominated background on ch82 and ch3.** They are anomalous in
   225/361 (62.3%) and 185/361 (51.2%) sampled files, respectively. They are
   the persistent pair in all six persistence ALERTs and participate in most
   bulk-only ALERTs.
2. **Distributed transient statistical extremes across many other channels.**
   The extreme condition is overwhelmingly associated with
   `nPulses_median`: it appears in 49 extreme channel rows spanning 44/48
   extreme ALERT files and 19 different channels.

Thus the reduced non-ALERT fraction is a mixture: frequent ch82/ch3
multivariate IF anomalies help create WARNs and bulk events, while most strict
ALERTs are actually caused by isolated high-z pulse-count deviations on a
broader set of channels.

## 1. Temporal distribution

WARN/ALERT activity is strongly enriched after the first quarter of the
processed run, but it is not one continuous ALERT interval:

| Processed quarter | OK | WARN | ALERT |
| --- | ---: | ---: | ---: |
| Sequence 0–90 | 81 | 4 | 6 |
| Sequence 91–180 | 50 | 15 | 25 |
| Sequence 181–270 | 44 | 27 | 19 |
| Sequence 271–360 | 38 | 31 | 21 |

- There are 51 separate ALERT episodes.
- The longest uninterrupted ALERT episode is only 4 processed files.
- 34/51 ALERT episodes are isolated single-file ALERTs.
- WARNs form 30 episodes; the longest WARN episode is 9 files.
- The longest uninterrupted non-OK region is 23 processed files
  (sequence 218–240, sampled subruns 570–624), containing 19 WARN and 4 ALERT.
- The first ALERT occurs at sequence 1/subrun 3 and the last at
  sequence 360/subrun 902.

The best description is **dispersed isolated events and short bursts, with
increasingly dense WARN/ALERT activity in the later run**, rather than a single
continuous bad period.

## 2. Primary alert condition

The dominant mechanism is **extreme z**, followed by bulk. Persistence is a
minor direct contributor.

- Extreme involved: 48/71 (67.6%)
- Bulk involved: 25/71 (35.2%)
- Persistence involved: 6/71 (8.5%)

Multiple flags can fire together, so the simple percentages do not sum to
100%. The mutually exclusive table above accounts for all 71 ALERTs exactly.

## 3. Dominant channels

### Frequent anomalous channels

| Channel | Anomalous files | ALERT files anomalous | WARN files anomalous | OK files anomalous | Longest streak | Max z |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 82 | 225 (62.3%) | 49 | 75 | 101 | 27 | 9.85 |
| 3 | 185 (51.2%) | 48 | 49 | 88 | 8 | 11.23 |
| 7 | 23 (6.4%) | 10 | 2 | 11 | 1 | 45.76 |
| 15 | 20 (5.5%) | 9 | 3 | 8 | 2 | 19.70 |
| 22 | 17 (4.7%) | 9 | 3 | 5 | 1 | 47.63 |
| 26 | 10 (2.8%) | 9 | 1 | 0 | 1 | 16.07 |

ch82 and ch3 clearly dominate anomaly frequency, but neither reaches the
extreme threshold. Their role is persistent/bulk participation:

- All 6 persistence ALERTs have exactly `3;82` as the persistent channel set.
- ch82 participates in 22/25 bulk ALERTs and 17/18 bulk-only ALERTs.
- ch3 participates in 21/25 bulk ALERTs and 14/18 bulk-only ALERTs.

### Channels directly triggering extreme ALERTs

The largest repeat extreme contributors are ch26 (7 files), ch0 (6), ch15
(5), ch13 (5), ch27 (3), and ch34 (3). Additional extreme triggers are spread
across many channels. This is not a single-channel extreme-z failure.

One representative file, subrun 168, contains a ch4 `max_z` of 1,000,000. That
value is faithfully present in the log and plot, but its physical meaning
cannot be established from the log alone; it particularly warrants checking
for a zero-width reference feature, missing/degenerate input, or a genuine
event-level pulse-count excursion before assigning a detector cause.

## 4. Do WARN and ALERT share the same channels?

**Partly, but not completely.**

- ch82 and ch3 are the top two channels in both WARN and ALERT anomaly counts.
- Only 2 of the top 5 WARN channels are also in the top 5 ALERT channels:
  ch82 and ch3.
- Across all channels, WARN-versus-ALERT anomaly frequency has Spearman
  correlation 0.742, indicating substantial but imperfect overlap.

WARNs are therefore strongly associated with the recurring ch82/ch3 pattern.
ALERTs retain that background, especially in bulk events, but add a different
population of high-z statistical anomalies across many other channels.

## 5. Dominant features

Across 794 anomalous channel rows:

- No individual z-threshold feature (`<none; IF-only>`): 441/794 (55.5%)
- `nPulses_median`: 151/794 (19.0%)
- `sideband_rms_mean`: 38/794 (4.8%)
- `nPulses_std`: 36/794 (4.5%)
- `pulseDuriation_min_mean`: 33/794 (4.2%)

Within the 259 anomalous rows belonging to ALERT files:

- IF-only: 106/259 (40.9%)
- `nPulses_median`: 80/259 (30.9%)

For the rows that directly satisfy `max_z >= 15`, the attribution is much
sharper:

- `nPulses_median`: 49 extreme channel rows, present in 44/48 extreme ALERT
  files, across 19 channels
- `sideband_mean_median`: 3 rows
- `nPulses_mean`: 1 row
- `sideband_rms_mean`: 1 row

Therefore **`nPulses_median` is the dominant extreme-alert feature**, while
IF-only multivariate deviations dominate the larger background population.

## 6. Channel × feature stability

The two frequent channels are repeatedly flagged in a stable way:

- ch82: 213/225 anomalous rows (94.7%) are IF-only; 12 involve
  `pulseDuriation_max_median`.
- ch3: 156/185 anomalous rows (84.3%) are IF-only; 29 involve
  `pulseDuriation_min_mean`, with only a few other features.

So ch82/ch3 mostly repeat the **same detection mode** (IF-only), rather than
cycling randomly through many z-trigger features. Other alert-driver channels
show more channel-specific statistical features; for example, 9/10 anomalous
ch26 rows and 9/14 anomalous ch13 rows trigger `nPulses_median`.

## 7. Statistical layer versus Isolation Forest

Overall anomalous rows:

- Isolation-Forest-only: 441/794 (55.5%)
- Statistical-only: 294/794 (37.0%)
- Statistical + IF: 59/794 (7.4%)

WARN anomalous rows:

- IF-only: 133/197 (67.5%)
- Statistical-only: 57/197 (28.9%)
- Both: 7/197 (3.6%)

ALERT anomalous rows:

- Statistical-only: 122/259 (47.1%)
- IF-only: 106/259 (40.9%)
- Both: 31/259 (12.0%)

All rows directly exceeding `max_z >= 15` involve the statistical layer
(44 statistical-only and 9 statistical+IF extreme rows). Thus the broad
anomaly background is mostly IF-only, but strict ALERT files shift toward the
statistical layer.

## 8. Single systematic problem, multiple problems, or random fluctuations?

The current evidence supports **at least two model-visible components**, not
purely random unrelated fluctuations and not a single proven detector fault:

1. A systematic, long-lived multivariate deviation on ch82/ch3.
2. Short-lived, distributed `nPulses_median` extremes across many channels,
   plus bulk events in which ch82/ch3 frequently participate.

The temporal enrichment later in the run argues against uniform independent
sampling noise. However, the evidence does not establish whether these two
components share one underlying run condition or have separate physical
causes.

## 9. Most specific responsible conclusion from current evidence

The responsible model/log-level conclusion is:

> Run 2014 has a stable IF-only anomaly pattern dominated by ch82 and ch3,
> producing most WARNs and contributing heavily to bulk events. Its 71 strict
> ALERTs are nevertheless dominated by transient extreme statistical
> deviations, chiefly `nPulses_median`, distributed across many other
> channels. Activity is increasingly dense later in the run but occurs as
> isolated events and short bursts.

This is sufficient to identify the detector-model signatures responsible for
the reduced non-ALERT fraction. It is **not sufficient to identify a hardware
cause**.

## 10. Exact next raw-data check, if needed

The highest-value next check would be an event-level pulse multiplicity and
occupancy comparison using the exact representative files and their nearest
processed neighbors:

1. Inspect ch4 in subrun 168 (`max_z = 1,000,000`), ch38 in subrun 902
   (`max_z = 67.36`), and ch66 in subrun 3 (`max_z = 21.11`).
2. For each, compare the event-by-event pulse-count distribution, number of
   events, zero/empty fraction, and channel occupancy with adjacent sampled
   files and the representative OK subrun 94.
3. Separately compare the full feature vectors and event-level occupancy for
   ch82/ch3 in representative WARN subrun 605 against OK subrun 94 and adjacent
   processed files.
4. Verify the corresponding DAQ threshold/config values before interpreting
   any change as detector hardware behavior.

This would directly test whether the `nPulses_median` extremes and ch82/ch3 IF
shift reflect real event-level distributions, missing/degenerate inputs, or
configuration-linked changes. No such raw-data inspection was performed here.

## Representative subruns

| Subrun | Status | Selection reason |
| ---: | --- | --- |
| 94 | OK | Modal anomaly count, near median severity/sequence |
| 605 | WARN | Modal anomaly count, near median severity/sequence |
| 3 | ALERT | First strict ALERT |
| 902 | ALERT | Largest anomalous-channel count among remaining ALERTs |
| 168 | ALERT | Largest max-z among remaining ALERTs |

Each has canonical z-score heatmap, max-z channel plot, IF-score channel plot,
and detector geometry plot under `representative_subruns/`.

## Sanity checks

- Exactly 361 successfully processed run-2014 subruns: passed.
- Status totals 213 OK / 77 WARN / 0 PEND / 71 ALERT: passed.
- Alert flags reproduce Step-1 strict ALERT exactly: passed.
- Timeline order exactly matches the successful processed-path cache: passed.
- Persistence begins only from the fifth processed file and is confined to
  run 2014: passed.
- All statistics and plots are restricted to run 2014: passed.
- Production log, path cache, Step-1 tables, model files, config, and metadata
  retained identical size and modification time during analysis: passed.
- No production source or reproduction output was modified: passed.
