#!/bin/bash
# Generate evaluate + report + plots for one 260429 EXT model (skip train and apply).
# Used to fill in missing reports after the original training jobs were interrupted.
#
# Arguments:
#   $1 - CONFIG  : path to sweep config YAML (relative to initialdir)
#   $2 - VARIANT : trigger_lvds | trigger_nolvds | notrigger_lvds | notrigger_nolvds
#   $3 - QUALITY : Loose | Medium | Tight
#
# Submit from the isolation_forest/ directory:
#   condor_submit condor/submit_sweep_260429_EXT_reports.sub

set -euo pipefail

CONFIG=${1:?Usage: run_sweep_260429_EXT_reports.sh <config> <variant> <quality>}
VARIANT=${2:?}
QUALITY=${3:?}

SCRIPT_DIR="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest/condor"
INSTALLATION_PATH="${SCRIPT_DIR}/.."

cd "${INSTALLATION_PATH}"

echo "============================================================"
echo "  autoDQM sweep 260429 EXT — evaluate + report + plots"
echo "    config  : $CONFIG"
echo "    variant : $VARIANT"
echo "    quality : $QUALITY"
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

MODEL_TAG=$(python3 -c "
import yaml
with open('${CONFIG}') as f:
    d = yaml.safe_load(f)
print(d.get('model_tag', 'sweep') + '_260429_EXT')
")
echo "  Model tag (before pipeline suffixes): $MODEL_TAG"

FLAGS=()
case $VARIANT in
    trigger_lvds)     ;;
    trigger_nolvds)   FLAGS=(--no-trigger-LVDS) ;;
    notrigger_lvds)   FLAGS=(--no-trigger) ;;
    notrigger_nolvds) FLAGS=(--no-trigger --no-trigger-LVDS) ;;
    *) echo "ERROR: unknown variant '$VARIANT'" >&2; exit 1 ;;
esac

python3 -m src.pipeline \
    --config "$CONFIG" \
    --model-tag "$MODEL_TAG" \
    --train-goodRunList \
    --train-goodRunList-quality "$QUALITY" \
    --skip-train --skip-apply \
    "${FLAGS[@]}"

echo ""
echo "============================================================"
echo "  Done: $CONFIG  $VARIANT  $QUALITY  $(date -u)"
echo "============================================================"
