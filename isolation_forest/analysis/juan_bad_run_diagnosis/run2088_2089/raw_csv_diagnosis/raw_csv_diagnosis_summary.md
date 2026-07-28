# Run 2088/2089 focused raw Digitizer CSV diagnosis

## Scope and verification

This analysis used canonical feature extraction, the stored reference model,
the authoritative anomaly log and processed-file ordering, and 17 selected raw
Digitizer CSV files. It did not read ROOT, retrain or rerun the detector, change
thresholds/source, or modify production inputs.

All reconstructed target features and exact z scores agree with the logged
values after the detector's normal output rounding.

One requested case needed correction from the authoritative log:
Run 2089 subrun324/channel19 is not an `nPulses_median` anomaly. It triggers
`pulseHeight_min_median` (z=-11.27) and `pulseArea_min_median` (z=11.31).
Channel26 is the `nPulses_median` extreme in that file. Channel19's raw
`nPulses` was nevertheless checked as a same-file control.

## Typical `nPulses_median` extreme events

### Run 2088 subrun321/channel43

The canonical reconstruction is:

- observed `nPulses_median` = 2;
- reference mean = 1.00220;
- reference raw/used sigma = 0.043646;
- exact z = 22.8613, logged as 22.86.

Channel43 is present in 45 of 991 file events (occupancy 0.0454). Its raw
distribution is `{1:22, 2:15, 3:6, 4:2}`: 51.1% of channel events have at
least two pulses, mean 1.733, standard deviation 0.863, and median 2.
There are no zero-pulse rows.

The nearest previous/next successfully processed OK controls have median 1 and
only 26.2% and 30.5% of channel events at `nPulses >= 2`. The target therefore
reflects a genuine population-level integer-multiplicity transition, not an
isolated large outlier.

### Run 2089 subrun324/channel26

The canonical reconstruction is:

- observed `nPulses_median` = 2;
- reference mean = 1.00404;
- reference raw/used sigma = 0.061959;
- exact z = 16.0746, logged as 16.07.

Channel26 is present in 61 of 997 file events (occupancy 0.0612). Raw counts are
`{1:25, 2:19, 3:14, 4:3}`: 59.0% have at least two pulses, mean 1.918,
standard deviation 0.918, and median 2. There are no zero-pulse rows.

The same channel in the adjacent OK controls has median 1 and 37.9%/34.9% at
`nPulses >= 2`. This is the same discrete event-population mechanism as the
Run-2088 example.

Channel19 in the same target file has median 1, only 7.4% of events with two
pulses, and `z(nPulses_median)=-0.21`; this independently confirms that its
ALERT contribution comes from pulse-height/area features, not `nPulses`.

## Million-z cases

Both million-z cases have exactly the same numerical origin previously seen
in Run 2014:

- Run 2088 subrun396/channel69:
  observed median 2, reference mean 1, raw sigma 0, used sigma `1e-6`,
  hence `(2-1)/1e-6 = 1,000,000`.
- Run 2089 subrun270/channel23:
  observed median 2, reference mean 1, raw sigma 0, used sigma `1e-6`,
  giving the same z.

The recorded distributions are real but modest:

- subrun396/ch69: `{1:24, 2:14, 3:6, 4:2, 5:2, 7:1}`, with 51.0% at
  `nPulses >= 2`;
- subrun270/ch23: `{1:12, 2:11, 3:2, 4:1}`, with 53.8% at
  `nPulses >= 2`.

Thus the median transition is supported by more than half of the observed
channel events, while the million-scale number is almost entirely reference
variance-floor amplification. It must not be interpreted as physical severity.

## Local versus detector-wide behavior

For all four extreme files, an all-channel canonical reconstruction finds
exactly one channel with `|z(nPulses_median)| > 8`, and it is also the only
channel above 15:

- Run 2088 subrun321: ch43;
- Run 2088 subrun396: ch69;
- Run 2089 subrun324: ch26;
- Run 2089 subrun270: ch23.

The typical and million-z `nPulses` extremes are therefore single-channel
events, not detector-wide multiplicity changes.

## Increased `sideband_rms_mean` activity

The automatically selected cases are:

- Run 2089 typical: subrun251/ch36, exact z=9.02;
- Run 2089 largest z: subrun852/ch0, exact z=14.86;
- comparable Run 2088 case: subrun333/ch33, exact z=9.05.

Their reconstructed observed/reference values are:

- 2089 sub251/ch36: 18.30 versus `2.684 ± 1.731`;
- 2089 sub852/ch0: 35.46 versus `2.938 ± 2.188`;
- 2088 sub333/ch33: 23.30 versus `3.482 ± 2.189`.

This is not an upward shift of the entire `sideband_rms` distribution. In all
three targets the median remains about 0.89–0.90 and the 75th percentile about
0.97–1.14, comparable to neighboring OK files. The elevated mean is produced
by a small high-RMS tail:

- sub251/ch36: q90=1.12 but q95=155 and max=420;
- sub852/ch0: q75=0.97, q90=72.7, max=368;
- sub333/ch33: q75=1.14, q95=129, max=452.

The single largest observation contributes approximately 39%, 55%, and 38% of
the positive sum respectively. Removing only that observation still leaves
means of 11.4, 17.0, and 14.7, so the feature is not caused by exactly one
outlier; rather, a small several-event noisy tail raises the mean while the
bulk of events remains nominal.

The behavior is local or paired, not broad:

- sub251: only ch36 exceeds z=8;
- sub852: only neighboring ch0/ch1 exceed z=8;
- sub333: only neighboring ch32/ch33 exceed z=8.

The same tail-dominated, one- or two-channel phenomenon is already present in
Run 2088. Therefore `sideband_rms_mean` is not a genuinely new Run-2089 anomaly
type; it is an existing local noisy-tail behavior occurring in many more
files/channels. The CSV evidence does not establish its hardware cause.

## Lightweight bulk context

- Run 2088 subrun508 is mixed IF+statistical but is primarily four simultaneous
  `nPulses_median` anomalies, plus one pulse-height/area anomaly and one IF-only
  channel.
- Run 2089 subrun922 is a larger version of the same mixture: five
  `nPulses_median` channels, a two-channel `sideband_rms_mean` pair, one
  pulse-height anomaly, and one IF-only channel.
- Run 2089 subrun659 is bulk-only and more heterogeneous: two IF-only channels,
  two `pulseArea_max_median` channels, and one `nPulses_median` channel.

These files combine already identified statistical/IF patterns; they do not
require a qualitatively new bulk mechanism. This section used the authoritative
log only and did not open the three bulk CSVs.

## Data integrity

All 17 opened raw CSVs are readable and structurally consistent. Each contains
all 96 channels and 991–1000 unique events; row counts range from 8,123 to
9,156. No target channel is missing, and there are no duplicate
`(event_id, channel)` rows, NaN/inf values in relevant raw metrics, malformed
files, or strongly abnormal coverage.

No representative anomaly is explained by a CSV-format or integrity failure.

## Overall interpretation

The raw data supports, rather than revises, the model/log conclusion:

**Run 2089 primarily contains the same local `nPulses_median` mechanism as Run
2088, occurring more frequently across many channels.** In both runs, enough
recorded channel events acquire multiplicity at least two for the median to
cross from 1 to 2. Narrow or zero learned reference variance then amplifies
this small discrete transition, sometimes to one million.

Run 2089 also contains more `sideband_rms_mean` anomalies, but these are the
same local, rare-high-tail behavior already visible in Run 2088. They broaden
the anomaly mix without defining a qualitatively new run state.

## Is ROOT waveform inspection necessary?

ROOT is not necessary to explain the detector decisions or the 2088-to-2089
efficiency change: the exact aggregates, z scores, event fractions, locality,
and reference-floor effects are all resolved at CSV level.

ROOT inspection would only be necessary for a subsequent physical-cause study:

- subrun321/ch43, subrun396/ch69, subrun324/ch26, and subrun270/ch23 to
  determine what waveform structures the extra counted pulses represent;
- subrun251/ch36, subrun852/ch0/ch1, and subrun333/ch32/ch33 to determine the
  waveform/baseline origin of the rare high-`sideband_rms` tail.

## Outputs

- `typical_extreme_npulses_summary.csv`
- `typical_extreme_npulses_value_counts.csv`
- `million_z_reconstruction.csv`
- `extreme_file_channel_summary.csv`
- `sideband_rms_raw_summary.csv`
- `sideband_rms_feature_reconstruction.csv`
- `bulk_context_summary.csv`
- `representative_file_integrity.csv`
- `raw_csv_diagnostic_metrics.json`
- `raw_csv_diagnosis_summary.md`
- `diagnose_run2088_2089_raw_csv.py`
- `plots/` containing 15 diagnostic PNG files
