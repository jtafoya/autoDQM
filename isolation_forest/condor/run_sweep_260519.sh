#!/bin/bash
# Train one cell of the 2026-05-19 sweep.
#
# Arguments:
#   $1 - CONFIG : path to sweep config YAML (relative to initialdir)
#   $2 - VARIANT: notrigger_nolvds | trigger_nolvds | notrigger_lvds | trigger_lvds
#   $3 - TC     : withConfig | ignoreConfig (trigger board config integration)

set -euo pipefail

CONFIG=${1:?Usage: run_sweep_260519.sh <config> <variant> <tc>}
VARIANT=${2:?}
TC=${3:?}

SCRIPT_DIR="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest/condor"
INSTALLATION_PATH="${SCRIPT_DIR}/.."

cd "${INSTALLATION_PATH}"

echo "============================================================"
echo "  autoDQM sweep 260519 — train"
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
    echo "ERROR: required packages not found. Run 'bash setup.sh' on lxplus first." >&2
    exit 1
}
echo "  Dependencies: OK"
echo ""

MODEL_TAG=$(python3 -c "
import yaml
with open('${CONFIG}') as f:
    d = yaml.safe_load(f)
print(d.get('model_tag', 'sweep'))
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

TC_FLAGS=()
if [ "$TC" = "ignoreConfig" ]; then
    TC_FLAGS=(--no-trigger-config)
fi

echo "  Feature flags : ${FLAGS[*]:-'(none)'}"
echo "  TrigCfg flags : ${TC_FLAGS[*]:-'(none)'}"
echo ""

python3 -m src.pipeline \
    --config    "$CONFIG" \
    --model-tag "$MODEL_TAG" \
    --fraction  0.1 \
    --skip-apply --skip-evaluate --skip-report --skip-all-plots \
    "${FLAGS[@]}" "${TC_FLAGS[@]}"

echo ""
echo "============================================================"
echo "  Done: $CONFIG  $VARIANT  $TC  $(date -u)"
echo "============================================================"
