#!/bin/bash
# Regenerate one combined _paths.txt for one IFhp model tag.
# Arguments: $1=CONFIG  $2=MODEL_TAG_BASE  $3=QUALITY
#
# Submitted as a 28-job array by submit_combine_IFhp_paths.sub.

set -euo pipefail

CONFIG=${1:?}
MODEL_TAG=${2:?}
QUALITY=${3:?}

INSTALLATION_PATH="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest"
cd "${INSTALLATION_PATH}"

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
export PYTHONUSERBASE="${HOME}/.local"
export PATH="${HOME}/.local/bin:${PATH}"
export PYTHONPATH="${HOME}/.local/lib/python${PYVER}/site-packages:${INSTALLATION_PATH}:${PYTHONPATH:-}"

echo "Host    : $(hostname)"
echo "Start   : $(date -u)"
echo "Config  : $CONFIG"
echo "Tag     : ${MODEL_TAG}_${QUALITY}_ignoreDAQConfig"
echo ""

python3 -m src.pipeline \
    --config "$CONFIG" \
    --model-tag "$MODEL_TAG" \
    --train-goodRunList \
    --train-goodRunList-quality "$QUALITY" \
    --logs-dir logs/applyToRuns_260429_IFhp \
    --combine-specific-run-outputs '*'

echo ""
echo "Finish: $(date -u)"
