#!/bin/bash
# Combine per-run CSVs and evaluate one 260519 model.
#
# Arguments:
#   $1 - CONFIG  : path to sweep config YAML (relative to initialdir)
#   $2 - VARIANT : feature variant
#   $3 - TC      : withConfig | ignoreConfig

set -euo pipefail

CONFIG=${1:?Usage: run_sweep_260519_combineEval.sh <config> <variant> <tc>}
VARIANT=${2:?}
TC=${3:?}

SCRIPT_DIR="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest/condor"
INSTALLATION_PATH="${SCRIPT_DIR}/.."

cd "${INSTALLATION_PATH}"

echo "============================================================"
echo "  autoDQM sweep 260519 — combine + evaluate"
echo "    config  : $CONFIG"
echo "    variant : $VARIANT"
echo "    trigCfg : $TC"
echo "  Host : $(hostname)"
echo "  Start: $(date -u)"
echo "============================================================"

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
export PYTHONUSERBASE="${HOME}/.local"
export PATH="${HOME}/.local/bin:${PATH}"
export PYTHONPATH="${HOME}/.local/lib/python${PYVER}/site-packages:${INSTALLATION_PATH}:${PYTHONPATH:-}"

python3 -c "import pandas, sklearn, numpy, scipy, watchdog" || {
    echo "ERROR: required packages not found." >&2; exit 1
}
echo "  Dependencies: OK"
echo ""

MODEL_TAG=$(python3 -c "
import yaml
with open('${CONFIG}') as f:
    d = yaml.safe_load(f)
print(d.get('model_tag', 'sweep'))
")

FLAGS=()
case $VARIANT in
    trigger_lvds)     ;;
    trigger_nolvds)   FLAGS=(--no-trigger-LVDS) ;;
    notrigger_lvds)   FLAGS=(--no-trigger) ;;
    notrigger_nolvds) FLAGS=(--no-trigger --no-trigger-LVDS) ;;
    *) echo "ERROR: unknown variant '$VARIANT'" >&2; exit 1 ;;
esac

TC_FLAGS=()
if [ "$TC" = "ignoreConfig" ]; then
    TC_FLAGS=(--no-trigger-config)
fi

# Skip if no per-run CSVs exist yet
n_csvs=$(find "logs/applyToRuns_260519/" -name "*.csv" 2>/dev/null | grep -c "${MODEL_TAG}" || true)
if [ "$n_csvs" -eq 0 ]; then
    echo "  No per-run CSVs found for $MODEL_TAG — nothing to do."
    exit 0
fi
echo "  Per-run CSVs found: $n_csvs"
echo ""

echo "── Step 1: combine ──────────────────────────────────────────"
python3 -m src.pipeline \
    --config    "$CONFIG" \
    --model-tag "$MODEL_TAG" \
    --logs-dir  logs/applyToRuns_260519 \
    --combine-specific-run-outputs '*' \
    "${FLAGS[@]}" "${TC_FLAGS[@]}"

echo ""
echo "── Step 2: evaluate + report ────────────────────────────────"
python3 -m src.pipeline \
    --config      "$CONFIG" \
    --model-tag   "$MODEL_TAG" \
    --logs-dir    logs/applyToRuns_260519 \
    --reports-dir reports/applyToRuns_260519 \
    --plots-dir   plots/applyToRuns_260519 \
    --skip-train --skip-apply --skip-all-plots \
    "${FLAGS[@]}" "${TC_FLAGS[@]}"

echo ""
echo "============================================================"
echo "  Done: $MODEL_TAG  $VARIANT  $TC  $(date -u)"
echo "============================================================"
