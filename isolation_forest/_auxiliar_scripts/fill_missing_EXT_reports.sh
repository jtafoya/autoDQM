#!/bin/bash
# Run evaluate + report + plots for all 260429_EXT tags that are missing outputs.
# Training and apply are skipped; the existing logs/<tag>.csv is used.
# Tags that already have reports/plots will be auto-skipped by the pipeline.
#
# Run from the isolation_forest/ directory:
#   bash _auxiliar_scripts/fill_missing_EXT_reports.sh

set -euo pipefail
cd "$(dirname "$0")/.."

trigger_configs=(
    "config_ignoreDAQConfig"
    "config_ignoreTriggerConfig_ignoreDAQConfig"
)

# Full EXT contamination / z-threshold grid (matches submit_sweep_260429_EXT.sub)
declare -A z_for_cont=(
    [0p001]="5 6 7 8 9"
    [0p002]="5 6 7 8 9"
    [0p005]="8 9"
    [0p01]="8 9"
    [0p02]="8 9"
    [0p05]="8 9"
)

variants=("trigger_lvds" "trigger_nolvds" "notrigger_lvds" "notrigger_nolvds")
qualities=("Loose" "Medium" "Tight")

declare -A variant_flags=(
    [trigger_lvds]=""
    [trigger_nolvds]="--no-trigger-LVDS"
    [notrigger_lvds]="--no-trigger"
    [notrigger_nolvds]="--no-trigger --no-trigger-LVDS"
)

n=0; total=432
echo "============================================================"
echo "  fill_missing_EXT_reports — evaluate + report + plots"
echo "  Start: $(date -u)"
echo "============================================================"
echo ""

for tc in "${trigger_configs[@]}"; do
    for c in "${!z_for_cont[@]}"; do
        for z in ${z_for_cont[$c]}; do
            cfg="configs/${tc}__ifContamination_${c}__zThreshold_${z}sigma.yaml"
            model_tag="sweep__ifContamination_${c}__zThreshold_${z}sigma_260429_EXT"
            for v in "${variants[@]}"; do
                flags="${variant_flags[$v]}"
                for q in "${qualities[@]}"; do
                    (( n++ )) || true
                    echo "  [$n/$total] $cfg  $v  $q"
                    # shellcheck disable=SC2086
                    python3 -m src.pipeline \
                        --config "$cfg" \
                        --model-tag "$model_tag" \
                        --train-goodRunList \
                        --train-goodRunList-quality "$q" \
                        --skip-train --skip-apply \
                        $flags
                done
            done
        done
    done
done

echo ""
echo "============================================================"
echo "  Done: $(date -u)"
echo "============================================================"
