#!/bin/bash
# Submit all applyToRuns jobs for the 2026-05-19 sweep.
#
# 480 clusters × 64 jobs = 30720 total apply jobs.
#   3 z-thresholds × 4 contaminations × 5 consecutive_n
#   × 4 feature variants × 2 triggerConfig states
#   × 64 batches (runs 1601–2238, 10 runs/job)
#
# Requires training jobs (submit_sweep_260519.sub) to have finished.
# Run from the isolation_forest/ directory:
#   bash condor/submit_sweep_260519_applyToRuns_all.sh

set -euo pipefail

cd "$(dirname "$0")/.."

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p001__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p005__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p01__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260519_applyToRuns.sub \
    CONFIG=configs/config_260519__ifContamination_0p05__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig
