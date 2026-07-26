#!/bin/bash
# run_repro_pengy_exact.sh — clean-room reproduction of pengy's 3.5% FP result
# (digi-only, z=8σ, if_contamination=0.001, n_consec=5, no trigger config,
#  train = 20% of good_run_list_TRAINING.txt, apply = his frozen seed42/frac40
#  manifest, evaluate = text-list ground truth). Two modes, one condor proc each
# (submit_repro_pengy_exact.sub):
#
#   pengy    Apply PENGY'S trained model (copied from his AFS checkout) to his
#            manifest. Validates the apply+evaluate half alone: the result must
#            match his summary exactly (473/13432 alerts = 3.5%). Any deviation
#            here is environment or missing EOS files — not method.
#
#   retrain  Train from scratch by his method (--fraction 0.2, test_seed 42,
#            params pinned in configs/repro_pengy_exact.yaml), then apply the
#            same manifest. The job log also diffs the retrained model against
#            his (seen_files list + reference statistics): if those match, this
#            mode must reproduce the pengy-mode numbers; if they differ, the
#            good-list globs resolve differently today than at his train time,
#            and the printed diff is the explanation for any FP gap.
#
# All output dirs are wiped first: step_apply APPENDS to an existing log and
# evaluate AUTO-SKIPS when eval_summary.txt exists, so stale outputs would
# corrupt or mask the result. Nothing here shares directories with the scans.
set -euo pipefail

MODE=${1:?Usage: run_repro_pengy_exact.sh <pengy|retrain>}
case "$MODE" in pengy|retrain) ;; *) echo "ERROR: unknown mode '$MODE'" >&2; exit 1 ;; esac

INSTALLATION_PATH="/afs/cern.ch/user/l/lbailloe/private/autoDQM/isolation_forest"
PENGY_MODEL_DIR="/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/models/juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig"
MANIFEST="${INSTALLATION_PATH}/condor/apply_good_training_sampled_paths_seed42_frac40.tsv"
GOOD_LIST="/afs/cern.ch/user/l/lbailloe/private/autoDQM/data/good_run_list_TRAINING.txt"
CONFIG="configs/repro_pengy_exact.yaml"
FEATURE_FLAGS=(--no-trigger --no-trigger-LVDS --no-trigger-config)

BASE_TAG="repro_pengy_exact_${MODE}"
RESOLVED_TAG="${BASE_TAG}_noTrigger_noLVDS_ignoreTriggerConfig"   # suffix added by pipeline from FEATURE_FLAGS
LOGS_DIR="/eos/user/l/lbailloe/autoDQM_scan/logs/repro_pengy_exact_${MODE}"
REPORTS_DIR="reports/repro_pengy_exact_${MODE}"
APPLY_LIST="${TMPDIR:-/tmp}/repro_pengy_exact_${MODE}_$$.txt"
trap 'rm -f "${APPLY_LIST}"' EXIT

cd "${INSTALLATION_PATH}"

# ── Environment (same pattern as run_scan.sh) ─────────────────────────────────
PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
export PYTHONUSERBASE="${HOME}/.local"
export PATH="${HOME}/.local/bin:${PATH}"
export PYTHONPATH="${HOME}/.local/lib/python${PYVER}/site-packages:${INSTALLATION_PATH}:${PYTHONPATH:-}"
python3 -c "import pandas, sklearn, numpy, scipy, watchdog" || {
    echo "ERROR: required packages not found (run setup.sh on lxplus first)." >&2; exit 1; }
python3 -c "import sklearn, numpy, pandas; print('  env:', 'sklearn', sklearn.__version__, '| numpy', numpy.__version__, '| pandas', pandas.__version__)"

[ -f "${MANIFEST}" ] || {
    echo "ERROR: manifest not found: ${MANIFEST}" >&2
    echo "       git checkout origin/branch_peng -- condor/apply_good_training_sampled_paths_seed42_frac40.tsv" >&2
    exit 1; }
N_MANIFEST=$(wc -l < "${MANIFEST}")
echo "  Mode       : ${MODE}"
echo "  Manifest   : ${N_MANIFEST} subrun paths (pengy's frozen seed42/frac40 sample)"
echo "  Model tag  : ${RESOLVED_TAG}"

# ── Fresh state: outputs AND the model dir for this mode ──────────────────────
rm -rf "${LOGS_DIR}" "${REPORTS_DIR}" "models/${RESOLVED_TAG}"
mkdir -p "${LOGS_DIR}"

# ── Step 1: obtain the model ──────────────────────────────────────────────────
if [ "$MODE" = "pengy" ]; then
    echo ""
    echo "  --- Model: copy pengy's trained model verbatim ---"
    [ -r "${PENGY_MODEL_DIR}/detector.pkl" ] || {
        echo "ERROR: cannot read ${PENGY_MODEL_DIR} (AFS permissions?)" >&2; exit 1; }
    mkdir -p "models/${RESOLVED_TAG}"
    cp -p "${PENGY_MODEL_DIR}"/* "models/${RESOLVED_TAG}/"
    md5sum "models/${RESOLVED_TAG}/detector.pkl" "models/${RESOLVED_TAG}/reference.npz"
else
    echo ""
    echo "  --- Model: retrain by pengy's method (20% of good list, seed 42) ---"
    python3 -m src.pipeline \
        --config "${CONFIG}" \
        --model-tag "${BASE_TAG}" \
        --fraction 0.2 \
        "${FEATURE_FLAGS[@]}" \
        --skip-apply --skip-evaluate --skip-report --skip-all-plots

    echo ""
    echo "  --- Model diff vs pengy's (explains any FP gap up front) ---"
    python3 - "models/${RESOLVED_TAG}" "${PENGY_MODEL_DIR}" <<'EOF' || echo "  WARNING: model diff failed (non-fatal)"
import sys, json, numpy as np
mine, his = sys.argv[1], sys.argv[2]
a = json.load(open(f"{mine}/seen_files.json")); b = json.load(open(f"{his}/seen_files.json"))
print(f"  seen_files: mine={len(a)}  pengy={len(b)}  identical={sorted(a)==sorted(b)}")
ra, rb = np.load(f"{mine}/reference.npz", allow_pickle=True), np.load(f"{his}/reference.npz", allow_pickle=True)
for k in ra.files:
    if k not in rb.files: print(f"  {k}: only in mine"); continue
    x, y = ra[k], rb[k]
    if x.shape != y.shape: print(f"  {k}: shape {x.shape} vs {y.shape}  DIFF"); continue
    try:   same = np.allclose(x.astype(float), y.astype(float), equal_nan=True)
    except (ValueError, TypeError): same = bool((x == y).all())
    print(f"  {k}: {x.shape}  {'SAME' if same else 'DIFF'}")
EOF
fi

# ── Step 2: apply to pengy's exact frozen paths (no re-sampling) ──────────────
echo ""
echo "  --- Apply: model on pengy's manifest paths ---"
cut -f2 "${MANIFEST}" > "${APPLY_LIST}"
python3 -m src.pipeline \
    --config "${CONFIG}" \
    --model-tag "${BASE_TAG}" --skip-train \
    --apply-list "${APPLY_LIST}" \
    --skip-evaluate --skip-report --skip-all-plots \
    "${FEATURE_FLAGS[@]}" \
    --logs-dir "${LOGS_DIR}"

LOG="${LOGS_DIR}/${RESOLVED_TAG}.csv"
[ -s "${LOG}" ] || LOG=$(find "${LOGS_DIR}" -type f -name '*.csv' -size +1k | head -1)
[ -n "${LOG:-}" ] && [ -s "${LOG}" ] || { echo "ERROR: no apply log under ${LOGS_DIR}" >&2; exit 1; }

# Coverage check: every manifest path must appear in the log, or the FP
# denominator is silently wrong (resolve_run_list drops missing files without error).
python3 - "${LOG}" "${N_MANIFEST}" <<'EOF'
import sys, pandas as pd
log, expected = sys.argv[1], int(sys.argv[2])
n = pd.read_csv(log, usecols=["filename"], low_memory=False)["filename"].nunique()
print(f"  coverage: {n} unique subruns in log vs {expected} manifest paths")
if n != expected:
    print(f"  WARNING: {expected - n} manifest subrun(s) missing from the log (gone from EOS?)")
EOF

# ── Step 3: evaluate — text-list ground truth, exactly like pengy ─────────────
echo ""
echo "  --- Evaluate (ground truth: training good list) ---"
python3 -m src.evaluate \
    --config "${CONFIG}" \
    --log-file "${LOG}" \
    --good-list-path "${GOOD_LIST}" \
    --out-dir "${REPORTS_DIR}"

echo ""
echo "  Reference (pengy): Total 13432 | ok 12882 (95.9%) | warn 77 (0.6%) | alert 473 (3.5%)"
grep -E "Total subruns|True Negative|Mild anomaly|Unverifiable|False Positive" "${REPORTS_DIR}/eval_summary.txt" || true
echo ""
echo "DONE (${MODE}) — full summary: ${REPORTS_DIR}/eval_summary.txt"
