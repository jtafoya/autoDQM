#!/bin/bash
# Apply one batch of the 260519 sweep — per-run apply mode.
#
# Arguments:
#   $1 - CONFIG  : path to sweep config YAML (relative to initialdir)
#   $2 - VARIANT : feature variant
#   $3 - TC      : withConfig | ignoreConfig
#   $4 - PROCESS : HTCondor $(Process) — first run = 1601 + PROCESS * 10
#
# Each job applies to up to 10 consecutive runs (1601–2238),
# scoring 20% of each run's files.  Per-run logs are written to local scratch
# and bulk-copied to AFS on exit.

RUNS_PER_JOB=10
FIRST_RUN=1601
LAST_RUN=2238

set -euo pipefail

CONFIG=${1:?Usage: run_sweep_260519_applyToRuns.sh <config> <variant> <tc> <process>}
VARIANT=${2:?}
TC=${3:?}
PROCESS=${4:?}

BASE_RUN=$(( FIRST_RUN + PROCESS * RUNS_PER_JOB ))
END_RUN=$(( BASE_RUN + RUNS_PER_JOB - 1 ))
if (( END_RUN > LAST_RUN )); then END_RUN=$LAST_RUN; fi

SCRIPT_DIR="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest/condor"
INSTALLATION_PATH="${SCRIPT_DIR}/.."

cd "${INSTALLATION_PATH}"

echo "============================================================"
echo "  autoDQM sweep 260519 — apply to runs"
echo "    config  : $CONFIG"
echo "    variant : $VARIANT"
echo "    trigCfg : $TC"
echo "    process : $PROCESS  →  runs $BASE_RUN–$END_RUN"
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

LOCAL_TMP="${TMPDIR:-/tmp}/applyToRuns_260519_$$"
LOCAL_LOGS="${LOCAL_TMP}/logs"
mkdir -p "${LOCAL_LOGS}"

AFS_LOGS="${INSTALLATION_PATH}/logs/applyToRuns_260519"
mkdir -p "${AFS_LOGS}"

N_OK=0
N_FAIL=0

for (( i=0; i<RUNS_PER_JOB; i++ )); do
    RUN=$(( BASE_RUN + i ))
    if (( RUN > LAST_RUN )); then break; fi

    echo "--- Run $RUN  ($(( i+1 ))/${RUNS_PER_JOB}) ---"

    if python3 -m src.pipeline \
            --config    "${CONFIG}" \
            --model-tag "$MODEL_TAG" \
            --skip-train \
            --train-goodRunList \
            --apply-specific-run "$RUN" \
            --apply-specific-run-fraction 0.4 \
            --logs-dir "${LOCAL_LOGS}" \
            "${FLAGS[@]}" "${TC_FLAGS[@]}"; then
        N_OK=$(( N_OK + 1 ))
    else
        echo "WARNING: run $RUN failed (exit $?) — continuing" >&2
        N_FAIL=$(( N_FAIL + 1 ))
    fi
done

echo ""
echo "Copying outputs from scratch to AFS (${AFS_LOGS}) ..."
cp -rp "${LOCAL_LOGS}/." "${AFS_LOGS}/"
echo "  Copy complete."
rm -rf "${LOCAL_TMP}"

echo ""
echo "============================================================"
echo "  Done: $CONFIG  $VARIANT  $TC"
echo "  Runs $BASE_RUN–$END_RUN  |  OK: $N_OK  Failed: $N_FAIL"
echo "  $(date -u)"
echo "============================================================"

if (( N_FAIL > 0 )); then exit 1; fi
