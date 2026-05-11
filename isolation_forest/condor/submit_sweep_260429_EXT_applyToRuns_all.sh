#!/bin/bash
# Submit one Condor cluster (86-job array) per model for the EXT apply-to-runs exercise.
#
# 12 submissions total:
#   1 trigger-config variant (ignoreDAQConfig — with triggerConfig)
#   × 2 if_contamination values (0.001, 0.002)
#   × 2 z_threshold values (7σ, 8σ)
#   × 1 feature variant (trigger_lvds — full feature set: digi + trigger rates + LVDS)
#   × 3 goodRunsList quality selections (Loose, Medium, Tight)
#
# Each cluster covers runs 1422–2276 (86 jobs × 10 runs, 20 % of files per run).
# Total: 12 × 86 = 1032 jobs.
#
# Run from the isolation_forest/ directory:
#   bash condor/submit_sweep_260429_EXT_applyToRuns_all.sh

set -euo pipefail

SUBFILE="condor/submit_sweep_260429_EXT_applyToRuns.sub"

trigger_configs=("config_ignoreDAQConfig")
contaminations=("0p001" "0p002")
sigmas=("7" "8")
variants=("trigger_lvds")
qualities=("Loose" "Medium" "Tight")

n=0
for tc in "${trigger_configs[@]}"; do
    for c in "${contaminations[@]}"; do
        for z in "${sigmas[@]}"; do
            cfg="configs/${tc}__ifContamination_${c}__zThreshold_${z}sigma.yaml"
            for v in "${variants[@]}"; do
                for q in "${qualities[@]}"; do
                    echo "Submitting: $cfg  $v  $q"
                    condor_submit -name bigbird11.cern.ch "$SUBFILE" \
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
echo "Submitted $n clusters ($n × 86 = $((n * 86)) jobs total)."
