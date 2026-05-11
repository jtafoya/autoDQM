#!/bin/bash
# Combine per-run outputs from the 260429 EXT apply-to-runs exercise and
# evaluate them (reports + plots), keeping results separate from the
# initial training-list outputs.
#
# Per-run logs live in:
#   logs/applyToRuns_260429_EXT/<tag>_run<N>.csv
#
# Combine writes:
#   logs/applyToRuns_260429_EXT/<tag>.csv        (concatenated)
#   logs/applyToRuns_260429_EXT/<tag>_paths.txt  (merged path cache)
#
# Evaluate writes:
#   reports/applyToRuns_260429_EXT/<tag>/        (framework_good_runs.json etc.)
#   plots/applyToRuns_260429_EXT/<tag>/          (all diagnostic plots)
#
# Scope:
#   trigger config : ignoreDAQConfig (with triggerConfig)
#   contaminations : 0.001, 0.002
#   z-thresholds   : 7σ, 8σ
#   variant        : trigger_lvds (full feature set: digi + trigger rates + LVDS)
#   qualities      : Loose, Medium, Tight
#   total          : 12 combinations
#
# Run from the isolation_forest/ directory:
#   bash _auxiliar_scripts/combine_and_evaluate_applyToRuns_260429_EXT.sh

set -euo pipefail

cd "$(dirname "$0")/.."

contaminations=("0p001" "0p002")
sigmas=("7" "8")
qualities=("Loose" "Medium" "Tight")

n_total=$(( ${#contaminations[@]} * ${#sigmas[@]} * ${#qualities[@]} ))
echo "============================================================"
echo "  combine_and_evaluate_applyToRuns_260429_EXT"
echo "  $n_total combinations"
echo "  Start: $(date -u)"
echo "============================================================"
echo ""

# ── Pass 1: combine per-run CSVs ─────────────────────────────────────────────
echo "────────────────────────────────────────────────────────────"
echo "  PASS 1 — combine"
echo "────────────────────────────────────────────────────────────"
n=0
for c in "${contaminations[@]}"; do
    for z in "${sigmas[@]}"; do
        cfg="configs/config_ignoreDAQConfig__ifContamination_${c}__zThreshold_${z}sigma.yaml"
        model_tag="sweep__ifContamination_${c}__zThreshold_${z}sigma_260429_EXT"
        for q in "${qualities[@]}"; do
            (( n++ )) || true
            echo ""
            echo "  [$n/$n_total] $cfg  $q"
            python3 -m src.pipeline \
                --config "$cfg" \
                --model-tag "$model_tag" \
                --train-goodRunList \
                --train-goodRunList-quality "$q" \
                --logs-dir logs/applyToRuns_260429_EXT \
                --combine-specific-run-outputs '*'
        done
    done
done

echo ""
echo "────────────────────────────────────────────────────────────"
echo "  PASS 2 — evaluate (reports + plots)"
echo "────────────────────────────────────────────────────────────"
n=0
for c in "${contaminations[@]}"; do
    for z in "${sigmas[@]}"; do
        cfg="configs/config_ignoreDAQConfig__ifContamination_${c}__zThreshold_${z}sigma.yaml"
        model_tag="sweep__ifContamination_${c}__zThreshold_${z}sigma_260429_EXT"
        for q in "${qualities[@]}"; do
            (( n++ )) || true
            echo ""
            echo "  [$n/$n_total] $cfg  $q"
            python3 -m src.pipeline \
                --config "$cfg" \
                --model-tag "$model_tag" \
                --train-goodRunList \
                --train-goodRunList-quality "$q" \
                --logs-dir    logs/applyToRuns_260429_EXT \
                --reports-dir reports/applyToRuns_260429_EXT \
                --plots-dir   plots/applyToRuns_260429_EXT \
                --skip-train --skip-apply --skip-all-plots
        done
    done
done

echo ""
echo "============================================================"
echo "  Done: $(date -u)"
echo "============================================================"
