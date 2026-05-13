#!/bin/bash
# Combine per-run CSVs and evaluate one IFhp model from the applyToRuns exercise.
# Each job is independent (one model per job), so there are no race conditions
# between the combine and evaluate steps.
#
# Arguments:
#   $1 - CONFIG  : path to sweep config YAML (relative to initialdir)
#   $2 - QUALITY : Loose | Medium | Tight
#
# Writes:
#   logs/applyToRuns_260429_IFhp/<tag>.csv          (combined)
#   reports/applyToRuns_260429_IFhp/<tag>/           (framework_good_runs.json etc.)
#
# Submit from the isolation_forest/ directory:
#   condor_submit condor/submit_applyToRuns_260429_IFhp_combineEval.sub

set -euo pipefail

CONFIG=${1:?Usage: run_applyToRuns_260429_IFhp_combineEval.sh <config> <quality>}
QUALITY=${2:?}

SCRIPT_DIR="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest/condor"
INSTALLATION_PATH="${SCRIPT_DIR}/.."

cd "${INSTALLATION_PATH}"

echo "============================================================"
echo "  autoDQM applyToRuns 260429 IFhp — combine + evaluate"
echo "    config  : $CONFIG"
echo "    quality : $QUALITY"
echo "  Host : $(hostname)"
echo "  Start: $(date -u)"
echo "============================================================"

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
export PYTHONUSERBASE="${HOME}/.local"
export PATH="${HOME}/.local/bin:${PATH}"
export PYTHONPATH="${HOME}/.local/lib/python${PYVER}/site-packages:${INSTALLATION_PATH}:${PYTHONPATH:-}"

echo "  Python : $(python3 --version)  ($(which python3))"

python3 -c "import pandas, sklearn, numpy, scipy, watchdog" || {
    echo "ERROR: required packages not found." >&2
    exit 1
}
echo "  Dependencies: OK"
echo ""

MODEL_TAG=$(python3 -c "
import yaml
with open('${CONFIG}') as f:
    d = yaml.safe_load(f)
print(d.get('model_tag', 'sweep') + '_260429_IFhp')
")
FULL_TAG="${MODEL_TAG}_${QUALITY}_ignoreDAQConfig"
echo "  Full tag: $FULL_TAG"

# Skip if no per-run CSVs exist for this model
n_csvs=$(find logs/applyToRuns_260429_IFhp/ -maxdepth 1 -name "${FULL_TAG}_run*.csv" 2>/dev/null | wc -l)
if [ "$n_csvs" -eq 0 ]; then
    echo "  No per-run CSVs found — nothing to do."
    exit 0
fi
echo "  Per-run CSVs: $n_csvs"
echo ""

echo "── Step 1: combine ──────────────────────────────────────────"
python3 -m src.pipeline \
    --config  "$CONFIG" \
    --model-tag "$MODEL_TAG" \
    --train-goodRunList \
    --train-goodRunList-quality "$QUALITY" \
    --logs-dir logs/applyToRuns_260429_IFhp \
    --combine-specific-run-outputs '*'

echo ""
echo "── Step 2: evaluate ─────────────────────────────────────────"
python3 -m src.pipeline \
    --config  "$CONFIG" \
    --model-tag "$MODEL_TAG" \
    --train-goodRunList \
    --train-goodRunList-quality "$QUALITY" \
    --logs-dir    logs/applyToRuns_260429_IFhp \
    --reports-dir reports/applyToRuns_260429_IFhp \
    --plots-dir   plots/applyToRuns_260429_IFhp \
    --skip-train --skip-apply --skip-all-plots

echo ""
echo "============================================================"
echo "  Done: $FULL_TAG  $(date -u)"
echo "============================================================"
