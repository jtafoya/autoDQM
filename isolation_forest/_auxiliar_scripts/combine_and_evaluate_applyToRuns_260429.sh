#!/bin/bash
# Combine per-run outputs from the 260429 apply-to-runs exercise and
# evaluate them (reports + plots), keeping results separate from the
# initial training-list outputs.
#
# Per-run logs live in:
#   logs/applyToRuns_260429/<tag>_run<N>.csv
#
# Combine writes:
#   logs/applyToRuns_260429/<tag>.csv        (concatenated)
#   logs/applyToRuns_260429/<tag>_paths.txt  (merged path cache)
#
# Evaluate writes:
#   reports/applyToRuns_260429/<tag>/        (run_summary.csv etc.)
#   plots/applyToRuns_260429/<tag>/          (all diagnostic plots)
#
# Initial outputs in reports/<tag>/ and plots/<tag>/ are never touched.
#
# Scope — what was actually submitted:
#   trigger configs : ignoreDAQConfig, ignoreTriggerConfig_ignoreDAQConfig
#   contaminations  : 0p005, 0p01
#   z-thresholds    : 7sigma
#   variants        : trigger_lvds, trigger_nolvds, notrigger_lvds, notrigger_nolvds
#   qualities       : Loose, Medium, Tight
#   total           : 48 combinations
#
# Run from the isolation_forest/ directory:
#   bash _auxiliar_scripts/combine_and_evaluate_applyToRuns_260429.sh

set -euo pipefail

cd "$(dirname "$0")/.."

trigger_configs=(
    "config_ignoreDAQConfig"
    "config_ignoreTriggerConfig_ignoreDAQConfig"
)
contaminations=("0p005" "0p01")
sigmas=("7")
variants=("trigger_lvds" "trigger_nolvds" "notrigger_lvds" "notrigger_nolvds")
qualities=("Loose" "Medium" "Tight")

declare -A variant_flags=(
    [trigger_lvds]=""
    [trigger_nolvds]="--no-trigger-LVDS"
    [notrigger_lvds]="--no-trigger"
    [notrigger_nolvds]="--no-trigger --no-trigger-LVDS"
)

n_total=$(( ${#trigger_configs[@]} * ${#contaminations[@]} * ${#sigmas[@]} * ${#variants[@]} * ${#qualities[@]} ))
echo "============================================================"
echo "  combine_and_evaluate_applyToRuns_260429"
echo "  $n_total combinations"
echo "  Start: $(date -u)"
echo "============================================================"
echo ""

# ── Pass 1: combine per-run CSVs ─────────────────────────────────────────────
echo "────────────────────────────────────────────────────────────"
echo "  PASS 1 — combine"
echo "────────────────────────────────────────────────────────────"
n=0
for tc in "${trigger_configs[@]}"; do
    for c in "${contaminations[@]}"; do
        for z in "${sigmas[@]}"; do
            cfg="configs/${tc}__ifContamination_${c}__zThreshold_${z}sigma.yaml"
            model_tag="sweep__ifContamination_${c}__zThreshold_${z}sigma_260429"
            for v in "${variants[@]}"; do
                flags="${variant_flags[$v]}"
                for q in "${qualities[@]}"; do
                    (( n++ )) || true
                    echo ""
                    echo "  [$n/$n_total] $cfg  $v  $q"
                    # shellcheck disable=SC2086
                    python3 -m src.pipeline \
                        --config "$cfg" \
                        --model-tag "$model_tag" \
                        --train-goodRunList \
                        --train-goodRunList-quality "$q" \
                        --logs-dir logs/applyToRuns_260429 \
                        $flags \
                        --combine-specific-run-outputs '*'
                done
            done
        done
    done
done

echo ""
echo "────────────────────────────────────────────────────────────"
echo "  PASS 2 — evaluate (reports + plots)"
echo "────────────────────────────────────────────────────────────"
n=0
for tc in "${trigger_configs[@]}"; do
    for c in "${contaminations[@]}"; do
        for z in "${sigmas[@]}"; do
            cfg="configs/${tc}__ifContamination_${c}__zThreshold_${z}sigma.yaml"
            model_tag="sweep__ifContamination_${c}__zThreshold_${z}sigma_260429"
            for v in "${variants[@]}"; do
                flags="${variant_flags[$v]}"
                for q in "${qualities[@]}"; do
                    (( n++ )) || true
                    echo ""
                    echo "  [$n/$n_total] $cfg  $v  $q"
                    # shellcheck disable=SC2086
                    python3 -m src.pipeline \
                        --config "$cfg" \
                        --model-tag "$model_tag" \
                        --train-goodRunList \
                        --train-goodRunList-quality "$q" \
                        --logs-dir    logs/applyToRuns_260429 \
                        --reports-dir reports/applyToRuns_260429 \
                        --plots-dir   plots/applyToRuns_260429 \
                        $flags \
                        --skip-train --skip-apply
                done
            done
        done
    done
done

echo ""
echo "============================================================"
echo "  Done: $(date -u)"
echo "============================================================"
