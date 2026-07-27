#!/bin/bash
# run_combineEval_juan_reproduction.sh — combine + evaluate node of juan_repro.dag.
#
# Runs pengy's two manual post-apply steps as one condor job so the whole
# reproduction (train → apply array → combine/evaluate) can be chained
# unattended: merge the 97 per-run CSVs into one log, then evaluate against
# the training good list (text-list ground truth — the accounting behind his
# 473/13432 = 3.5%) and write the report.
set -euo pipefail

INSTALLATION_PATH="/afs/cern.ch/user/l/lbailloe/private/autoDQM/isolation_forest"
CONFIG="configs/juan_reproduction_digi_z8_if0001_train20_seed42.yaml"
MODEL_TAG="juan_reproduction_digi_z8_if0001_train20_seed42"
RESOLVED_TAG="${MODEL_TAG}_noTrigger_noLVDS_ignoreTriggerConfig"
FEATURE_FLAGS=(--no-trigger --no-trigger-LVDS --no-trigger-config)

cd "${INSTALLATION_PATH}"

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
export PYTHONUSERBASE="${HOME}/.local"
export PATH="${HOME}/.local/bin:${PATH}"
export PYTHONPATH="${HOME}/.local/lib/python${PYVER}/site-packages:${INSTALLATION_PATH}:${PYTHONPATH:-}"
python3 -c "import pandas, sklearn, numpy, scipy, watchdog" || {
    echo "ERROR: required packages not found." >&2; exit 1; }

# Coverage before combining: per-run CSVs published vs runs in the manifest.
n_csvs=$(find "logs/${RESOLVED_TAG}" -name "${RESOLVED_TAG}_run*.csv" 2>/dev/null | wc -l)
n_runs=$(wc -l < condor/apply_good_training_runs.txt)
echo "  Coverage: ${n_csvs} per-run CSV(s) of ${n_runs} manifest run(s)"
[ "$n_csvs" -gt 0 ] || { echo "ERROR: no per-run CSVs to combine." >&2; exit 1; }

echo "── Step 1: combine ──────────────────────────────────────────"
python3 -m src.pipeline \
    --config    "${CONFIG}" \
    --model-tag "${MODEL_TAG}" \
    --combine-specific-run-outputs '*' \
    "${FEATURE_FLAGS[@]}"

echo ""
echo "── Step 2: evaluate + report ────────────────────────────────"
# step_evaluate AUTO-SKIPS when eval_summary.txt exists — wipe this tag's
# report dir so a re-run (or DAG retry) always evaluates the fresh log.
rm -rf "reports/${RESOLVED_TAG}"
python3 -m src.pipeline \
    --config    "${CONFIG}" \
    --model-tag "${MODEL_TAG}" \
    --skip-train --skip-apply --skip-all-plots \
    "${FEATURE_FLAGS[@]}"

echo ""
echo "  Reference (pengy): Total 13432 | ok 12882 (95.9%) | warn 77 (0.6%) | alert 473 (3.5%)"
grep -E "Total subruns|True Negative|Mild anomaly|Unverifiable|False Positive" \
    "reports/${RESOLVED_TAG}/eval_summary.txt" || true
echo ""
echo "DONE — full summary: reports/${RESOLVED_TAG}/eval_summary.txt"
