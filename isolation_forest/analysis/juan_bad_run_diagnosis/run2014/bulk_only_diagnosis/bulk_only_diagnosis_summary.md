# Run 2014 bulk-only ALERT diagnosis

## Scope and selection

This analysis used the authoritative Run 2014 timeline, Step-1 classification,
combined anomaly log, trained reference, canonical feature extraction, and only
three representative Digitizer CSV files. It did not read ROOT files, retrain,
rerun the detector, change thresholds, or modify production inputs.

The exact selection is:

`strict_status == ALERT`, `bulk_alert == True`,
`persistent_alert == False`, and `extreme_alert == False`.

It contains exactly 18 Run 2014 files. Sixteen have exactly 5 anomalous
channels, one has 6, and one has 7. Every file has fewer than 2 persistent
channels and `max_z_over_file < 15`, confirming that all 18 became ALERT solely
through the configured five-channel single-file bulk condition.

## Primary cause and channel composition

The bulk-only files have a recurring ch3/ch82 background plus a changing set of
additional moderate anomalies:

- ch82 is anomalous in 17/18 files (94.4%): 16 IF-only rows and one
  statistical+IF row;
- ch3 is anomalous in 14/18 files (77.8%): 13 IF-only rows and one
  statistical+IF row;
- both occur together in 13 files, and every one of the 18 files contains at
  least one of ch3 or ch82;
- ch9 is the only other channel reaching 25%, appearing in 5/18 files;
- the remaining channels are dispersed: ch1, ch22, and ch23 occur four times,
  several channels occur two or three times, and 16 channels occur only once.

Thus ch3/ch82 are important contributors, accounting for 31 of the 93 anomalous
channel rows and normally supplying one or two of the five counts required for
a bulk ALERT. They are not sufficient by themselves: every file also contains
statistical anomalies on other channels. There is no small recurring group
beyond the ch3/ch82 core.

## Feature and method composition

Across 93 anomalous channel rows:

- 43 (46.2%) are IF-only;
- 40 (43.0%) are statistical-only;
- 10 (10.8%) are statistical+IF;
- there are no missing-channel, new-channel, or other-method rows.

All 18 files contain at least one statistical anomaly; 17/18 contain at least
one IF-only anomaly; and 9/18 contain a statistical+IF row. Bulk-only ALERTs
are therefore a mixture of many moderate statistical and IF anomalies, rather
than a pure IF or pure statistical mode.

`nPulses_median` remains the most frequent individual statistical trigger, but
it is not overwhelmingly dominant:

- 11/18 files contain at least one `nPulses_median` trigger;
- it occurs on 13 anomalous rows;
- it accounts for 13/50 = 26.0% of rows having a statistical trigger.

Other important statistical triggers are `sideband_rms_mean` (11 rows in 6
files), `nPulses_std` (8 rows in 6 files), `sideband_mean_mean` (6 rows in 5
files), and `sideband_mean_median` (4 rows in 3 files), followed by less common
pulse-area, pulse-height, and pulse-duration features.

Consequently, the integer `nPulses` behavior found in extreme-z events remains
one component of bulk-only files, but bulk-only behavior is much broader in
feature composition. Here the `nPulses_median` z values remain below 15 and
help reach the channel-count threshold rather than independently causing an
extreme ALERT.

## Similarity and repeated patterns

The full anomalous-channel sets have mean pairwise Jaccard similarity 0.226,
median 0.25, and maximum 0.667. Much of that similarity is the shared ch3/ch82
background. After excluding channels 3 and 82, mean similarity drops to 0.061,
median similarity becomes zero, and 116 of 153 file pairs have no remaining
channel in common.

The 18 files therefore do not form one repeated multi-channel detector pattern.
They are best described as one recurring two-channel IF background overlaid
with several heterogeneous moderate statistical patterns. Small repeated
groups exist—for example ch3/ch8/ch9/ch82 and ch22/ch23-related combinations—
but they do not unify all files.

## Representative raw Digitizer CSV checks

Three files were selected deterministically:

- subrun271: largest anomaly count, with 7 channels;
- subrun863: highest mean channel-set Jaccard similarity, representing the
  typical recurring composition;
- subrun802: lowest mean channel-set Jaccard similarity, representing a
  distinct composition.

All three are readable, contain 96 channels and 999–1000 events, and have no
NaN values in the active raw Digitizer source metrics.

### Subrun271 — largest event

The seven anomalous channels do not share one universal raw change:

- ch9 has `nPulses_median = 2` versus reference mean 1.013
  (z = 9.32); 19/35 observed ch9 events have `nPulses >= 2`;
- ch12/ch13 show large pulse-area shifts; ch12 also has pulse-duration spread
  shifts (z values 8.01–9.49);
- ch14/ch15/ch22 are IF-only, each showing different constellations of moderate
  z shifts;
- ch82 has the known duration/occupancy IF background, with occupancy 0.232
  and several duration features near 5–6 sigma.

This is a mixture of a local `nPulses` transition, a small pulse-area/duration
group, other moderate IF vectors, and the ch82 background—not a single
detector-wide observable shift.

### Subrun863 — typical event

The five channels illustrate the common threshold-combination mechanism:

- ch3 and ch82 are IF-only background channels;
- ch8/ch9 have `sideband_mean_mean` z values -8.79 and -8.73;
- ch32 has `nPulses_median = 2` (z = 13.17), with 24/47 observed events at
  `nPulses >= 2`.

Two persistent-background counts plus three independent statistical counts
produce the five-channel bulk ALERT.

### Subrun802 — distinct event

This file lacks ch82 and is mainly statistical:

- ch3 is statistical+IF through `pulseDuriation_min_mean` (z = 9.52);
- ch26/ch36 trigger on `nPulses_median` (z = 8.00 and 14.38);
- ch40 triggers on pulse-height and pulse-area medians;
- ch66 triggers on `sideband_rms_mean`.

Its channels and features are heterogeneous, showing that a bulk-only ALERT
can occur without the usual ch82 IF row. It is not evidence for one broad
event-level change shared by all five channels.

## Temporal structure

Counts in processed-file sequence segments are:

- 0–90: 0/91;
- 91–180: 5/90;
- 181–270: 5/90;
- 271–360: 8/90.

Bulk-only ALERTs are absent from the first quarter and become more common in
the final quarter (8.9% of files versus 5.6% in each middle quarter). They are
distributed across the later run rather than forming one continuous burst.
Nine of the 18 are immediately adjacent to a different ALERT, eight are
adjacent to an extreme ALERT, and five are adjacent to a WARN; these categories
overlap. This supports increasing later-run anomaly activity but does not
identify a single causal episode.

## Interpretation

The 18 bulk-only ALERTs are not a distinct third physical anomaly with a stable
channel/feature signature. They are primarily an **operational threshold
superposition mode**:

1. the recurring ch3/ch82 IF background contributes one or two anomalous
   channels;
2. a heterogeneous set of three or more moderate statistical/IF anomalies
   occurs in the same file;
3. no channel reaches z=15 and persistence remains below two channels, but the
   total reaches the five-channel bulk threshold.

This is therefore a mixture of the already identified ch3/ch82 background,
moderate forms of the `nPulses` mechanism, and other independent baseline,
RMS, pulse-area, pulse-height, and duration shifts. No unsupported hardware
cause is inferred.

## Integrated Run 2014 explanation

Run 2014 has 71 ALERT files out of 361, hence 290/361 = 80.33% non-ALERT
efficiency. The mutually exclusive decomposition is:

- 40 extreme-only;
- 7 bulk+extreme;
- 1 persistence+extreme;
- 18 bulk-only;
- 5 persistence-only.

Thus 48/71 ALERTs involve the extreme mechanism, dominated by locally amplified
`nPulses_median` transitions. Five are pure ch3/ch82 persistence ALERTs. The
remaining 18 bulk-only files are mainly the superposition described above:
the ch3/ch82 IF background lowers the number of additional anomalous channels
needed to reach five, while heterogeneous moderate statistical changes supply
the remainder. Together these three detector-decision mechanisms fully explain
the 71 ALERT classifications without invoking data-integrity failures or an
unsupported physical cause.

## Outputs

- `bulk_only_subruns.csv`
- `bulk_only_channel_summary.csv`
- `bulk_only_feature_summary.csv`
- `bulk_only_channel_feature_matrix.csv`
- `bulk_only_method_summary.csv`
- `bulk_only_subrun_channel_matrix.csv`
- `bulk_only_subrun_feature_matrix.csv`
- `bulk_only_pairwise_similarity.csv`
- `bulk_only_temporal_summary.csv`
- `bulk_only_representative_raw_summary.csv`
- `bulk_only_diagnostic_metrics.json`
- `bulk_only_diagnosis_summary.md`
- `bulk_only_diagnosis.py`
- `plots/bulk_only_channel_frequency.png`
- `plots/bulk_only_feature_frequency.png`
- `plots/bulk_only_channel_feature_heatmap.png`
- `plots/bulk_only_subrun_channel_recurrence_heatmap.png`
- `plots/bulk_only_temporal_location.png`
- `plots/bulk_only_subrun271_anomalous_feature_z_heatmap.png`
- `plots/bulk_only_subrun802_anomalous_feature_z_heatmap.png`
- `plots/bulk_only_subrun863_anomalous_feature_z_heatmap.png`
