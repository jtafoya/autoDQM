#!/bin/bash
# Combine per-run outputs from the 260429 IFhp apply-to-runs exercise and
# evaluate them (reports only, no plots), keeping results separate from the
# initial training-list outputs.
#
# Per-run logs live in:
#   logs/applyToRuns_260429_IFhp/<tag>_run<N>.csv
#
# Combine writes:
#   logs/applyToRuns_260429_IFhp/<tag>.csv        (concatenated)
#   logs/applyToRuns_260429_IFhp/<tag>_paths.txt  (merged path cache)
#
# Evaluate writes:
#   reports/applyToRuns_260429_IFhp/<tag>/        (framework_good_runs.json etc.)
#
# Scope:
#   trigger config : ignoreDAQConfig (with triggerConfig)
#   contaminations : 0.001, 0.002
#   z-thresholds   : 7σ, 8σ
#   n_estimators   : 200, 300, 500
#   max_samples    : 256, 1024, 4096
#   variant        : trigger_lvds (full feature set: digi + trigger rates + LVDS)
#   qualities      : Loose, Medium, Tight
#   total          : 108 combinations
#
# Run from the isolation_forest/ directory:
#   bash _auxiliar_scripts/combine_and_evaluate_applyToRuns_260429_IFhp.sh

set -euo pipefail

cd "$(dirname "$0")/.."

contaminations=("0p001" "0p002")
sigmas=("7" "8")
n_estimators=("200" "300" "500")
max_samples=("256" "1024" "4096")
qualities=("Loose" "Medium" "Tight")

n_total=$(( ${#contaminations[@]} * ${#sigmas[@]} * ${#n_estimators[@]} * ${#max_samples[@]} * ${#qualities[@]} ))
echo "============================================================"
echo "  combine_and_evaluate_applyToRuns_260429_IFhp"
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
        for ne in "${n_estimators[@]}"; do
            for ms in "${max_samples[@]}"; do
                cfg="configs/config_ignoreDAQConfig__ifContamination_${c}__zThreshold_${z}sigma__nEst_${ne}__maxSamp_${ms}.yaml"
                model_tag="sweep__ifContamination_${c}__zThreshold_${z}sigma__nEst_${ne}__maxSamp_${ms}_260429_IFhp"
                for q in "${qualities[@]}"; do
                    (( n++ )) || true
                    full_tag="${model_tag}_${q}_ignoreDAQConfig"
                    # Skip if already combined
                    if [ -f "logs/applyToRuns_260429_IFhp/${full_tag}.csv" ]; then
                        echo "  [$n/$n_total] SKIP (already combined): $full_tag"
                        continue
                    fi
                    # Skip if no per-run CSVs exist (model may not have been trained yet)
                    n_csvs=$(find "logs/applyToRuns_260429_IFhp/" -maxdepth 1 -name "${full_tag}_run*.csv" 2>/dev/null | wc -l)
                    if [ "$n_csvs" -eq 0 ]; then
                        echo "  [$n/$n_total] SKIP (no per-run CSVs): $full_tag"
                        continue
                    fi
                    echo ""
                    echo "  [$n/$n_total] $cfg  $q  ($n_csvs run CSVs)"
                    python3 -m src.pipeline \
                        --config "$cfg" \
                        --model-tag "$model_tag" \
                        --train-goodRunList \
                        --train-goodRunList-quality "$q" \
                        --logs-dir logs/applyToRuns_260429_IFhp \
                        --combine-specific-run-outputs '*'
                done
            done
        done
    done
done

echo ""
echo "────────────────────────────────────────────────────────────"
echo "  PASS 2 — evaluate (reports only, no plots)"
echo "────────────────────────────────────────────────────────────"
n=0
for c in "${contaminations[@]}"; do
    for z in "${sigmas[@]}"; do
        for ne in "${n_estimators[@]}"; do
            for ms in "${max_samples[@]}"; do
                cfg="configs/config_ignoreDAQConfig__ifContamination_${c}__zThreshold_${z}sigma__nEst_${ne}__maxSamp_${ms}.yaml"
                model_tag="sweep__ifContamination_${c}__zThreshold_${z}sigma__nEst_${ne}__maxSamp_${ms}_260429_IFhp"
                for q in "${qualities[@]}"; do
                    (( n++ )) || true
                    full_tag="${model_tag}_${q}_ignoreDAQConfig"
                    # Skip if combined CSV does not exist
                    if [ ! -f "logs/applyToRuns_260429_IFhp/${full_tag}.csv" ]; then
                        echo "  [$n/$n_total] SKIP (no combined CSV): $full_tag"
                        continue
                    fi
                    echo ""
                    echo "  [$n/$n_total] $cfg  $q"
                    python3 -m src.pipeline \
                        --config "$cfg" \
                        --model-tag "$model_tag" \
                        --train-goodRunList \
                        --train-goodRunList-quality "$q" \
                        --logs-dir    logs/applyToRuns_260429_IFhp \
                        --reports-dir reports/applyToRuns_260429_IFhp \
                        --plots-dir   plots/applyToRuns_260429_IFhp \
                        --skip-train --skip-apply --skip-all-plots
                done
            done
        done
    done
done

echo ""
echo "============================================================"
echo "  Done: $(date -u)"
echo "============================================================"
