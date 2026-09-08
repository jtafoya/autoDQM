# AutoFLAME known-failure recognition report

Category recognition accuracy: **6/9**

## Per-family category recognition

| Family | Correct | Completed | Planned |
| --- | ---: | ---: | ---: |
| DAQ automatic restart | 0 | 2 | 2 |
| broken PMT base | 3 | 3 | 3 |
| VMax distribution shift | 2 | 2 | 2 |
| LVDS connection/noise failure | 1 | 2 | 2 |

## Per-target details

### Target 1500 — DAQ automatic restart

- Same-family peers available: [1604]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | daq_auto_restart | high_trigger_rate | incorrect |
| cause | unknown | unknown | not_scorable |
| action | unknown | Check the actual trigger rate and trigger-logic behavior, and review whether firmware was recently reflashed or DAQ software/configuration changed. If a firmware/software mismatch is confirmed, recompile and redeploy MilliDAQ. If the anomaly localizes to an LVDS path, inspect, reseat, and test the associated LVDS cable and connectors, especially those mapped to channel 24. | not_scorable |
| recovery | Run 1501 was subsequently reported with no issues. | Conditionally, trigger rates and trigger logic return to nominal behavior and the channel-24 pulse-duration and sideband anomalies disappear in a new run. | ground_truth_available |

- Confidence: 0.76
- Supporting historical runs: [1747, 2068, 2126]
- Reasoning summary: OBSERVED: All 84 subruns are anomalous; channel 24 repeatedly dominates with z-scores up to 63.6 and a feature pattern centered on sideband mean and pulse-duration extrema. INFERRED: This strongly resembles run 1747's high-trigger-rate signature, which involved nearly the same pulse-duration feature set. Runs 2068 and 2126 provide weaker support for an LVDS/trigger-path alternative. No exact match is established because the current evidence supplies neither trigger-rate measurements nor firmware, software, cable, queue, or board-matching status. Missing/discriminating checks: inspect trigger rates and logic, compare digitizer and trigger-board rates, check board matching and queue occupancy, review recent firmware/configuration changes, and localize channel 24's LVDS mapping. Lack of reported missing channels or nPulses-dominated anomalies weakens the LVDS-noise hypothesis.

### Target 1604 — DAQ automatic restart

- Same-family peers available: [1500]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | daq_auto_restart | digitizer_lockup | incorrect |
| cause | unknown | unknown | not_scorable |
| action | unknown | Check digitizer responsiveness, DAQ/board status, CPU usage, and the subrun timing and channel grouping of the nPulses changes. If a slab digitizer lockup is confirmed, follow the run-1620 remedy: restart the slab DAQ PC while the VME is powered off, then start a validation run. Do not reboot solely from this anomaly signature without operational confirmation. | not_scorable |
| recovery | The run continued in normal configuration at approximately 4.85 Hz, although high CPU usage alerts were observed. | unknown | ground_truth_available |

- Confidence: 0.86
- Supporting historical runs: [1620, 1605]
- Reasoning summary: OBSERVED: 86 of 641 subruns are anomalous, with 97 anomalous entries dominated by nPulses_median; channel 0 appears twice at max_z=45.8, followed by channels 31, 46, and 83. INFERRED: This is a strong but not exact match to run 1620, which had the same anomaly fraction pattern, repeated channel-0 max_z=45.8, and predominantly nPulses_median anomalies and was diagnosed as a digitizer lockup. Run 1605 is a weaker partial match associated with high CPU usage. Broken-PMT-base, Vmax-shift, and LVDS-noise cases are less supported because the supplied snapshot shows neither missing channels nor broad pulse-height/area/occupancy changes. UNKNOWN: digitizer lock state, affected hardware grouping, CPU status, trigger/board-matching behavior, and whether a reboot restores normal operation; these checks discriminate lockup from high CPU or an LVDS/trigger-path issue.

### Target 1637 — broken PMT base

- Same-family peers available: [1640, 1642]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | broken_PMT_base | broken_PMT_base | correct |
| cause | Broken PMT base. The run was reported as good through subrun 356 and bad after subrun 357 due to the broken PMT base. | unknown; suspected intermittent degradation in the PMT base, HV path, or shared LVDS path affecting channels 32 and 33 | ground_truth_available |
| action | unknown | Check timestamp-aligned HV trip logs and current draw for channels 32/33, and compare their pulse-height, occupancy, and count trends. If HV current is unstable or non-nominal, disable the affected HV path and isolate the base, cable, and connector using a validated cable/base substitution test. If HV is nominal, inspect the shared LVDS mapping and connections before replacing hardware. | not_scorable |
| recovery | unknown | Not observed. If this diagnosis is confirmed and corrected, recovery should be demonstrated by stable nominal HV current, nonzero and stable counts/occupancy, recovered pulse-height behavior, and no recurrence in subsequent subruns. | not_scorable |

- Confidence: 0.86
- Supporting historical runs: [1640, 1642]
- Reasoning summary: OBSERVED: Channels 32 and 33 dominate the alert; channel 32 has the same sideband, pulse-count, pulse-height-variation, and occupancy feature combination seen in run 1640, with a similarly large z-score. INFERRED: This is a strong match to the early channel-32/33 signature of the broken-PMT-base family. Support includes the exact channel pair and feature pattern. Contradictions are that only 65/359 subruns are anomalous and no missing-channel or HV-trip evidence is supplied, unlike the persistent/later failures in runs 1640/1642. UNKNOWN: HV current/trip history, direction of pulse-height and occupancy changes, LVDS counts, and temporal correlation between channels 32/33. A DAQ-rate disturbance is a secondary possibility because pulse-count anomalies occur, but it does not explain the highly specific 32/33 pattern as well. HV/current checks and LVDS/path isolation are the discriminating tests.

### Target 1640 — broken PMT base

- Same-family peers available: [1637, 1642]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | broken_PMT_base | broken_PMT_base | correct |
| cause | Damaged PMT base due to unknown reasons, possibly power grid fluctuations propagating through the LV supplies; appeared first as change of channel ch32/33 behaviour (both are coupled through the same LVDS pin) leading e.g. to smaller VMax readouts; eventually the channel HV tripped and completely turned off contributions from these channels/LVDS | Likely a damaged PMT base or associated HV cable/connector affecting channels 32 and 33; the exact failed component and initiating cause are unknown. | ground_truth_available |
| action | Check the HV current draw Check HV log for a trip near the run timestamp. If channel current draws are unstable or different from nominal, switch it off until a physical intervention can be carried out. Physical intervention: Check continuity of all HV cables between HVPS and involved channels. Physical intervention: Disconnect the HV off all the relevant PMT bases. Connect one at a time and turn HV on noting which ones don't draw nominal current values. This allows to indentify the faulty HV paths (problem can be either in the cables, at the connectors, or at the base. Physical intervention: Use a validated healthy HV cable to power the problematic base. If draws are nominal, then the culprit is most likely in the HV cable and/or connector between the HV splitter box and the base. If the current draw is not nominal, then try replacing the base for a new one. N.B. be sure to use the same base version and set exactly the same gain with the switches to match the broken base! Physical intervention: If the problem is in the cables/connectors, do further eliminatory testing to determine isolate the issue. E.g. plug a healthy cable into the output of the HV splitter originally leading to the issue, and use it to power a healtyh PMT. If draws are nominal, the issue is at the original cable not currently being used. | Check the HV trip log and current draw for channels 32 and 33. If current is absent, unstable, or non-nominal, switch off the affected HV path and isolate the fault by testing the HV cables, connectors, and PMT bases individually with validated components. Replace the base only if testing localizes the failure to it. Also inspect LVDS connectivity if HV behavior is nominal. | ground_truth_available |
| recovery | HV draw back to nominal and stable values, LVDS counts non-zero, VMax recovers for the involved channels | Expected recovery is stable nominal HV current, nonzero channel/LVDS pulse contributions, restored occupancy and pulse-height behavior, and disappearance of repeated missing-channel alerts in a subsequent run. | ground_truth_available |

- Confidence: 0.9
- Supporting historical runs: [1637, 1642]
- Reasoning summary: OBSERVED: 740 of 741 subruns are anomalous; channel 32 repeatedly has extreme deviations in sideband, pulse-count, pulse-height, and occupancy features, while channels 32 and 33 repeatedly appear missing. INFERRED: This closely matches run 1642, including the same channels, missing-channel pattern, and feature family, and partially matches the channel-32 signature preceding the broken-base diagnosis in run 1637. The lower reported maximum z-score and different anomaly count do not contradict the family but prevent asserting identical severity. A degraded LVDS connection is a weaker alternative because missing channels can occur in LVDS cases, but the current signature is substantially closer to the broken-PMT-base history. UNKNOWN: HV current, HV-trip timing, LVDS counts, waveform presence, physical mapping, and onset time. These checks discriminate a PMT-base/HV-path failure from LVDS or readout connectivity problems.

### Target 1642 — broken PMT base

- Same-family peers available: [1637, 1640]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | broken_PMT_base | broken_PMT_base | correct |
| cause | Damaged PMT base due to unknown reasons, possibly power grid fluctuations propagating through the LV supplies (continuation of issue seen at run 1640); channel HV already tripped, no pulse contributions from these channels/LVDS | Suspected damaged PMT base or associated HV cable/connector path affecting coupled channels 32 and 33; not confirmed from the supplied snapshot. | ground_truth_available |
| action | Check the HV current draw Check HV log for a trip near the run timestamp. If channel current draws are unstable or different from nominal, switch it off until a physical intervention can be carried out. Physical intervention: Check continuity of all HV cables between HVPS and involved channels. Physical intervention: Disconnect the HV off all the relevant PMT bases. Connect one at a time and turn HV on noting which ones don't draw nominal current values. This allows to indentify the faulty HV paths (problem can be either in the cables, at the connectors, or at the base. Physical intervention: Use a validated healthy HV cable to power the problematic base. If draws are nominal, then the culprit is most likely in the HV cable and/or connector between the HV splitter box and the base. If the current draw is not nominal, then try replacing the base for a new one. N.B. be sure to use the same base version and set exactly the same gain with the switches to match the broken base! Physical intervention: If the problem is in the cables/connectors, do further eliminatory testing to determine isolate the issue. E.g. plug a healthy cable into the output of the HV splitter originally leading to the issue, and use it to power a healtyh PMT. If draws are nominal, the issue is at the original cable not currently being used. | Check the HV trip log and current draw for channels 32/33 near the run timestamp. If current is abnormal or unstable, disable the affected HV path and isolate the cable, connector, and PMT base using a validated cable and one-at-a-time tests. Also inspect the shared LVDS connection; if HV behavior is nominal, test LVDS noise or connection failure as an alternative diagnosis. | ground_truth_available |
| recovery | HV draw back to nominal and stable values, LVDS counts non-zero, VMax recovers for the involved channels | HV current is nominal and stable, channels 32/33 remain present with nonzero counts, and their pulse-height and sideband metrics return to baseline in a subsequent run. | ground_truth_available |

- Confidence: 0.9
- Supporting historical runs: [1640, 1637]
- Reasoning summary: OBSERVED: all 202 subruns are anomalous; channels 32/33 repeatedly appear as missing and also show strong sideband, pulse-count, and pulse-height anomalies. INFERRED: this closely matches run 1640, where coupled channels 32/33 progressed to missing contributions following a PMT-base/HV failure; run 1637 provides a weaker precursor match. Unlike the LVDS-noise references, the target specifically reproduces the 32/33 feature pattern from run 1640. UNKNOWN: HV current/trip history, anomaly timing within the run, LVDS counts, board matching, and physical connection status. These checks are required to distinguish a damaged base/HV path from LVDS or DAQ connectivity failure.

### Target 1702 — VMax distribution shift

- Same-family peers available: [1703]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | vmax_distribution_shift | vmax_distribution_shift | correct |
| cause | The Vmax pulse distribution increased after changes made during preceding slab detector tests. The eLog suggests that this may have been related to a software or zero-suppression change removing normal-sized pulses, but the cause was not confirmed. | unknown | ground_truth_available |
| action | Revert to running without zero suppression. | Verify whether zero suppression or pulse-selection software/configuration changed before this run. If confirmed, revert to running without zero suppression and start a validation run; otherwise investigate other run-wide configuration changes before modifying hardware. | ground_truth_available |
| recovery | After reverting to no zero suppression, the average Vmax returned to its previous levels by run 1705. | Confirm that pulse-height/Vmax, pulse-area, and pulse-count distributions return to their previous baseline in a subsequent run. | ground_truth_available |

- Confidence: 0.95
- Supporting historical runs: [1703]
- Reasoning summary: OBSERVED: All 129 subruns are anomalous, with 10,816 entries and extreme deviations across pulse-count, pulse-height, and pulse-area features, especially on channels 50, 57, and 25. INFERRED: This closely matches run 1703 in affected channels, features, extreme z-scores, universal subrun coverage, and anomaly density; that case was a Vmax distribution shift associated with an unconfirmed software/zero-suppression change. No equally close match appears among the hardware-failure cases, which were more localized or included explicit missing channels. UNKNOWN: The direction of the distributions, current zero-suppression setting, timing of configuration changes, trigger rate, and channel completeness. Discriminating checks are comparison of raw Vmax/pulse distributions and run configuration against the preceding healthy run; only if a zero-suppression change is verified should it be reverted.

### Target 1703 — VMax distribution shift

- Same-family peers available: [1702]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | vmax_distribution_shift | vmax_distribution_shift | correct |
| cause | The Vmax pulse distribution increased after changes made during preceding slab detector tests. The eLog suggests that this may have been related to a software or zero-suppression change removing normal-sized pulses, but the cause was not confirmed. | unknown | ground_truth_available |
| action | Revert to running without zero suppression. | Check whether zero suppression or related slab-detector software/configuration changed before this run. If confirmed, revert to running without zero suppression and start a validation run; otherwise investigate run-wide configuration or acquisition changes before hardware intervention. | ground_truth_available |
| recovery | After reverting to no zero suppression, the average Vmax returned to its previous levels by run 1705. | Confirm that pulse-height/Vmax distributions and pulse-count/area features return to their prior baseline across subruns and that the widespread channel anomalies clear. | ground_truth_available |

- Confidence: 0.95
- Supporting historical runs: [1702]
- Reasoning summary: OBSERVED: all 627 subruns are anomalous, with 52,957 entries; channels 50, 57, and 25 show extreme pulse-count, pulse-height, and pulse-area deviations. INFERRED: this is a strong near-exact match to run 1702, including the same leading channels/features, extreme capped z-scores, and run-wide persistence, favoring a Vmax distribution shift over a localized PMT, LVDS, or digitizer fault. UNKNOWN: actual distribution direction, zero-suppression state, configuration history, trigger rates, missing channels, and HV/DAQ status. Check pre-run configuration changes and compare raw Vmax distributions with a known-good run. A localized hardware fault is less supported because the anomaly is widespread, but should be reconsidered if configuration and raw-distribution checks do not reproduce the run-1702 pattern.

### Target 2068 — LVDS connection/noise failure

- Same-family peers available: [2126]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | LVDS_noise | LVDS_noise | correct |
| cause | Unclear. Possible charge collection in LVDS pins, or mechanical failure of the LVDS jumper wires needing readjustment; higher trigger rates than usual | unknown | ground_truth_available |
| action | Physical intervention: Carefully check whether all the LVDS pins are fully seated into the trigger board and digitizer Physical intervention: Carefully press in all the jumper wires while the run is off, and check again by starting a new run. It may take a few iterations. Check physical channel mapping and cable connections for the flagged channels. | First verify whether channel 2 belongs to an affected LVDS/trigger path. Check board-matching efficiency, digitizer versus trigger-board rates, DAQ queue occupancy, and raw channel-presence data. Inspect and reseat the corresponding LVDS pins, jumper wires, and signal cables; use trigger-mask tests to isolate the path. If HV current or trip logs are abnormal instead, investigate the channel's HV cable and PMT base rather than assuming LVDS noise. | ground_truth_available |
| recovery | Trigger rates recover to nominal values | If the LVDS-path hypothesis is confirmed, recovery is indicated by channel 2 remaining present, board matching returning to normal, stable queue occupancy and trigger rates, and no recurrence after the path is re-enabled. Otherwise unknown. | ground_truth_available |

- Confidence: 0.45
- Supporting historical runs: [2126, 1640, 1642]
- Reasoning summary: OBSERVED: all 5 subruns are anomalous; channel 2 is missing in every subrun; channels 47 and 4 have extreme nPulses_median deviations; other channels show mixed waveform and isolation-forest anomalies. INFERRED: persistent channel loss plus extreme pulse-count anomalies is partially similar to LVDS_noise run 2126. Persistent missing channels also resemble broken-PMT-base runs 1640/1642, but the target lacks their paired-channel pattern and HV/VMax evidence. No exact historical match exists. UNKNOWN: board matching, queue behavior, trigger rates, channel mapping, HV current/trips, and raw waveform presence; these checks discriminate an LVDS/DAQ path fault from an HV/PMT-base fault.

### Target 2126 — LVDS connection/noise failure

- Same-family peers available: [2068]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | LVDS_noise | digitizer_lockup | incorrect |
| cause | DAQ board-matching efficiency dropped below 100% beginning in run 2126, file 26, around event 700. The DAQ queue filled with mostly empty, unmatched digitizer events and the apparent digitizer trigger rate became abnormally high while the trigger-board files remained normal. Trigger-mask tests localized the problem to digitizer 0 LVDS channel 0, corresponding to detector channels 0 and 1. The subsequent intervention indicated an intermittent or degraded LVDS-pin, jumper-wire, or MCX signal connection. | unknown | ground_truth_available |
| action | Temporarily mask LVDS channel 0 or the affected trigger path to permit data taking. Isolate the problematic connection by removing trigger-mask channels one at a time and restoring them until the problem reappears. Inspect and reseat the LVDS pins at both the trigger board and digitizer, the LVDS jumper wires, and the MCX signal cables for digitizer channels 0 and 1. Start a new run after each connection change and monitor board matching, DAQ queue occupancy, and trigger rates. | Conditionally, if DAQ logs or channel-status checks confirm a digitizer/readout lockup, stop the run and restart the affected DAQ PC using the run-1620 procedure with the VME powered off. Before restarting, check whether the missing channels cluster by digitizer and inspect DAQ auto-restart, CPU, firmware, and LVDS status. | ground_truth_available |
| recovery | Board-matching efficiency returns to 100%, the DAQ queue no longer fills with empty unmatched events, trigger rates return to their normal range, and all affected cables and channels can remain connected and enabled without the problem recurring. | Confirm in a new run that all expected channels are present and that nPulses and anomaly rates return to nominal values. | ground_truth_available |

- Confidence: 0.35
- Supporting historical runs: [1620, 1500, 1604, 2068]
- Reasoning summary: OBSERVED: 65 of 86 subruns are anomalous, with 936 entries, extreme nPulses_median deviations, and multiple missing channels across distinct IDs. INFERRED: this broad readout-loss pattern is more consistent with a DAQ/digitizer disruption than the localized channel-pair loss of broken-PMT-base cases. Run 1620 provides a partial digitizer-lockup analogue; runs 1500/1604 resemble transient DAQ disruption, and run 2068 partially resembles repeated missing-channel behavior. No historical case is an exact match: run 1620 did not report missing channels in the supplied snapshot, while PMT/LVDS cases were more localized. UNKNOWN: channel-to-digitizer mapping, timing of losses, DAQ restart/CPU logs, firmware state, trigger rate, and HV/LVDS status. These checks are needed to distinguish lockup from auto-restart, LVDS failure, or configuration problems.
