#!/bin/bash
# Run one batch of the 2026-04-29 IF hyperparameter sweep — apply-to-runs mode.
#
# Arguments:
#   $1 - CONFIG  : path to sweep config YAML (relative to initialdir)
#   $2 - VARIANT : trigger_lvds only for this sweep
#   $3 - QUALITY : Loose | Medium | Tight
#   $4 - PROCESS : HTCondor $(Process) — first run of batch = 1422 + PROCESS * 10
#
# Each job processes up to 10 consecutive runs (1422 + PROCESS*10 through
# 1422 + PROCESS*10 + 9, capped at 2276).
#
# Per-run logs are written to local scratch ($TMPDIR) during the job; a single
# bulk copy to AFS is done at job exit.
#
# Skips training; uses IFhp models already produced by submit_sweep_260429_IFhp.sub.
# Applies to 20% of each run's files and writes per-run logs to
# logs/applyToRuns_260429_IFhp/<tag>_run<N>.csv.
#
# Submit from the isolation_forest/ directory:
#   bash condor/submit_sweep_260429_IFhp_applyToRuns_all.sh

RUNS_PER_JOB=10
FIRST_RUN=1422
LAST_RUN=2276

set -euo pipefail

CONFIG=${1:?Usage: run_sweep_260429_IFhp_applyToRuns.sh <config> <variant> <quality> <process>}
VARIANT=${2:?}
QUALITY=${3:?}
PROCESS=${4:?}

BASE_RUN=$(( FIRST_RUN + PROCESS * RUNS_PER_JOB ))
END_RUN=$(( BASE_RUN + RUNS_PER_JOB - 1 ))
if (( END_RUN > LAST_RUN )); then END_RUN=$LAST_RUN; fi

SCRIPT_DIR="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest/condor"
INSTALLATION_PATH="${SCRIPT_DIR}/.."

cd "${INSTALLATION_PATH}"

echo "============================================================"
echo "  autoDQM sweep 260429 IFhp — apply to runs"
echo "    config  : $CONFIG"
echo "    variant : $VARIANT"
echo "    quality : $QUALITY"
echo "    process : $PROCESS  →  runs $BASE_RUN–$END_RUN"
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

MODEL_TAG=$(python3 -c "
import yaml
with open('${CONFIG}') as f:
    d = yaml.safe_load(f)
print(d.get('model_tag', 'sweep') + '_260429_IFhp')
")
echo "  Model tag (before pipeline suffixes): $MODEL_TAG"

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

# ── Local scratch (avoids continuous AFS writes) ──────────────────────────────
LOCAL_TMP="${TMPDIR:-/tmp}/applyToRuns_IFhp_${$}"
LOCAL_LOGS="${LOCAL_TMP}/logs"
mkdir -p "${LOCAL_LOGS}"

AFS_LOGS="${INSTALLATION_PATH}/logs/applyToRuns_260429_IFhp"
mkdir -p "${AFS_LOGS}"

# ── Apply loop ─────────────────────────────────────────────────────────────────
N_OK=0
N_FAIL=0

for (( i=0; i<RUNS_PER_JOB; i++ )); do
    RUN=$(( BASE_RUN + i ))
    if (( RUN > LAST_RUN )); then
        break
    fi

    echo "--- Run $RUN  ($((i+1))/$RUNS_PER_JOB) ---"

    if python3 -m src.pipeline \
            --config "$CONFIG" \
            --model-tag "$MODEL_TAG" \
            --train-goodRunList \
            --train-goodRunList-quality "$QUALITY" \
            --skip-train \
            --apply-specific-run "$RUN" \
            --apply-specific-run-fraction 0.2 \
            --logs-dir "${LOCAL_LOGS}" \
            "${FLAGS[@]}"; then
        N_OK=$(( N_OK + 1 ))
    else
        echo "WARNING: run $RUN failed (exit $?) — continuing" >&2
        N_FAIL=$(( N_FAIL + 1 ))
    fi
done

# ── Bulk copy scratch → AFS ────────────────────────────────────────────────────
echo ""
echo "Copying outputs from scratch to AFS ($AFS_LOGS) ..."
find "${LOCAL_LOGS}" -maxdepth 1 -type f -exec cp {} "${AFS_LOGS}/" \;
echo "  Copy complete."

rm -rf "${LOCAL_TMP}"

echo ""
echo "============================================================"
echo "  Done: $CONFIG  $VARIANT  $QUALITY"
echo "  Runs $BASE_RUN–$END_RUN  |  OK: $N_OK  Failed: $N_FAIL"
echo "  $(date -u)"
echo "============================================================"

if (( N_FAIL > 0 )); then
    exit 1
fi
