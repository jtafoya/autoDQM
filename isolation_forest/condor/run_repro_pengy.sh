#!/bin/bash
# run_repro_pengy.sh — reproduce pengy's 40% apply result on a condor worker.
#
# Scores OUR existing digi-only model on PENGY'S frozen 40% sample of subrun
# paths (condor/apply_good_training_sampled_paths_seed42_frac40.tsv, fetched from
# branch_peng), then evaluates against the good run list. This isolates the one
# real difference from pengy's run — the apply SAMPLING: his manifest was built
# with a NUMERIC subrun sort (run_subrun_sort_key), whereas our pipeline's
# --apply-specific-run-fraction samples over a LEXICOGRAPHIC glob sort, so with
# the same seed 42 the two pick different 40% subruns. Feeding his exact paths
# via --apply-list removes that variable.
#
# Runs as ONE condor job (submit_repro_pengy.sub) because ~13.4k subruns in a
# single process exceeds the login node's CPU/time limit.
set -euo pipefail

INSTALLATION_PATH="/afs/cern.ch/user/l/lbailloe/private/autoDQM/isolation_forest"
MANIFEST="${INSTALLATION_PATH}/condor/apply_good_training_sampled_paths_seed42_frac40.tsv"
LOGS_DIR="/eos/user/l/lbailloe/autoDQM_scan/logs/repro_pengy"
REPORTS_DIR="reports/repro_pengy"
MODEL_TAG="condor_scan_trainFrac0p2"                                   # + feature flags below
RESOLVED_TAG="condor_scan_trainFrac0p2_noTrigger_noLVDS_ignoreTriggerConfig"
GOOD_LIST="/afs/cern.ch/user/l/lbailloe/private/autoDQM/data/good_run_list_TRAINING.txt"
APPLY_LIST="${TMPDIR:-/tmp}/pengy_apply_list_$$.txt"

cd "${INSTALLATION_PATH}"

# ── Make pip --user packages visible on the worker (see run_scan.sh) ──────────
PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
export PYTHONUSERBASE="${HOME}/.local"
export PATH="${HOME}/.local/bin:${PATH}"
export PYTHONPATH="${HOME}/.local/lib/python${PYVER}/site-packages:${INSTALLATION_PATH}:${PYTHONPATH:-}"
python3 -c "import pandas, sklearn, numpy, scipy, watchdog" || {
    echo "ERROR: required packages not found (run setup.sh on lxplus first)." >&2; exit 1; }

[ -f "${MANIFEST}" ] || {
    echo "ERROR: manifest not found: ${MANIFEST}" >&2
    echo "       git checkout origin/branch_peng -- condor/apply_good_training_sampled_paths_seed42_frac40.tsv" >&2
    exit 1; }

# Fresh output — step_apply AUTO-SKIPS if the log already exists, and appends.
rm -rf "${LOGS_DIR}" "${REPORTS_DIR}"
mkdir -p "${LOGS_DIR}"

# Pengy's exact sampled subrun paths = column 2 of his manifest.
cut -f2 "${MANIFEST}" > "${APPLY_LIST}"
echo "  Apply list : $(wc -l < "${APPLY_LIST}") paths (pengy's frozen 40% sample)"
echo "  Model      : ${RESOLVED_TAG}"
echo ""

echo "  --- Apply (our model on his paths, no re-sampling) ---"
python3 -m src.pipeline \
    --config configs/config.yaml \
    --model-tag "${MODEL_TAG}" --skip-train \
    --apply-list "${APPLY_LIST}" \
    --skip-evaluate --skip-report --skip-all-plots \
    --no-trigger --no-trigger-LVDS --no-trigger-config \
    --logs-dir "${LOGS_DIR}"

# Locate the log the apply wrote (logs_dir/<tag>.csv, or a <tag>/ subdir).
LOG=$(find "${LOGS_DIR}" -type f -name '*.csv' -size +1k | head -1)
[ -n "${LOG}" ] || { echo "ERROR: no apply log produced under ${LOGS_DIR}" >&2; exit 1; }
echo ""
echo "  Apply log  : ${LOG}"

echo ""
echo "  --- Evaluate against the good run list ---"
python3 -m src.evaluate \
    --config "models/${RESOLVED_TAG}/config.yaml" \
    --log-file "${LOG}" \
    --good-list-path "${GOOD_LIST}" \
    --out-dir "${REPORTS_DIR}"

rm -f "${APPLY_LIST}"
echo ""
echo "DONE — false-positive rate in ${REPORTS_DIR}/eval_summary.txt (expect ~3.58% if the sort was the cause)"
