#!/bin/bash
# Run the full autoDQM pipeline for one feature variant — Medium quality, default config.
# Called by submit__Medium.sub with a single argument: the variant name.
#
# Variants:
#   trigger_lvds      — trigger rates on, LVDS counts on  (default)
#   trigger_nolvds    — trigger rates on, LVDS counts off
#   notrigger_lvds    — trigger rates off, LVDS counts on
#   notrigger_nolvds  — trigger rates off, LVDS counts off
#
# Working directory (set by initialdir in submit.sub):
#   /afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest/

set -euo pipefail

VARIANT=${1:?Usage: run_pipeline__Medium.sh <variant>}

SCRIPT_DIR="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest/condor"
INSTALLATION_PATH="${SCRIPT_DIR}/.."

cd "${INSTALLATION_PATH}"

echo "============================================================"
echo "  autoDQM pipeline — variant: $VARIANT"
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

FLAGS=()
case $VARIANT in
    trigger_lvds)
        ;;
    trigger_nolvds)
        FLAGS=(--no-trigger-LVDS)
        ;;
    notrigger_lvds)
        FLAGS=(--no-trigger)
        ;;
    notrigger_nolvds)
        FLAGS=(--no-trigger --no-trigger-LVDS)
        ;;
    *)
        echo "ERROR: unknown variant '$VARIANT'" >&2
        exit 1
        ;;
esac

echo "  Flags: ${FLAGS[*]:-'(none — full feature set)'}"
echo ""

python3 -m src.pipeline \
	--config config.yaml \
	--model-tag condor_full_260428 \
	--train-goodRunList \
	--train-goodRunList-quality Medium \
	--train-goodRunList-fraction 0.1 \
	--apply-to-training-list \
	"${FLAGS[@]}"

echo ""
echo "============================================================"
echo "  Done: $VARIANT  $(date -u)"
echo "============================================================"
