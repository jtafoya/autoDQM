# AutoFLAME known-failure recognition report

Category recognition accuracy: **5/9**

## Per-family category recognition

| Family | Correct | Completed | Planned |
| --- | ---: | ---: | ---: |
| DAQ automatic restart | 0 | 2 | 2 |
| broken PMT base | 3 | 3 | 3 |
| VMax distribution shift | 2 | 2 | 2 |
| LVDS connection/noise failure | 0 | 2 | 2 |

## Per-target details

### Target 1500 — DAQ automatic restart

- Same-family peers available: [1604]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | daq_auto_restart | high_trigger_rate | incorrect |
| cause | unknown | unknown | not_scorable |
| action | unknown | Conditionally check the detector trigger rate, trigger logic, DAQ/firmware configuration, and LVDS cable and pin connections. If a high-rate or trigger-matching problem is confirmed, recompile MilliDAQ after any firmware reflash and repair or reseat the faulty LVDS connection. | not_scorable |
| recovery | Run 1501 was subsequently reported with no issues. | unknown | ground_truth_available |

- Confidence: 0.6
- Supporting historical runs: [1747, 2068, 2126]
- Reasoning summary: OBSERVED: all 84 subruns contain anomalies; 315 channel-entries are anomalous; channel 24 is repeatedly flagged by statistical and isolation-forest methods with very large z-scores, and many other channels are affected. INFERRED: this broad, persistent pattern is most similar to the high-trigger-rate case 1747, with partial similarity to LVDS-noise cases 2068 and 2126 because those also involve widespread anomalies and trigger-path effects. No trigger-rate, board-matching, power-trip, firmware, or missing-channel evidence is supplied, so the failure family is not confirmed and the cause and recovery remain unknown.

### Target 1604 — DAQ automatic restart

- Same-family peers available: [1500]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | daq_auto_restart | digitizer_lockup | incorrect |
| cause | unknown | unknown | not_scorable |
| action | unknown | Conditionally restart the slab DAQ PC while the VME is powered off, after confirming the issue is a digitizer/DAQ lockup and preserving relevant logs. | not_scorable |
| recovery | The run continued in normal configuration at approximately 4.85 Hz, although high CPU usage alerts were observed. | unknown | ground_truth_available |

- Confidence: 0.65
- Supporting historical runs: [1620]
- Reasoning summary: OBSERVED: 86 of 641 subruns contain anomalies, with 97 anomalous channel-entries; the strongest repeated abnormalities are nPulses_median anomalies, including channel 0 at max_z=45.8 and additional channels with large z-scores. INFERRED: This resembles run 1620, where repeated nPulses_median anomalies and a matching channel-0 max_z=45.8 were associated with a digitizer lockup. The current alert does not provide CPU, DAQ-state, firmware, HV/LVDS, timing, or subsequent-run evidence, so the cause and recovery cannot be established. Check DAQ/digitizer logs and channel behavior before applying the conditional restart.

### Target 1637 — broken PMT base

- Same-family peers available: [1640, 1642]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | broken_PMT_base | broken_PMT_base | correct |
| cause | Broken PMT base. The run was reported as good through subrun 356 and bad after subrun 357 due to the broken PMT base. | unknown; the channel-32/33 pattern is consistent with an emerging coupled PMT-base, HV, or LVDS-path problem, but the supplied evidence does not establish the physical cause. | ground_truth_available |
| action | unknown | Conditionally inspect HV current and HV-trip logs for channels 32 and 33, then check LVDS counts and VMax behavior. If HV is unstable or non-nominal, switch off the affected path and isolate the cable, connector, and PMT base by controlled substitution before replacing hardware. | not_scorable |
| recovery | unknown | unknown; confirm recovery only if HV draw is nominal and stable, LVDS counts are non-zero, and VMax and channel pulse behavior return to normal in a subsequent run. | not_scorable |

- Confidence: 0.84
- Supporting historical runs: [1640, 1642]
- Reasoning summary: OBSERVED: 65 of 359 subruns contain anomalies, with repeated high-significance anomalies on channel 32 and a related anomaly on channel 33 involving sideband, pulse-count, pulse-height variability, and occupancy features. INFERRED: this closely matches runs 1640 and 1642, where coupled channels 32/33 preceded or accompanied a broken-PMT-base failure. The current case has no reported missing-channel entries, HV trip, LVDS count loss, or recovery result, so it may be an earlier or less severe stage and the diagnosis is not confirmed. Channel 39 and the broader anomaly population are less specific.

### Target 1640 — broken PMT base

- Same-family peers available: [1637, 1642]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | broken_PMT_base | broken_PMT_base | correct |
| cause | Damaged PMT base due to unknown reasons, possibly power grid fluctuations propagating through the LV supplies; appeared first as change of channel ch32/33 behaviour (both are coupled through the same LVDS pin) leading e.g. to smaller VMax readouts; eventually the channel HV tripped and completely turned off contributions from these channels/LVDS | unknown | ground_truth_available |
| action | Check the HV current draw Check HV log for a trip near the run timestamp. If channel current draws are unstable or different from nominal, switch it off until a physical intervention can be carried out. Physical intervention: Check continuity of all HV cables between HVPS and involved channels. Physical intervention: Disconnect the HV off all the relevant PMT bases. Connect one at a time and turn HV on noting which ones don't draw nominal current values. This allows to indentify the faulty HV paths (problem can be either in the cables, at the connectors, or at the base. Physical intervention: Use a validated healthy HV cable to power the problematic base. If draws are nominal, then the culprit is most likely in the HV cable and/or connector between the HV splitter box and the base. If the current draw is not nominal, then try replacing the base for a new one. N.B. be sure to use the same base version and set exactly the same gain with the switches to match the broken base! Physical intervention: If the problem is in the cables/connectors, do further eliminatory testing to determine isolate the issue. E.g. plug a healthy cable into the output of the HV splitter originally leading to the issue, and use it to power a healtyh PMT. If draws are nominal, the issue is at the original cable not currently being used. | Conditional on confirming a PMT/HV fault: check HV current draw and HV logs for trips or unstable currents on the affected channels, then inspect HV cables, connectors, and PMT bases. Also verify LVDS connections because channels 32 and 33 are reported missing. | ground_truth_available |
| recovery | HV draw back to nominal and stable values, LVDS counts non-zero, VMax recovers for the involved channels | unknown | ground_truth_available |

- Confidence: 0.88
- Supporting historical runs: [1637, 1642]
- Reasoning summary: OBSERVED: nearly all subruns contain anomalies; channel 32 has repeated statistical+isolation-forest anomalies with the same sideband_mean_median, nPulses, pulseHeight_max_std, and occupancy pattern seen in run 1637, and channels 32/33 repeatedly appear as missing. INFERRED: this strongly resembles the broken-PMT-base family, with run 1642 providing an additional similarity through missing channels 32/33. UNKNOWN: HV currents, HV trips, timing of onset, physical inspection results, and whether the missing channels are caused by hardware or DAQ readout. The broad anomaly coverage leaves DAQ/LVDS-related alternatives possible, so the proposed hardware diagnosis remains conditional.

### Target 1642 — broken PMT base

- Same-family peers available: [1637, 1640]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | broken_PMT_base | broken_PMT_base | correct |
| cause | Damaged PMT base due to unknown reasons, possibly power grid fluctuations propagating through the LV supplies (continuation of issue seen at run 1640); channel HV already tripped, no pulse contributions from these channels/LVDS | unknown; the concentration of anomalies in channels 32 and 33, including repeated missing-channel detections, is consistent with a coupled PMT-base/HV/LVDS-path failure seen in run 1640, but no HV or hardware measurements are provided. | ground_truth_available |
| action | Check the HV current draw Check HV log for a trip near the run timestamp. If channel current draws are unstable or different from nominal, switch it off until a physical intervention can be carried out. Physical intervention: Check continuity of all HV cables between HVPS and involved channels. Physical intervention: Disconnect the HV off all the relevant PMT bases. Connect one at a time and turn HV on noting which ones don't draw nominal current values. This allows to indentify the faulty HV paths (problem can be either in the cables, at the connectors, or at the base. Physical intervention: Use a validated healthy HV cable to power the problematic base. If draws are nominal, then the culprit is most likely in the HV cable and/or connector between the HV splitter box and the base. If the current draw is not nominal, then try replacing the base for a new one. N.B. be sure to use the same base version and set exactly the same gain with the switches to match the broken base! Physical intervention: If the problem is in the cables/connectors, do further eliminatory testing to determine isolate the issue. E.g. plug a healthy cable into the output of the HV splitter originally leading to the issue, and use it to power a healtyh PMT. If draws are nominal, the issue is at the original cable not currently being used. | Conditionally, check HV current draws and HV logs for channels 32 and 33, then inspect and reseat the associated HV/LVDS cables, connectors, and PMT bases. Keep affected HV off until the fault is isolated if currents are unstable or non-nominal. | ground_truth_available |
| recovery | HV draw back to nominal and stable values, LVDS counts non-zero, VMax recovers for the involved channels | unknown | ground_truth_available |

- Confidence: 0.82
- Supporting historical runs: [1640, 1637]
- Reasoning summary: OBSERVED: all 202 subruns contain anomalies; channels 32 and 33 repeatedly show statistical/isolation-forest anomalies and missing-channel entries, with 532 anomalous channel-entries overall. INFERRED: this closely matches run 1640, where channels 32/33 first exhibited similar feature shifts and then became missing because of a documented PMT-base/HV/LVDS failure; run 1637 provides a partial similarity involving channels 32/33. UNKNOWN: HV currents, HV-trip timing, LVDS counts, VMax behavior, physical cabling, and whether the channels recover after intervention. Therefore the category is a strong analogical match, but the cause and recovery are not confirmed.

### Target 1702 — VMax distribution shift

- Same-family peers available: [1703]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | vmax_distribution_shift | vmax_distribution_shift | correct |
| cause | The Vmax pulse distribution increased after changes made during preceding slab detector tests. The eLog suggests that this may have been related to a software or zero-suppression change removing normal-sized pulses, but the cause was not confirmed. | unknown | ground_truth_available |
| action | Revert to running without zero suppression. | If confirmed to be associated with a zero-suppression or software configuration change, revert to running without zero suppression. | ground_truth_available |
| recovery | After reverting to no zero suppression, the average Vmax returned to its previous levels by run 1705. | unknown | ground_truth_available |

- Confidence: 0.86
- Supporting historical runs: [1703]
- Reasoning summary: Observed: all 129 subruns contain anomalies, with 10,816 anomalous channel-entries and dominant statistical+IF flags on channels 50, 57, and 25 involving pulse counts, pulse heights, and pulse areas; several max_z values are clipped at very large values. Inferred: this closely matches run 1703, which had the same dominant channels and feature family with anomalies in every subrun, supporting a Vmax/pulse-distribution shift. No direct Vmax measurement, configuration-change record, or recovery result is supplied, so the specific cause and confirmed corrective outcome remain unknown.

### Target 1703 — VMax distribution shift

- Same-family peers available: [1702]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | vmax_distribution_shift | vmax_distribution_shift | correct |
| cause | The Vmax pulse distribution increased after changes made during preceding slab detector tests. The eLog suggests that this may have been related to a software or zero-suppression change removing normal-sized pulses, but the cause was not confirmed. | Unknown; the pattern is consistent with a software or zero-suppression configuration change affecting pulse selection, but this is not confirmed by the supplied evidence. | ground_truth_available |
| action | Revert to running without zero suppression. | Conditionally test reverting to operation without zero suppression, after verifying the run configuration and comparing Vmax and pulse-count distributions with a known-good run. | ground_truth_available |
| recovery | After reverting to no zero suppression, the average Vmax returned to its previous levels by run 1705. | Unknown; confirm by checking whether Vmax and pulse distributions return to baseline in a subsequent run. | ground_truth_available |

- Confidence: 0.9
- Supporting historical runs: [1702]
- Reasoning summary: The current alert shows anomalies in all 627 subruns and 52,957 channel-entries, with prominent channels 50, 57, and 25 and features dominated by nPulses, pulseHeight, and pulseArea. This closely matches run 1702, which had all subruns anomalous, 10,816 anomalous entries, the same prominent channels, similarly extreme z-scores, and the same feature family; that case was annotated as a Vmax distribution shift associated with a possibly changed zero-suppression or software configuration. The supplied evidence does not establish the actual configuration change or recovery.

### Target 2068 — LVDS connection/noise failure

- Same-family peers available: [2126]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | LVDS_noise | daq_auto_restart | incorrect |
| cause | Unclear. Possible charge collection in LVDS pins, or mechanical failure of the LVDS jumper wires needing readjustment; higher trigger rates than usual | unknown | ground_truth_available |
| action | Physical intervention: Carefully check whether all the LVDS pins are fully seated into the trigger board and digitizer Physical intervention: Carefully press in all the jumper wires while the run is off, and check again by starting a new run. It may take a few iterations. Check physical channel mapping and cable connections for the flagged channels. | unknown | ground_truth_available |
| recovery | Trigger rates recover to nominal values | unknown | ground_truth_available |

- Confidence: 0.45
- Supporting historical runs: [1500, 1604, 1605, 1620]
- Reasoning summary: OBSERVED: all 5 subruns contain anomalies, with extreme nPulses_median outliers on channels 47 and 4, repeated missing-channel alerts for channel 2, and additional isolation-forest anomalies. INFERRED: this is more consistent with a short-lived DAQ-wide or digitizer/DAQ disruption than an isolated detector channel fault. The broad, run-spanning pattern partially resembles the daq_auto_restart cases 1500 and 1604; the channel-47 nPulses signature also resembles high-CPU case 1605, while missing-channel and pulse-count anomalies have partial similarity to digitizer-lockup case 1620. No historical case is an exact match, and the supplied evidence does not establish a confirmed cause, intervention, or recovery.

### Target 2126 — LVDS connection/noise failure

- Same-family peers available: [2068]
- Status: completed

| Field | Ground truth | Prediction | Status |
| --- | --- | --- | --- |
| category | LVDS_noise | vmax_distribution_shift | incorrect |
| cause | DAQ board-matching efficiency dropped below 100% beginning in run 2126, file 26, around event 700. The DAQ queue filled with mostly empty, unmatched digitizer events and the apparent digitizer trigger rate became abnormally high while the trigger-board files remained normal. Trigger-mask tests localized the problem to digitizer 0 LVDS channel 0, corresponding to detector channels 0 and 1. The subsequent intervention indicated an intermittent or degraded LVDS-pin, jumper-wire, or MCX signal connection. | unknown | ground_truth_available |
| action | Temporarily mask LVDS channel 0 or the affected trigger path to permit data taking. Isolate the problematic connection by removing trigger-mask channels one at a time and restoring them until the problem reappears. Inspect and reseat the LVDS pins at both the trigger board and digitizer, the LVDS jumper wires, and the MCX signal cables for digitizer channels 0 and 1. Start a new run after each connection change and monitor board matching, DAQ queue occupancy, and trigger rates. | Conditionally compare the run configuration with the preceding slab-detector tests, especially zero-suppression settings and software changes. If a configuration change is confirmed and Vmax distributions shifted, test reverting zero suppression. | ground_truth_available |
| recovery | Board-matching efficiency returns to 100%, the DAQ queue no longer fills with empty unmatched events, trigger rates return to their normal range, and all affected cables and channels can remain connected and enabled without the problem recurring. | unknown | ground_truth_available |

- Confidence: 0.72
- Supporting historical runs: [1702, 1703, 1605]
- Reasoning summary: Observed: 65 of 86 subruns contain anomalies, with 936 anomalous channel-entries; channels 69 and 50 show saturated max_z=1000000 and nPulses_median anomalies, alongside many missing-channel flags. This is partially similar to runs 1702 and 1703, which prominently affected channels 50 and 69 with saturated statistical scores and broad detector anomalies, and to run 1605 for the nPulses_median pattern. However, the current evidence does not include Vmax features, configuration history, or recovery results, so a Vmax distribution shift is a cautious family-level match rather than a confirmed diagnosis.
