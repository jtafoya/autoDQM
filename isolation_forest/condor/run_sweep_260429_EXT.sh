#!/bin/bash
# Run one cell of the 2026-04-29 parameter sweep extension (EXT).
#
# Extends the original sweep into lower contamination (0.001, 0.002) and
# higher z-threshold (8σ, 9σ) territory, following the finding that
# contamination=0.005 and z-threshold=7σ gave the best results.
#
# Arguments:
#   $1 - CONFIG  : path to sweep config YAML (relative to initialdir)
#   $2 - VARIANT : trigger_lvds | trigger_nolvds | notrigger_lvds | notrigger_nolvds
#   $3 - QUALITY : Loose | Medium | Tight
#
# The model tag is read from the config's model_tag field; _260429_EXT is
# appended before the pipeline applies its own suffixes (_<Quality>, _noTrigger, etc.).
#
# Submit from the isolation_forest/ directory:
#   condor_submit condor/submit_sweep_260429_EXT.sub

set -euo pipefail

CONFIG=${1:?Usage: run_sweep_260429_EXT.sh <config> <variant> <quality>}
VARIANT=${2:?Usage: run_sweep_260429_EXT.sh <config> <variant> <quality>}
QUALITY=${3:?Usage: run_sweep_260429_EXT.sh <config> <variant> <quality>}

SCRIPT_DIR="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest/condor"
INSTALLATION_PATH="${SCRIPT_DIR}/.."

cd "${INSTALLATION_PATH}"

echo "============================================================"
echo "  autoDQM sweep 260429 EXT"
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

echo "  Python : $(python3 --version)  ($(which python3))"
echo "  PYTHONPATH prefix: ${HOME}/.local/lib/python${PYVER}/site-packages"

python3 -c "import pandas, sklearn, numpy, scipy, watchdog" || {
    echo "ERROR: required packages not found." >&2
    echo "Run 'bash setup.sh' on lxplus before submitting condor jobs." >&2
    exit 1
}
echo "  Dependencies: OK"
echo ""

# Read model_tag from config and append EXT date suffix.
# The pipeline will then append _<Quality>, _noTrigger, _noLVDS, etc. after this.
MODEL_TAG=$(python3 -c "
import yaml
with open('${CONFIG}') as f:
    d = yaml.safe_load(f)
print(d.get('model_tag', 'sweep') + '_260429_EXT')
")
echo "  Model tag (before pipeline suffixes): $MODEL_TAG"

# Map variant name to feature-flag arguments
FLAGS=()
case $VARIANT in
    trigger_lvds)     ;;
    trigger_nolvds)   FLAGS=(--no-trigger-LVDS) ;;
    notrigger_lvds)   FLAGS=(--no-trigger) ;;
    notrigger_nolvds) FLAGS=(--no-trigger --no-trigger-LVDS) ;;
    *)
        echo "ERROR: unknown variant '$VARIANT'" >&2
        exit 1
        ;;
esac
echo "  Feature flags: ${FLAGS[*]:-'(none — full feature set)'}"
echo ""

python3 -m src.pipeline \
    --config "$CONFIG" \
    --model-tag "$MODEL_TAG" \
    --train-goodRunList \
    --train-goodRunList-quality "$QUALITY" \
    --train-goodRunList-fraction 0.1 \
    --apply-to-training-list \
    "${FLAGS[@]}"

echo ""
echo "============================================================"
echo "  Done: $CONFIG  $VARIANT  $QUALITY  $(date -u)"
echo "============================================================"
