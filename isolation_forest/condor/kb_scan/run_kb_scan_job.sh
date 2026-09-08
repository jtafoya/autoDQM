#!/bin/bash
# HTCondor entrypoint for one provenance-checked per-run scan.

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

run_environment_check() {
    if [[ -n "${AUTODQM_ENV_CHECK_COMMAND:-}" ]]; then
        "${AUTODQM_ENV_CHECK_COMMAND}"
    else
        python3 -c "import numpy, pandas, scipy, sklearn, yaml"
    fi
}

MAX_ENV_CHECK_ATTEMPTS=3
ENV_CHECK_SLEEP_SECONDS=${AUTODQM_ENV_CHECK_SLEEP_SECONDS:-5}
environment_ready=false
for attempt in $(seq 1 "${MAX_ENV_CHECK_ATTEMPTS}"); do
    if run_environment_check; then
        echo "[ENV CHECK] Dependency import succeeded on attempt ${attempt}/${MAX_ENV_CHECK_ATTEMPTS}."
        environment_ready=true
        break
    else
        rc=$?
        echo "[ENV CHECK] Attempt ${attempt}/${MAX_ENV_CHECK_ATTEMPTS} failed with status ${rc}." >&2
        if [[ "${attempt}" -lt "${MAX_ENV_CHECK_ATTEMPTS}" ]]; then
            echo "[ENV CHECK] Retrying after ${ENV_CHECK_SLEEP_SECONDS}s." >&2
            sleep "${ENV_CHECK_SLEEP_SECONDS}"
        fi
    fi
done
if [[ "${environment_ready}" != true ]]; then
    echo "[ENV CHECK] Dependency import failed after ${MAX_ENV_CHECK_ATTEMPTS} attempts." >&2
    exit 1
fi

# Used only by the bounded environment-check regression test.
if [[ "${AUTODQM_ENV_CHECK_ONLY:-0}" == "1" ]]; then
    exit 0
fi

python3 condor/kb_scan/campaign.py run-job --config "${CONFIG}" --run "${RUN}"
