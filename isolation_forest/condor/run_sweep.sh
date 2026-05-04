#!/bin/bash
# Run the full autoDQM pipeline for one parameter-sweep config.
# Called by submit_sweep.sub with a single argument: path to the config file
# (relative to the isolation_forest/ initialdir).
#
# The config file encodes all sweep parameters (z_threshold, if_contamination,
# trigger/DAQ config flags) and the model_tag.  No --model-tag override is
# passed here so the tag defined in the config file takes effect; the pipeline
# auto-appends _Tight / _ignoreTriggerConfig / _ignoreDAQConfig as appropriate.
#
# Submit from the isolation_forest/ directory:
#   condor_submit condor/submit_sweep.sub

set -euo pipefail

CONFIG=${1:?Usage: run_sweep.sh <config_path>}

SCRIPT_DIR="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest/condor"
INSTALLATION_PATH="${SCRIPT_DIR}/.."

cd "${INSTALLATION_PATH}"

echo "============================================================"
echo "  autoDQM sweep — config: $CONFIG"
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
    echo "Run 'bash setup.sh' on lxplus before submitting condor jobs." >&2
    exit 1
}
echo "  Dependencies: OK"
echo ""

python3 -m src.pipeline \
    --config "$CONFIG" \
    --train-goodRunList \
    --train-goodRunList-quality Tight \
    --train-goodRunList-fraction 0.1 \
    --apply-to-training-list \
    --skip-subrun-plots

echo ""
echo "============================================================"
echo "  Done: $CONFIG  $(date -u)"
echo "============================================================"
