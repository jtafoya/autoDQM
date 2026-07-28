# Run 2014 raw Digitizer CSV diagnosis

## Scope and provenance

This diagnosis used only run-2014 Digitizer CSV files, the checked-out canonical
feature/reference/detector code, the existing trained model, and the existing
run-2014 anomaly log/timeline. It did not read ROOT files, retrain, change
thresholds or source, or rerun the detector.

The checked-out implementation forms one vector per `(file, channel)`.
`nPulses_median` is the pandas median of the raw event-level `nPulses` values
present for that channel. The trained model has 29 active Digitizer features:
three aggregations of nine source metrics, plus `occupancy` and `frac_dead`.
`TDC` and `TDCRollovers` are ignored in this trained configuration, so the
nominal 35-feature construction reduces to 29 active features.

The reconstructed vectors, z scores, rounded `max_z`, methods, and IF scores
match the existing anomaly log for all selected targets. Reference standard
deviations were reconstructed from the stored Welford `M2/count`; the production
code then replaces values below `1e-6` with `1e-6`.

## Case A — subrun168, channel 4

The exact trigger is `nPulses_median`:

`observed = 2`, `reference mean = 1`, `reference sigma before floor = 0`,
`sigma used = 1e-6`, hence

`z = (2 - 1) / 1e-6 = 1,000,000`.

The million-scale value is therefore primarily numerical/reference-statistics
amplification by the standard-deviation floor. It amplifies a genuine, but
small and discrete, recorded change in the aggregate: the median moved from
the reference value 1 to 2.

The file has 998 unique events. Channel 4 occurs in 24 events (occupancy
0.02405); its raw `nPulses` counts are `{1: 10, 2: 12, 3: 2}`, with mean
1.667, standard deviation 0.637, and median 2. There are no zero values.
Fourteen of 24 observed channel events (58.3%) have `nPulses >= 2`, so this
cannot be a single-outlier effect. In the selected adjacent/nearby controls,
the channel median is consistently 1; their fraction at `nPulses >= 2` ranges
from 8.6% to 32.5%. Occupancy is somewhat reduced relative to the reference
(z = -4.17), but the channel is neither absent nor silent.

Only channel 4 has `|z(nPulses_median)| > 8` (and >15) in this file. This is a
local channel-level aggregate change, not a detector-wide multiplicity event.

Classification: **genuine recorded discrete distribution change plus dominant
numerical/reference-statistics amplification**; no data-integrity evidence.

## Case B — subrun902, channel 38

The exact trigger is also `nPulses_median`:

`observed = 2`, `reference mean = 1.0002938`,
`reference sigma = 0.0148406`, giving `z = 67.3630` (logged as 67.36).
No sigma floor is applied here, but the very small learned reference spread
strongly amplifies the one-integer median transition.

The file has 608 unique events. Channel 38 occurs in 48 events (occupancy
0.07895); raw counts are `{1: 22, 2: 19, 3: 4, 4: 1, 5: 2}`, with mean
1.792, standard deviation 0.988, median 2, and no zeros. Twenty-six of 48
observed events (54.2%) have `nPulses >= 2`. Nearby controls retain median 1,
with 25.3%–44.8% at `nPulses >= 2`. Thus this is a population-level shift
across many channel events, not one or two extreme events.

Channels 38 and 43 are the only channels above both z=8 and z=15 for
`nPulses_median`. It is a small two-channel event, not detector-wide.

Subrun902 has fewer rows/events than the other representative files
(5,025 rows and 608 events), but it is readable, includes all 96 channels,
has no duplicate event/channel rows or non-finite relevant values, and is not
empty or evidently truncated. The target occupancy is normal enough that
reduced file coverage does not explain the median shift.

Classification: **genuine recorded discrete distribution change amplified by
a very narrow reference distribution**; no identified integrity fault.

## Case C — subrun3, channel 66

Again the exact trigger is `nPulses_median`:

`observed = 2`, `reference mean = 1.0025705`,
`reference sigma = 0.0472589`, giving `z = 21.1056` (logged as 21.11).
The sigma floor is not applied.

The file has 988 unique events. Channel 66 occurs in 78 events (occupancy
0.07895); raw counts are `{1: 38, 2: 28, 3: 10, 4: 2}`, with mean 1.692,
standard deviation 0.795, median 2, and no zeros. Forty of 78 observed events
(51.3%) have `nPulses >= 2`, just enough to move the median. Selected controls
retain median 1, with 31.5%–45.5% at `nPulses >= 2`. This is not caused by a
single high-multiplicity event.

Only channel 66 exceeds z=8 and z=15 for `nPulses_median`; the change is local,
not detector-wide.

Classification: **genuine recorded discrete distribution change amplified by
a narrow reference distribution**; no data-integrity evidence.

## Case D — channels 3 and 82, subrun605 versus subrun94

The prompt's case description required correction from the authoritative log:
in subrun605, channel 82 is IF-only anomalous (`IF score = -0.6469`,
`max_z = 5.59`), while channel 3 is nominal (`IF score = -0.6071`,
`max_z = 6.60`). Subrun605 also contains an unrelated statistical anomaly on
channel 2. In the OK control subrun94, channels 3 and 82 are both nominal,
with IF scores -0.4315 and -0.4025 respectively. Neither channel has any
active feature with `|z| > 8` in either file.

For channel 82, the strongest visible subrun605-versus-subrun94 movements are:

- `pulseDuriation_max_median`: 694.99 versus 302.49,
  z 5.59 versus -0.80;
- `pulseDuriation_min_mean`: 712.38 versus 286.60,
  z 4.94 versus -0.60;
- `pulseDuriation_max_mean`: 1083.05 versus 528.06,
  z 4.60 versus -0.80;
- `sideband_rms_median`: 5.929 versus 1.774,
  z 4.45 versus -0.29;
- `occupancy`: 0.2274 versus 0.1380,
  z 4.53 versus 0.15.

The raw distributions support these aggregate shifts. For example,
`pulseDuriation_max` has median 694.99 and upper quartile 2069.99 in subrun605,
versus 302.49 and 462.49 in subrun94. `sideband_rms` has median 5.929 versus
1.774. Channel 82 is present in 226 versus 137 events, explaining the occupancy
change. The same elevated duration/RMS regime is visible in the selected nearby
subrun605 controls, so this is a stable local background regime rather than a
one-file corruption.

Channel 3 moves in a similar direction but is not flagged in subrun605:
`pulseDuriation_min_mean` moves from 254.19 (z -0.35) to 707.66 (z 6.60);
`pulseDuriation_max_mean` from 347.42 (z -0.80) to 865.02 (z 5.09);
and `sideband_rms_median` from 0.884 (z -0.45) to 5.050 (z 4.60).
Its occupancy is nearly unchanged (0.0695 versus 0.0724).

This evidence explains how an IF-only result can occur: channel 82's vector
contains a joint constellation of several moderate 3–6 sigma shifts in
duration, RMS, occupancy, and pulse-height summaries, although no single
feature crosses the statistical threshold of 8. This is a description of the
observed multivariate pattern, not unsupported Isolation-Forest feature
importance or causal attribution. Channel 3 provides a related shifted vector
but does not cross the IF decision boundary in this particular WARN file.

Classification: **genuine recorded multivariate/local-regime change**; physical
hardware cause unresolved; no data-integrity evidence.

## Overall conclusion

The most specific defensible CSV-level explanation for run2014's reduced
non-ALERT rate is a combination of two mechanisms:

1. Many extreme ALERTs arise when a real integer transition of
   `nPulses_median` from approximately 1 to 2 occurs in enough events for a
   channel. Because the reference distribution for this discrete feature is
   zero or very narrow, the resulting z scores are numerically amplified,
   sometimes enormously. The three representative examples are local or
   limited to two channels, not detector-wide.
2. A separate ch82/ch3 background regime shows coherent moderate shifts across
   several raw observables. This can produce persistent IF-only behavior
   without any individual z score exceeding 8.

The representative files are readable and structurally consistent: all have
96 channel IDs, target channels are present, and there are no duplicate
`(event_id, channel)` rows, NaN/inf values in relevant columns, or obvious
empty/truncated files. Subrun902 has lower coverage, but no direct integrity
fault was found. No physical PMT/HV/electronics cause can be inferred from
these CSVs.

## Is ROOT waveform inspection necessary?

It is **not necessary to answer the current detector-output question**: the CSV
data fully reconstruct the features and detector decisions and distinguishes
distribution shifts, reference amplification, and integrity issues.

ROOT inspection is necessary only if the next goal is to determine the
underlying waveform/physical origin. The minimal next checks would be:

- run2014/subrun168, channel 4: verify pulse finding and waveform morphology for
  events with raw `nPulses` 2–3 versus neighboring subruns, asking whether the
  extra counted pulses are resolved pulses, after-pulses, or reconstruction
  artifacts;
- run2014/subrun902, channels 38 and 43, and run2014/subrun3, channel 66:
  perform the same targeted check for the median-1-to-2 transitions;
- run2014/subrun605, channel 82 (optionally channel 3): compare waveform length,
  baseline/noise, pulse timing, and pulse-duration construction with
  run2014/subrun94, specifically asking why duration, sideband RMS, occupancy,
  and pulse-height summaries shift together.

## Outputs

- `case_manifest.csv`
- `target_feature_reconstruction.csv`
- `extreme_npulses_event_summary.csv`
- `extreme_npulses_value_counts.csv` (supplementary long-form counts)
- `extreme_file_channel_summary.csv`
- `if_only_ch3_ch82_feature_comparison.csv`
- `if_only_ch3_ch82_event_summary.csv`
- `representative_file_integrity.csv`
- `raw_csv_diagnostic_metrics.json` (machine-readable synthesis/provenance)
- `raw_csv_diagnosis_summary.md`
- `run2014_raw_csv_diagnosis.py` (reproducible analysis script)
- `plots/` containing 20 separate diagnostic PNG files
