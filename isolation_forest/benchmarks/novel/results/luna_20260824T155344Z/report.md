# Novel Test — luna

## Run 1620
Category: daq_auto_restart
Cause: unknown
Action: If a DAQ restart or transient DAQ state change is confirmed near the anomalous subruns, review the restart and run-control logs, verify configuration continuity, and restart or reinitialize the affected DAQ components before retaking data. If no restart is found, inspect LVDS/trigger matching and channel-level pulse-count behavior to distinguish a readout issue from detector hardware.
Confidence: 0.68
Historical cases used: 1500, 1604
Reasoning summary: OBSERVED: 35 of 259 subruns contain anomalies, with 42 anomalous channel-entries; the strongest statistical anomalies are repeated nPulses_median deviations, led by channels 38, 0, 5, and 12, while some channels also have isolation-forest flags. INFERRED: this sparse, pulse-count-dominated pattern is most similar to runs 1500 and 1604, both annotated daq_auto_restart, rather than the persistent widespread missing-channel patterns of the broken-PMT-base cases. UNKNOWN: no restart timestamps, trigger/rate history, CPU data, LVDS matching, or HV measurements are provided, so the category remains provisional and the cause is unsupported.

## Run 1640
Category: broken_PMT_base
Cause: Unknown. The strongest hypothesis is a hardware/readout fault affecting the channel-32/33 region, possibly a broken PMT base or associated connection. This is an analogy rather than an exact historical match.
Action: Conditionally, inspect and reseat the PMT base, cabling, channel mapping, and readout connections for channels 32 and 33; check the anomaly onset by subrun and compare the affected channels with neighboring channels before replacing hardware. Also verify DAQ configuration because nearly every subrun is affected.
Confidence: 0.78
Historical cases used: 1637
Reasoning summary: OBSERVED: 740/741 subruns contain anomalies; channel 32 has repeated statistical+IF anomalies with max_z up to 54.2 and features [sideband_mean_median, nPulses_mean, nPulses_median, pulseHeight_max_std, occupancy]; channels 32 and 33 also have missing-channel entries. INFERRED: this closely resembles run 1637, where channel 32 and 33 showed a similar feature signature and the confirmed category was broken_PMT_base. The much larger anomaly scope and missing-channel flags also leave a DAQ/configuration or connection fault plausible. UNKNOWN: physical signal levels, HV, exact onset, channel mapping, and DAQ/log evidence needed to distinguish these causes.

## Run 1642
Category: LVDS_noise
Cause: unknown; the repeated missing-channel flags for channels 32 and 33, together with persistent pulse-count and pulse-feature anomalies, are consistent with a possible intermittent LVDS, trigger-path, or related channel connection problem. A broader DAQ/data-path fault remains possible.
Action: Conditional on confirming a connection or trigger-path fault: stop data taking, inspect and reseat the LVDS pins, jumper wires, MCX cables, and channel mapping for channels 32 and 33, then run trigger-mask/isolation tests while monitoring missing-channel counts, board matching, queue occupancy, and trigger rates. If those checks are normal, investigate DAQ restart or configuration/software state instead.
Confidence: 0.64
Historical cases used: 1637, 2068, 2126
Reasoning summary: Observed: all 202 subruns contain anomalies; channels 32 and 33 repeatedly appear as missing, while channels 25, 42, 31, 32, and 33 show strong nPulses-related deviations and channels 32/33 also show sideband and pulse-height deviations. Inferred: this favors a persistent or intermittent channel/trigger-data path issue over an isolated sensor failure, with LVDS connectivity as the leading hypothesis. Historical cases 2068 and 2126 show missing-channel and broad pulse-count anomalies associated with LVDS problems, while 1637 provides the closest channel/feature similarity for channels 32 and 33 but was attributed to a broken PMT base. No exact historical match exists, and board-matching, trigger-rate, queue, timing, and hardware measurements are unavailable.

## Run 1702
Category: systemic_DAQ_or_digitizer_data_integrity_failure
Cause: unknown; the anomaly is persistent across all 129 subruns and affects a very large fraction of channel-entries, with extreme capped statistical scores concentrated in pulse-count, pulse-height, and pulse-area features. This is more consistent with a run-wide acquisition or data-integrity problem than an isolated detector channel fault, but the supplied evidence does not establish whether the mechanism was a DAQ restart/state fault, digitizer lockup, high CPU condition, or LVDS/trigger-path issue.
Action: Inspect DAQ and digitizer logs for restarts, lockups, CPU or queue alarms, board-matching efficiency, trigger rates, and missing-channel status around the run. Verify digitizer and LVDS/trigger connections and compare raw pulse distributions with a known-good run. If a DAQ or digitizer state fault is confirmed, perform the corresponding controlled process/PC restart; if an LVDS or trigger-path fault is localized, reseat or temporarily mask the affected path before retaking data.
Confidence: 0.62
Historical cases used: 1500, 1604, 1605, 1620, 2126
Reasoning summary: OBSERVED: all subruns contain anomalies; 10,816 channel-entries are anomalous; several channels have max_z values of 1,000,000–2,000,000 and pulse-count/height/area features are affected, with many additional isolation-forest anomalies. INFERRED: the breadth and persistence favor a systemic acquisition or digitizer/data-integrity problem. Partial analogies exist with run 1500 (anomalies in every subrun and DAQ auto-restart), runs 1604–1605 (DAQ/CPU-related anomalies), run 1620 (digitizer lockup), and run 2126 (widespread acquisition anomalies from an LVDS path). No exact historical match exists, and restart, CPU, queue, trigger, missing-channel, and LVDS measurements are UNKNOWN.

## Run 1703
Category: daq_systemic_or_data_integrity_anomaly
Cause: unknown
Action: Conditionally, if raw-data and operational checks confirm a DAQ or configuration fault, inspect DAQ restart/error logs, trigger and digitizer rates, board-matching efficiency, queue occupancy, channel completeness, firmware/configuration consistency, and representative raw waveforms; then reinitialize or restart the affected DAQ component and validate a new run.
Confidence: 0.62
Historical cases used: 1500, 1604, 1642, 2068, 2126
Reasoning summary: No historical case is an exact match. OBSERVED: anomalies occur in all 627 subruns, affect 52,957 channel-entries, span many channels, and include extreme multi-feature statistical flags plus broad isolation-forest flags. INFERRED: the run-wide scale is more consistent with a systemic DAQ, trigger/data-integrity, or processing/configuration problem than a localized PMT fault; the extreme z-scores may also reflect a distribution or reference-data artifact. Partial similarities include all-subrun DAQ anomalies in runs 1500 and 1604, and broad data-integrity/LVDS issues in runs 1642, 2068, and 2126. UNKNOWN: trigger rates, board matching, queue state, missing-channel extent, raw waveforms, timing, DAQ logs, and firmware/configuration changes are unavailable. These checks discriminate a DAQ-wide fault from a detector-wide physical or analysis artifact.

## Run 2126
Category: DAQ-wide acquisition interruption or restart
Cause: Unknown; the broad missing-channel pattern and repeated extreme nPulses_median anomalies suggest a DAQ/data-stream or configuration problem more than an isolated detector channel fault.
Action: Check DAQ and digitizer logs for an automatic restart, lockup, firmware/configuration change, or acquisition interruption near the affected subruns; compare channel presence and pulse counts before and after the onset. If a DAQ lockup or restart is confirmed, restart the affected DAQ component using the approved procedure and verify channel recovery.
Confidence: 0.48
Historical cases used: 1500, 1604, 1605, 1620, 1702, 1703
Reasoning summary: OBSERVED: 65 of 86 subruns are anomalous, with 936 anomalous channel-entries, many missing-channel flags, and repeated extreme statistical anomalies in nPulses_median, including channel 69. INFERRED: the breadth across channels is more consistent with a DAQ-wide acquisition interruption, restart, lockup, or configuration effect than a single PMT fault. PARTIAL ANALOGIES: runs 1500 and 1604 show broad anomalies associated with DAQ auto-restart; run 1620 shows nPulses anomalies from a digitizer lockup; runs 1702-1703 show broad pulse-distribution changes after configuration/software changes. UNKNOWN: restart timing, CPU/load state, trigger rate, firmware/configuration, and whether missing channels are simultaneous. No exact historical match is established.
