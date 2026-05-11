#!/bin/bash
# Submit all applyToRuns jobs for the 2026-04-29 IF hyperparameter sweep.
#
# 108 clusters × 86 jobs = 9 288 total jobs.
#   2 contaminations × 2 z-thresholds × 3 n_estimators × 3 max_samples
#   × 1 variant (trigger_lvds) × 3 qualities (Loose, Medium, Tight)
#   × 86 batches (runs 1422–2276, 10 runs/job)
#
# Requires training jobs (submit_sweep_260429_IFhp.sub) to have finished.
# Run from the isolation_forest/ directory:
#   bash condor/submit_sweep_260429_IFhp_applyToRuns_all.sh

set -euo pipefail

cd "$(dirname "$0")/.."

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_200__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_200__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_200__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_300__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_300__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_300__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_7sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_200__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_200__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_200__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_300__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_300__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_300__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p001__zThreshold_8sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_200__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_200__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_200__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

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
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_300__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_300__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_300__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_7sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_200__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_200__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_200__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_200__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_200__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_300__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_300__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_300__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_300__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_300__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_500__maxSamp_256.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_500__maxSamp_1024.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Loose

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Medium

condor_submit condor/submit_sweep_260429_IFhp_applyToRuns.sub \
    CONFIG=configs/config_ignoreDAQConfig__ifContamination_0p002__zThreshold_8sigma__nEst_500__maxSamp_4096.yaml \
    VARIANT=trigger_lvds \
    QUALITY=Tight
