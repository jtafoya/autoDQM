#!/bin/bash
# Submit one Condor cluster (855-job array) per model for the apply-to-runs exercise.
#
# 48 submissions total:
#   2 trigger-config variants (ignoreDAQConfig, ignoreTriggerConfig_ignoreDAQConfig)
#   × 2 if_contamination values (0.005, 0.01)
#   × 1 z_threshold value (7 sigma)
#   × 4 feature variants (trigger_lvds/nolvds, notrigger_lvds/nolvds)
#   × 3 goodRunsList quality selections (Loose, Medium, Tight)
#
# Each cluster covers runs 1422–2276 (855 jobs, 20 % of files per run).
#
# Run from the isolation_forest/ directory:
#   bash condor/submit_sweep_260429_applyToRuns_all.sh

set -euo pipefail

SUBFILE="condor/submit_sweep_260429_applyToRuns.sub"

trigger_configs=(
    "config_ignoreDAQConfig"
    "config_ignoreTriggerConfig_ignoreDAQConfig"
)
contaminations=("0p005" "0p01")
sigmas=("7")
variants=("trigger_lvds" "trigger_nolvds" "notrigger_lvds" "notrigger_nolvds")
qualities=("Loose" "Medium" "Tight")

n=0
for tc in "${trigger_configs[@]}"; do
    for c in "${contaminations[@]}"; do
        for z in "${sigmas[@]}"; do
            cfg="configs/${tc}__ifContamination_${c}__zThreshold_${z}sigma.yaml"
            for v in "${variants[@]}"; do
                for q in "${qualities[@]}"; do
                    echo "Submitting: $cfg  $v  $q"
                    condor_submit "$SUBFILE" \
                        "CONFIG=$cfg" \
                        "VARIANT=$v" \
                        "QUALITY=$q"
                    (( n++ )) || true
                done
            done
        done
    done
done

echo ""
echo "Submitted $n clusters (${n} × 855 = $((n * 855)) jobs total)."
