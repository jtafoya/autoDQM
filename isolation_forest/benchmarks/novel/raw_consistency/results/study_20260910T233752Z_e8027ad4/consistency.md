# Semantic consistency review

Wording differences are NOT counted as diagnostic inconsistency. No accuracy/ground-truth score.
Fill semantic_review.json and rerun --report-only to record a human semantic verdict.

## Run 1620

Identical request bytes: True

### category: pending_human_review

- Trial 1: digitizer_timing_data_corruption
- Trial 2: digitizer_timing_metadata_corruption
- Trial 3: board-local TDC/rollover data corruption

### cause: pending_human_review

- Trial 1: The observed symptom is a persistent, channel-block-localized corruption of TDC and TDCRollovers values on digitizer channels 88-95. The inferred mechanism is invalid timing-word generation or interpretation—such as a digitizer timing-register/firmware state fault, synchronization fault, or decoder/schema error. The supplied evidence cannot distinguish among those mechanisms, so the underlying hardware/software cause is unknown. No exact resolved historical match was supplied.
- Trial 2: The observable symptom is invalid TDC/TDCRollovers metadata confined to digitizer channels 88-95. The inferred mechanism is board- or readout-group-specific corruption, misdecoding, or misconfiguration of timing-counter fields: channels 88-90 report an identical constant TDC of 149602000000000 while their rollover fields are nonzero and implausibly large; channels 91-93 report zero TDC with very large rollover values; and channels 94-95 have nearly constant TDC medians around 438087000000 with large rollover values and occasional extreme TDC values. Channels through 87 instead have ordinary varying TDC values and zero rollovers. The exact root cause—firmware/register state, counter-width or data-type decoding, serialization, or hardware timing logic—is unknown from the supplied summaries.
- Trial 3: Primary root cause is unknown. The observed symptom is persistent, channel-local corruption or misinterpretation of the TDC and TDCRollovers fields on contiguous digitizer channels 88-95. The most likely mechanism is a shared timing-counter readout, firmware/configuration, schema, or decoder fault affecting that channel block, rather than a PMT/HV or LVDS signal failure. The supplied summaries cannot distinguish corrupted source words from incorrect downstream decoding.

### action: pending_human_review

- Trial 1: Preserve the affected files and inspect raw timing words and event headers for channels 88-95, comparing them with adjacent channel 87 and the documented data schema. Verify channel-to-board grouping, TDC/rollover field offsets, integer widths, signedness, endianness, firmware version, timing-register configuration, clock synchronization, board matching, and any configuration change near run start. If direct readout shows the same invalid values, conditionally reinitialize the affected digitizer/timing logic or reload validated firmware/configuration and confirm recovery in a short test run. If raw words are valid but processed values are not, correct the decoder/schema and reprocess. Do not treat this as an LVDS-pin fault or remap mask indices to same-numbered digitizer channels without validating the supplied physical-pin mapping.
- Trial 2: First preserve and inspect representative original event records from channels 87-95, then verify the channel-to-digitizer-board grouping and decode the TDC/TDCRollovers words directly against the firmware data format, expected counter widths, signedness, byte order, and rollover semantics. Compare firmware, register, clock/synchronization, and readout configuration for the board serving channels 88-95 with a healthy board, and check board matching and DAQ-state logs. Do not use trigger-mask pin numbers as digitizer channel numbers. If direct raw-word inspection confirms a bad board state, conditionally restart or reset that digitizer and reapply validated timing registers; reflash/recompile only if a firmware/software-format mismatch is demonstrated. Start a short validation run and require TDC variation and rollover behavior consistent with healthy channels before accepting data.
- Trial 3: First inspect representative original timing words and event records for channels 87-95 and reproduce the TDC/TDCRollovers decoding with the exact firmware, schema, data type, units, and channel mapping. Compare against a known-good run and verify board identity, synchronization, counter-reset behavior, firmware/configuration, and any run-time configuration changes. If raw words are valid but decoded incorrectly, fix the parser/schema and reprocess the data. If the source counters are demonstrably stuck or malformed, conditionally reconfigure or restart the affected digitizer, then reflash validated firmware or replace/repair the board only if the fault persists. Do not alter PMT HV or LVDS cabling without independent evidence of a signal-path fault.

## Run 1640

Identical request bytes: True

### category: pending_human_review

- Trial 1: localized_digitizer_readout_loss
- Trial 2: localized_paired_channel_readout_loss
- Trial 3: digitizer_readout_channel_pair_dropout

### cause: pending_human_review

- Trial 1: Unknown root cause. The observed mechanism is complete loss of event records for digitizer channels 32 and 33 beginning at subrun 520. The leading hypothesis is a localized digitizer/readout-path failure, reset, or unintended disablement after subrun 519; the supplied evidence cannot distinguish hardware lockup, link failure, configuration change, or upstream trigger-path loss.
- Trial 2: OBSERVED symptom: digitizer channels 32 and 33 have no supplied channel measurements from subrun 520 through 741 after being present through subrun 519. INFERRED mechanism: a localized readout, channel-enable/configuration, or data-decoding failure affecting this channel pair began at the 519/520 boundary. The primary underlying hardware or software cause is unknown. A static trigger mask is not established as the cause, and persistent LVDS-pin failure or a global trigger-rate failure is disfavored by the supplied aggregate telemetry. An exact historical match is absent; digitizer lockup and intermittent LVDS connection cases are only partial analogies.
- Trial 3: Unknown. The observable symptom is complete loss of digitizer channels 32 and 33 beginning at subrun 520. The evidence localizes the likely mechanism to the digitizer-side acquisition/readout path shared by that channel pair, but it does not distinguish an undocumented channel-enable or zero-suppression change, digitizer/firmware state failure, local power or signal-connection loss, or downstream decoding/filtering. A trigger-board LVDS failure is less favored because the supplied LVDS summary reports no persistently zero or missing signal pins. Separate, persistent TDC/rollover inconsistencies on channels 88-95 suggest an additional data-decoding or digitizer-timing integrity problem that may or may not share the same cause.

### action: pending_human_review

- Trial 1: First compare channel-level event counters, board-matching efficiency, queue occupancy, digitizer status, and configuration immediately across subruns 519-520. Compare the correctly mapped LVDS physical pin for digitizer channels 32/33 before and after that boundary; do not equate a trigger-mask index with the same-numbered digitizer channel. If the LVDS input continues while digitizer records stop, conditionally reinitialize or restart the affected digitizer/readout process and inspect its data, clock, and trigger links. If LVDS input also stops, inspect and reseat the corresponding mapped LVDS connection and verify masking/configuration. Independently validate timing-field decoding for channels 88-95 against firmware and data-format definitions before using their TDC or rollover values.
- Trial 2: First verify the channel-to-board and physical-pin mapping, then compare DAQ/channel-enable configuration, digitizer status, firmware state, and raw fragment inventory immediately before and after subrun 520. Check board matching, synchronization, queue occupancy, per-board event counts, and whether channels 32/33 are absent in raw digitizer fragments or only lost during decoding. If raw fragments are absent and the affected digitizer path is unresponsive, conditionally reinitialize or restart the affected digitizer/DAQ process and confirm recovery in a new run. If fragments exist but decoded channels do not, conditionally correct the channel map or decoder/configuration. Inspect or reseat the mapped LVDS/signal connection only if pin-level or board-matching tests localize the fault there; do not use mask indices as digitizer-channel numbers.
- Trial 3: First compare the raw event/channel inventory and effective DAQ configuration immediately before and after subrun 520, including channel-enable state, zero suppression, thresholds, firmware version and any restart or operator intervention. Check board matching, synchronization, digitizer error/status registers, queue occupancy and per-board event counts; these telemetry are not supplied here. Verify the physical mapping before any intervention: trigger-mask indices are physical pins and must not be treated as same-number digitizer channels. If channels 32/33 are enabled but their digitizer path is unresponsive, conditionally stop the run, restart or reinitialize the affected digitizer/DAQ process, then start a new run and verify both channels reappear. If electronics remain responsive but signals are absent, conditionally inspect and reseat the mapped signal, power and digitizer-side connections. Independently validate the TDC/TDCRollovers decoder and firmware/schema for channels 88-95 before using their timing data.

## Run 1642

Identical request bytes: True

### category: pending_human_review

- Trial 1: LVDS_signal_loss
- Trial 2: localized_lvds_signal_loss
- Trial 3: persistent_lvds_signal_loss

### cause: pending_human_review

- Trial 1: Loss of the LVDS signal on physical signal pin 16, which maps to digitizer channels 32 and 33. The evidence localizes the failure to that shared LVDS path, but does not establish whether the underlying cause was an unseated/degraded connector or jumper, an upstream driver fault, or a transient configuration/state change. The reappearance of both channels in subruns 201-202 indicates recovery or intermittency rather than a permanently dead digitizer pair.
- Trial 2: The observed mechanism is a localized loss or inactivity of the LVDS signal on pin 16, which maps to digitizer channels 32 and 33: both channels are absent for subruns 1-200 while the pin is persistently zero, followed by limited reappearance in subruns 201-202. The underlying root cause is unknown. The leading hypotheses are an intermittent/degraded LVDS connection, cable or trigger-board input, or an unintended source/configuration disablement; the supplied evidence cannot distinguish these.
- Trial 3: The observed mechanism is loss of the signal on LVDS physical pin 16, the mapped path for digitizer channels 32 and 33, causing those channels to be absent in subruns 1-200. Their sparse reappearance in subruns 201-202 suggests an intermittent or restored path. The underlying root cause is unknown; plausible causes include an unseated/degraded pin, jumper or cable, a failed upstream signal source, or an unrecorded configuration/electronics-state change.

### action: pending_human_review

- Trial 1: Conditionally treat physical LVDS pin 16 and its shared path to digitizer channels 32/33 as the primary fault location: while the run is stopped, verify the repository mapping, inspect and reseat the pin, jumper, and associated connectors at both ends, and check continuity or swap the path with a known-good LVDS input. Start a new run after each change and confirm nonzero pin-16 counts and normal occupancy on both channels. Before physical intervention, compare subrun 200-201 configuration and DAQ-state logs to exclude an intentional enable/configuration change. Restart or service a digitizer only if board-matching, synchronization, or readout diagnostics specifically show a digitizer-state failure.
- Trial 2: First verify that LVDS pin 16 and its mapped digitizer channels 32/33 were intended to be enabled, using the physical-pin mapping rather than equating mask indices with digitizer channels. With the run stopped, inspect and reseat the pin-16 LVDS connector and associated jumper/cable at both ends, then start a short validation run and confirm stable pin counts, channel occupancy, and board matching. If movement changes the behavior or the path remains intermittently dead, conditionally replace or swap the cable/connection and retest. If the hardware path is sound, inspect source enablement and within-run configuration. Separately validate the timing-field decoding for channels 88-95 before treating their TDC/rollover values as detector behavior.
- Trial 3: With the run stopped, verify the repository mapping and inspect, continuity-test, and carefully reseat the physical LVDS pin-16 path at both ends, including its jumper and associated signal connections. Start a new run after each change and confirm that channels 32 and 33 have sustained occupancy and that pin 16 has normal counts. Before replacing hardware, compare live source signals at the digitizer and trigger-board ends and inspect within-run configuration, board-matching, synchronization, and queue telemetry. Replace or repair a cable/pin/source component only if these checks localize the loss; if an undocumented configuration change explains it, restore and record the intended configuration instead.

## Run 1702

Identical request bytes: True

### category: pending_human_review

- Trial 1: digitizer_timing_metadata_corruption
- Trial 2: digitizer_timing_readout_corruption
- Trial 3: digitizer_TDC_rollover_data_corruption

### cause: pending_human_review

- Trial 1: The observable failure is corruption or misinterpretation of TDC and rollover fields localized to digitizer channels 88-95. The underlying root cause is unknown from the supplied telemetry; plausible mechanisms include a firmware/data-format mismatch, malformed timing words, or a board-local synchronization/readout fault. This is not an exact match to a supplied historical case and is not supported as an LVDS, PMT-base, global-trigger, or complete digitizer-lockup failure.
- Trial 2: The observable symptom is corrupted or stuck TDC/TDCRollovers data localized to digitizer channels 88-95. The most likely mechanism is failure or mis-decoding of a shared timing counter/readout path for that channel group, rather than loss of detector pulses. The underlying root cause—firmware state, register/configuration error, serialization/decoding defect, synchronization fault, or hardware counter failure—is unknown from the supplied telemetry.
- Trial 3: Observed mechanism: the TDC and TDCRollovers outputs for digitizer channels 88-95 are stuck, zero, or populated with implausibly large counter-like values, while those channels remain present. This is most consistent with corruption in the affected digitizer timing/counter state or its decoding. The underlying root cause is unknown; supplied evidence cannot distinguish a firmware/register-state fault from a packed-data or software-decoder/schema error.

### action: pending_human_review

- Trial 1: First validate raw timing-word decoding for channels 88-95 against the installed digitizer firmware and configuration, compare the same events with neighboring channels 80-87, and inspect board synchronization/matching and error counters. Confirm the physical board/channel grouping rather than using trigger-mask indices as channel numbers. If the stored words are valid but interpreted with the wrong schema, correct the decoder or firmware/configuration compatibility and reprocess the data. If live diagnostics instead show a board-local synchronization or readout fault, stop the run and conditionally reset/restart the affected digitizer/DAQ; reflash or replace hardware only after firmware and cabling checks isolate that cause. Verify recovery in a new run by requiring ordinary, nonconstant TDC distributions, plausible rollover values, full board matching, and unchanged normal trigger/LVDS behavior.
- Trial 2: First preserve and inspect event-level timing words for channels 88-95 and compare their raw encoding, board identity, firmware version, timing registers, clock/reset state, event counters, and timestamps with channels 80-87. Check board matching, synchronization, queue occupancy, and digitizer-versus-trigger-board rates. Do not translate trigger-mask indices directly into digitizer channel numbers; verify the physical mapping. If corruption is confirmed at the digitizer output, conditionally reset or restart the affected digitizer/DAQ path and reload validated firmware and configuration; reflash/recompile only if a firmware/software mismatch is demonstrated. If raw words are valid but processed values are not, correct the TDC/rollover decoder instead. Validate recovery in a new run by requiring plausible, varying TDC values and rollover behavior while occupancy and trigger rate remain stable.
- Trial 3: First quarantine TDC and TDCRollovers from timing analyses for channels 88-95. Compare packed raw timing words against decoded values, verify the channel-to-board mapping and firmware/decoder version, and inspect board matching, synchronization, and DAQ state. If raw words are valid, correct the decoder/schema and reprocess the data. If raw words themselves are stuck or corrupted, conditionally reset or restart the affected digitizer/DAQ and verify normal TDC and rollover distributions in a new run; reflash firmware only if a version or configuration mismatch is confirmed. Do not replace PMT/HV or LVDS hardware without additional evidence.

## Run 1703

Identical request bytes: False

### category: pending_human_review

- Trial 1: digitizer_timing_metadata_corruption
- Trial 2: NO COMPLETED DIAGNOSIS
- Trial 3: NO COMPLETED DIAGNOSIS

### cause: pending_human_review

- Trial 1: The observed failure mechanism is corrupted, stuck, or sentinel-like TDC/TDCRollovers metadata in the contiguous channel block 88-95. The underlying root cause is unknown from the supplied telemetry; leading hypotheses are a digitizer timing-register/firmware/readout fault or a decoding/data-layout error affecting that block. Stable trigger telemetry, normal LVDS pin coverage, and persistent channel presence argue against a system-wide trigger failure, LVDS disconnection, PMT/HV loss, or complete digitizer lockup.
- Trial 2: NO COMPLETED DIAGNOSIS
- Trial 3: NO COMPLETED DIAGNOSIS

### action: pending_human_review

- Trial 1: First preserve the files and validate the TDC and TDCRollovers field layout, units, signedness, and rollover reconstruction for channels 88-95 against a known-good file or independent decoder. Identify which digitizer hardware/firmware serves this contiguous block, then inspect its firmware version, timing-register configuration, clock/synchronization state, and raw register words. Check board matching and DAQ-state telemetry during a controlled test run. If decoding is correct and the hardware timing fields remain stuck or impossible, conditionally restart/reinitialize the affected digitizer and DAQ process; reflash/recompile only after confirming a firmware mismatch. Quarantine timing values from channels 88-95 until validated, while retaining pulse/occupancy data separately if operationally acceptable.
- Trial 2: NO COMPLETED DIAGNOSIS
- Trial 3: NO COMPLETED DIAGNOSIS

## Run 2126

Identical request bytes: False

### category: pending_human_review

- Trial 1: NO COMPLETED DIAGNOSIS
- Trial 2: NO COMPLETED DIAGNOSIS
- Trial 3: NO COMPLETED DIAGNOSIS

### cause: pending_human_review

- Trial 1: NO COMPLETED DIAGNOSIS
- Trial 2: NO COMPLETED DIAGNOSIS
- Trial 3: NO COMPLETED DIAGNOSIS

### action: pending_human_review

- Trial 1: NO COMPLETED DIAGNOSIS
- Trial 2: NO COMPLETED DIAGNOSIS
- Trial 3: NO COMPLETED DIAGNOSIS
