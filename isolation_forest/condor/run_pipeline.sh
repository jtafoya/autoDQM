#!/bin/bash
# Run the full autoDQM pipeline for one feature variant.
# Called by submit.sub with a single argument: the variant name.
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

VARIANT=${1:?Usage: run_pipeline.sh <variant>}

SCRIPT_DIR="/afs/cern.ch/user/l/lbailloe/private/autoDQM/isolation_forest/condor"
INSTALLATION_PATH="${SCRIPT_DIR}/.."

cd "${INSTALLATION_PATH}"

echo "============================================================"
echo "  autoDQM pipeline — variant: $VARIANT"
echo "  Host : $(hostname)"
echo "  Start: $(date -u)"
echo "============================================================"

# Make pip --user packages (installed via setup.sh) visible on worker nodes.
# AFS is mounted on lxplus condor nodes, so ~/.local is available.
PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
export PYTHONUSERBASE="${HOME}/.local"
export PATH="${HOME}/.local/bin:${PATH}"
export PYTHONPATH="${HOME}/.local/lib/python${PYVER}/site-packages:${INSTALLATION_PATH}:${PYTHONPATH:-}"

echo "  Python : $(python3 --version)  ($(which python3))"
echo "  PYTHONPATH prefix: ${HOME}/.local/lib/python${PYVER}/site-packages"

# Verify dependencies are importable before doing any real work
python3 -c "import pandas, sklearn, numpy, scipy, watchdog" || {
    echo "ERROR: required packages not found." >&2
    echo "Run 'bash setup.sh' on lxplus before submitting condor jobs." >&2
    exit 1
}
echo "  Dependencies: OK"
echo ""

# Map variant name to CLI flags
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

#python3 -m src.pipeline \
#    --model-tag "condor" \
#    "${FLAGS[@]}"

# python3 -m src.pipeline \
# 	--config configs/config.yaml \
# 	--model-tag condor_full_260428 \
# 	--fraction 0.1 \
# 	"${FLAGS[@]}"

# python3 -m src.pipeline \
# 	--config configs/config.yaml \
# 	--model-tag condor_repo \
# 	--train-goodRunList \
# 	--train-goodRunList-quality Tight \
# 	--train-goodRunList-fraction 0.1 \
# 	--apply-to-training-list \
# 	"${FLAGS[@]}"

# Plain training mode (no --train-goodRunList): training files come from the
# good_list text file set in configs/config.yaml — data/good_run_list_TRAINING.txt.
# --fraction is plain mode's counterpart of --train-goodRunList-fraction.
# Note: without goodRunList mode no "_<quality>" suffix is appended, so outputs
# land under models/condor_extended* (feature-variant suffixes still apply).
python3 -m src.pipeline \
--config configs/config.yaml \
--model-tag condor_extended \
--fraction 0.1 \
--apply-list /afs/cern.ch/user/l/lbailloe/private/autoDQM/data/small_run.txt \
"${FLAGS[@]}"
	
echo ""
echo "============================================================"
echo "  Done: $VARIANT  $(date -u)"
echo "============================================================"
