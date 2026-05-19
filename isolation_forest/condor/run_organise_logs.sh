#!/bin/bash
# Run organise_run_outputs.py on a worker node.
# Safe to submit while a local run is in progress — all renames are atomic
# and already-moved files are silently skipped.

set -euo pipefail

INSTALLATION_PATH="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest"
cd "${INSTALLATION_PATH}"

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
export PYTHONUSERBASE="${HOME}/.local"
export PATH="${HOME}/.local/bin:${PATH}"
export PYTHONPATH="${HOME}/.local/lib/python${PYVER}/site-packages:${INSTALLATION_PATH}:${PYTHONPATH:-}"

echo "Host  : $(hostname)"
echo "Start : $(date -u)"
echo ""

python3 organise_run_outputs.py

echo ""
echo "Finish: $(date -u)"
