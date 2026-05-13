#!/bin/bash
# Submit apply-to-runs jobs for the 28 IFhp models that were retrained
# (cluster 11474985) and never had apply-to-runs submitted.
#
# 28 clusters × 86 jobs = 2 408 total jobs.
# Variant: trigger_lvds (full feature set: digi + trigger rates + LVDS).
# Runs 1422–2276, 10 runs/job.
#
# Run from the isolation_forest/ directory:
#   bash condor/submit_sweep_260429_IFhp_applyToRuns_retrain28.sh

set -euo pipefail

cd "$(dirname "$0")/.."

# contamination 0.001 / z 7sigma
condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

# contamination 0.001 / z 8sigma
condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_200__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

# contamination 0.002 / z 7sigma
condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

# contamination 0.002 / z 8sigma
condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_300__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium
