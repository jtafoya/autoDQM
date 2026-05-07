#!/bin/bash
# Run one cell of the 2026-04-29 parameter sweep — apply-to-runs mode.
#
# Arguments:
#   $1 - CONFIG  : path to sweep config YAML (relative to initialdir)
#   $2 - VARIANT : trigger_lvds | trigger_nolvds | notrigger_lvds | notrigger_nolvds
#   $3 - QUALITY : Loose | Medium | Tight
#   $4 - PROCESS : HTCondor $(Process) — run number = 1422 + (PROCESS % 855)
#
# Skips training; uses models already produced by submit_sweep_260429.sub.
# Applies to 20 % of each run's files and writes per-run logs to
# logs/applyToRuns_260429/<tag>_run<N>.csv, keeping them separate from the
# training-list logs in logs/.
#
# Submit from the isolation_forest/ directory:
#   condor_submit condor/submit_sweep_260429_applyToRuns.sub

set -euo pipefail

CONFIG=${1:?Usage: run_sweep_260429_applyToRuns.sh <config> <variant> <quality> <process>}
VARIANT=${2:?}
QUALITY=${3:?}
PROCESS=${4:?}

# Each cluster is a single model's 855-job array; Process runs 0–854 directly.
RUN=$((1422 + PROCESS))

SCRIPT_DIR="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest/condor"
INSTALLATION_PATH="${SCRIPT_DIR}/.."

cd "${INSTALLATION_PATH}"

echo "============================================================"
echo "  autoDQM sweep 260429 — apply to runs"
echo "    config  : $CONFIG"
echo "    variant : $VARIANT"
echo "    quality : $QUALITY"
echo "    process : $PROCESS  →  run $RUN"
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

# Read model_tag from config and append date suffix — must match the tag used
# during training (run_sweep_260429.sh).  The pipeline appends _<Quality>,
# _noTrigger, _noLVDS, _ignoreTriggerConfig, _ignoreDAQConfig after this.
MODEL_TAG=$(python3 -c "
import yaml
with open('${CONFIG}') as f:
    d = yaml.safe_load(f)
print(d.get('model_tag', 'sweep') + '_260429')
")
echo "  Model tag (before pipeline suffixes): $MODEL_TAG"

# Map variant name to feature-flag arguments
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
echo "  Applying to run: $RUN  (fraction 0.2)"
echo ""

python3 -m src.pipeline \
    --config "$CONFIG" \
    --model-tag "$MODEL_TAG" \
    --train-goodRunList \
    --train-goodRunList-quality "$QUALITY" \
    --skip-train \
    --apply-specific-run "$RUN" \
    --apply-specific-run-fraction 0.2 \
    --logs-dir logs/applyToRuns_260429 \
    "${FLAGS[@]}"

echo ""
echo "============================================================"
echo "  Done: $CONFIG  $VARIANT  $QUALITY  run $RUN  $(date -u)"
echo "============================================================"
