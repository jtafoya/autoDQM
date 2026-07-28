# Run 2088 versus Run 2089 model/log diagnosis

## Scope and validation

This analysis used only the authoritative Step-1 classifications, processed-path
ordering, combined anomaly log, model metadata, and existing detector outputs.
It did not read Digitizer CSV contents or ROOT files, retrain the model, rerun
the detector, change thresholds, or modify production inputs.

The successful processed-file order was reproduced exactly for both runs.
Status counts match the authoritative classification:

- Run 2088: 203 sampled, 180 OK, 23 ALERT, 0 WARN, 0 PEND;
  non-ALERT fraction 88.6700%.
- Run 2089: 369 sampled, 318 OK, 51 ALERT, 0 WARN, 0 PEND;
  non-ALERT fraction 86.1789%.

## ALERT mechanisms

Run 2088 is almost purely extreme:

- 22 extreme-only;
- 1 bulk+extreme;
- 0 bulk-only and 0 persistence-involving;
- total extreme rate: 23/203 = 11.330%;
- total bulk rate: 1/203 = 0.493%.

Run 2089 remains overwhelmingly extreme:

- 48 extreme-only;
- 2 bulk-only;
- 1 bulk+extreme;
- 0 persistence-involving;
- total extreme rate: 49/369 = 13.279%;
- total bulk rate: 3/369 = 0.813%.

The overall ALERT-rate increase is 13.821% - 11.330% = 2.491 percentage
points. The extreme-involving rate rises by 1.949 points and therefore explains
most of the degradation. The appearance of two bulk-only files contributes
another 0.542 points; the small change in overlap accounts for the remainder.
There is no persistent-alert mode in either run.

The severity distribution does not materially increase: ALERT
`max_z_over_file` has the same median (22.86) and essentially identical
quartiles in both runs (about 19–29), and both have a maximum of 1,000,000.
The primary change is frequency, not a larger typical maximum z. Run 2089 does
have more multi-channel ALERTs: only 16/51 have one anomalous channel, versus
13/23 in Run 2088.

## Channels

The dominant overall channels partly recur:

- ch3 is the most frequently anomalous channel in both runs, increasing from
  10/203 = 4.93% to 34/369 = 9.21%;
- ch9 increases from 2.96% to 4.88%;
- ch82 increases from 2.96% to 4.34%.

However, ch3/ch82 are not a Run-2014-like persistent pair here. Their longest
streaks are only two files, neither run has any persistence trigger, and they
are present in a minority of ALERT files.

The largest normalized channel increases in Run 2089 are ch3 (+4.29
percentage points), ch0 (+3.67), ch1 (+3.13), ch23 (+2.81), ch4 (+2.71), ch13
(+1.95), and ch9 (+1.92). At ALERT level, Run 2088 is led by ch10, ch22,
ch7/ch43/ch15, whereas Run 2089 is led by ch15, ch5/ch12, followed by
ch3/ch0/ch10. There is overlap, but not a fixed repeated channel group.

Forty-six of 96 channels increase their normalized anomaly rate and 18
decrease. Sixteen channels absent from the Run-2088 anomaly rows appear in
Run 2089, but most occur only once or twice. The notable new channels are ch4
(10 anomalous files, but only one ALERT presence) and ch27 (4 anomalous files,
3 ALERT presences). Thus the deterioration is broadly distributed, with a few
larger increases rather than concentration in one new channel.

## Features and channel-feature pairs

`nPulses_median` dominates both runs and nearly all ALERTs:

- Run 2088: 74 occurrences overall (0.365 per sampled file), present in all
  23 ALERT files;
- Run 2089: 180 occurrences overall (0.488 per sampled file), present in
  50/51 ALERT files;
- normalized occurrence-rate increase: +0.123 per sampled file, the largest
  absolute feature increase.

IF-only rows increase from 0.158 to 0.257 per sampled file. The largest change
in prominence is `sideband_rms_mean`, from 2/203 = 0.99% to 36/369 = 9.76%,
approximately a 9.9-fold normalized increase. `nPulses_std` and pulse-duration
standard deviations also become more frequent.

No feature is qualitatively new in Run 2089: all 16 triggered feature
categories seen there already occur in Run 2088. Some channel-feature pairs are
new or much more frequent, including:

- ch3 / IF-only: 4.93% -> 9.21%;
- ch12 / `nPulses_median`: 0 -> 1.63%;
- ch94 / `nPulses_median`: 1.48% -> 2.98%;
- ch34 / `nPulses_median`: 0.49% -> 1.90%;
- ch82 / IF-only: 2.96% -> 4.34%;
- ch18 / `nPulses_median`: 0 -> 1.36%;
- ch23 / pulse-duration standard deviations: 0 -> 1.08–1.36%.

This is the same main `nPulses_median` mode occurring across more channels and
files, accompanied by stronger IF/sideband-RMS and duration activity—not a
replacement by a new feature family.

## Statistical versus Isolation Forest composition

Normalized anomalous-row rates increase for all three active method classes:

- statistical-only: 0.478 -> 0.751 rows per sampled file;
- IF-only: 0.158 -> 0.257;
- statistical+IF: 0.0246 -> 0.0542.

Statistical-only rows remain dominant (72.4% of anomalous rows in Run 2088,
70.7% in Run 2089) and have the largest absolute increase. IF-only activity
also grows, and the fraction of ALERT files containing IF-only anomalies rises
from 17.4% to 29.4%, but the ALERT classification itself remains dominated by
statistical extreme z scores. There are no missing-channel, new-channel-method,
or other-method rows.

## ALERT-pattern similarity

ALERT channel sets are mostly unrelated:

- within Run 2088: mean channel Jaccard 0.0418, median 0;
- within Run 2089: mean 0.0416, median 0;
- cross-run: mean 0.0369, median 0.

In contrast, triggered-feature sets are highly similar:

- within Run 2088: mean feature Jaccard 0.699;
- within Run 2089: mean 0.577;
- cross-run: mean 0.637; all three medians are 0.5.

Therefore the repeated anomaly mode is feature-level, especially
`nPulses_median`, not a fixed channel group. Run 2089 is somewhat more
feature-diverse, consistent with increased sideband-RMS, duration, and IF
activity.

## Temporal behavior and the run boundary

Run-2088 quartile ALERT fractions are 5.9%, 5.9%, 21.6%, and 12.0%. It contains
a pronounced third-quartile burst rather than a monotonic end-of-run increase.

Run-2089 quartile fractions are 12.9%, 15.2%, 12.0%, and 15.2%. The degradation
is already present in the first quartile and remains approximately stationary
throughout the run; it does not progressively worsen toward the end.

The boundary shows no reset to a low-anomaly state: the last 20 Run-2088 files
contain 4 ALERTs (20%), while the first 20 Run-2089 files contain 5 (25%).
The first Run-2089 file is already an extreme ALERT. This supports continuity
from elevated late-2088 activity into a sustained Run-2089 rate, rather than an
abrupt qualitatively new mode at the run number boundary.

## Overall interpretation

The most concise defensible explanation of the 2088-to-2089 degradation is:

**the same channel-local, statistical extreme-z mode—overwhelmingly associated
with `nPulses_median`—occurs more frequently and across a broader set of
channels in Run 2089. Typical extreme severity is unchanged. Run 2089 also has
more IF-only, sideband-RMS, duration, and multi-channel activity, adding modest
feature diversity and two bulk-only ALERTs, but no persistent mode or wholly
new feature family appears.**

Thus Run 2089 is primarily the same problem becoming more frequent, with a
secondary broadening of accompanying anomaly patterns—not a qualitatively new
detector state. No hardware cause can be inferred at this stage.

## Recommended next raw Digitizer CSV cases

The following eight files were selected without opening their raw CSV contents:

### Run 2088

- subrun321, ch43, `nPulses_median`: typical one-channel extreme-only ALERT;
- subrun508, ch3/ch7/ch17/ch36/ch43/ch70: largest channel count and the only
  bulk+extreme file; chiefly `nPulses_median`, plus IF-only and
  pulse-height/area medians;
- subrun396, ch69, `nPulses_median`: maximum z = 1,000,000;
- subrun307, ch34, `nPulses_median`: additional representative extreme-only
  event.

### Run 2089

- subrun324, ch19/ch26: typical extreme-only ALERT combining pulse-height/area
  medians and `nPulses_median`;
- subrun922, ch0/ch5/ch6/ch15/ch27/ch38/ch39/ch40/ch45: largest channel count,
  bulk+extreme, with five `nPulses_median` triggers plus sideband-RMS and IF;
- subrun270, ch23, `nPulses_median`: maximum z = 1,000,000;
- subrun659, ch4/ch18/ch19/ch32/ch82: representative bulk-only file, combining
  IF-only, pulse-area-max median, and `nPulses_median`.

These cases should be the inputs to a separate raw Digitizer CSV stage; no raw
inspection was performed here.

## Outputs

- `run2088_2089_subrun_timeline.csv`
- `run2088_2089_alert_condition_summary.csv`
- `run2088_channel_summary.csv`
- `run2089_channel_summary.csv`
- `run2088_vs_2089_channel_comparison.csv`
- `run2088_feature_summary.csv`
- `run2089_feature_summary.csv`
- `run2088_vs_2089_feature_comparison.csv`
- `run2088_2089_method_summary.csv`
- `run2088_channel_feature_matrix.csv`
- `run2089_channel_feature_matrix.csv`
- `run2088_vs_2089_channel_feature_comparison.csv`
- `run2088_alert_channel_matrix.csv`
- `run2089_alert_channel_matrix.csv`
- `run2088_alert_feature_matrix.csv`
- `run2089_alert_feature_matrix.csv`
- `run2088_2089_similarity_summary.csv`
- `run2088_2089_temporal_quartiles.csv`
- `run2088_2089_boundary_summary.csv`
- `run2088_2089_representative_subruns.csv`
- `run2088_2089_diagnostic_metrics.json`
- `run2088_2089_diagnosis_summary.md`
- `diagnose_run2088_2089.py`
- `plots/` containing 16 presentation-quality PNG files
