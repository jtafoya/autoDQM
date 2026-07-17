#!/bin/bash
# Train the Juan-reproduction Digitizer-only model.
#
# Arguments:
#   $1 - CONFIG : path to training config YAML (relative to initialdir)
#   $2 - VARIANT: notrigger_nolvds
#   $3 - TC     : ignoreConfig (disable trigger board config integration)

set -euo pipefail

CONFIG=${1:?Usage: run_train_juan_reproduction_digi_z8_if0001_train20_seed42.sh <config> <variant> <tc>}
VARIANT=${2:?}
TC=${3:?}

SCRIPT_DIR="/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/condor"
INSTALLATION_PATH="${SCRIPT_DIR}/.."

cd "${INSTALLATION_PATH}"

echo "============================================================"
echo "  autoDQM Juan reproduction — train"
echo "    config  : $CONFIG"
echo "    variant : $VARIANT"
echo "    trigCfg : $TC"
echo "  Host : $(hostname)"
echo "  Start: $(date -u)"
echo "============================================================"

# Verify EOS is reachable before doing any real work; exit 1 fast so Condor
# retries on a different node rather than hanging for the full walltime.
EOS_PROBE="/eos/experiment/milliqan/run3_MilliMon/slab"
if ! timeout 15 ls "${EOS_PROBE}" > /dev/null 2>&1; then
    echo "ERROR: EOS not reachable at ${EOS_PROBE} — exiting for retry on another node." >&2
    exit 1
fi
echo "  EOS: OK"

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
    --fraction  0.2 \
    --skip-apply --skip-evaluate --skip-report --skip-all-plots \
    "${FLAGS[@]}" "${TC_FLAGS[@]}"

echo ""
echo "============================================================"
echo "  Done: $CONFIG  $VARIANT  $TC  $(date -u)"
echo "============================================================"
