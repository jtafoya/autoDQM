#!/bin/bash
# HTCondor entrypoint: one run per job, with the frozen TASK 1 model.

set -euo pipefail

CONFIG=${1:?Usage: run_kb_scan_job.sh <campaign-config> <run>}
RUN=${2:?Usage: run_kb_scan_job.sh <campaign-config> <run>}
INSTALLATION_PATH="/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest"

cd "${INSTALLATION_PATH}"

if [[ ! "${RUN}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: RUN must be an integer; got '${RUN}'." >&2
    exit 2
fi
if [[ ! -f "${CONFIG}" ]]; then
    echo "ERROR: campaign config not found: ${CONFIG}" >&2
    exit 2
fi

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
export PYTHONUSERBASE="${HOME}/.local"
export PATH="${HOME}/.local/bin:${PATH}"
export PYTHONPATH="${HOME}/.local/lib/python${PYVER}/site-packages:${INSTALLATION_PATH}:${PYTHONPATH:-}"

python3 -c "import numpy, pandas, scipy, sklearn, yaml"
python3 condor/kb_scan/campaign.py run-job --config "${CONFIG}" --run "${RUN}"
