#!/bin/bash
# Submit applyToRuns jobs for the 285 models retrained via submit_sweep_260521_train_retry.sub.
#
# 285 clusters × 60 jobs = 17100 total apply jobs.
#
# Run from the isolation_forest/ directory:
#   bash condor/submit_sweep_260521_train_retry_applyToRuns_all.sh

set -euo pipefail

cd "$(dirname "$0")/.."

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p001__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p005__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p01__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_6sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_7sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_1.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_2.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_3.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=trigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_lvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_4.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=trigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_lvds \
    TC=ignoreConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=withConfig

condor_submit condor/submit_sweep_260521_applyToRuns.sub \
    CONFIG=configs/config_260521__ifContamination_0p05__zThreshold_8sigma__alertConsec_5.yaml \
    VARIANT=notrigger_nolvds \
    TC=ignoreConfig

