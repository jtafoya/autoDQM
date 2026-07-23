#!/bin/bash
# batch_submit.sh — generate and submit the training-fraction scan as a Condor DAG.
#
# Goal: for each training fraction, train ONE IsolationForest on good_list
# (config default: good_run_list_TRAINING.txt), then apply that SAME model to
# every run in the apply list.
# Training is done once per fraction (not once per batch), so batches share a
# model.  The apply work is sharded per run (via --apply-specific-run) so it
# runs in parallel and can be merged back into a single report per fraction with
# the pipeline's built-in --combine-specific-run-outputs step.
#
# What this script does:
#   1. Reads an apply run-list (default: data/all_run_list_EXTENDED.txt) and
#      extracts the run numbers of every real EOS line (comments/blanks/
#      commented-out runs are ignored).
#   2. Groups those run numbers into chunks of $RUNS_PER_JOB (a '+'-joined list
#      per chunk). Default is 1 — one Condor apply job per run, run in parallel,
#      so the apply step finishes in ~one run's wall time instead of days.
#   3. Writes three Condor parameter files under condor/:
#        scan_train_params.txt    BASE_TAG, TRAINFRAC          (1 line / fraction)
#        scan_apply_params.txt    BASE_TAG, RUN_GROUP          (fractions × groups)
#        scan_combine_params.txt  BASE_TAG                     (1 line / fraction)
#      with BASE_TAG = <prefix>_trainFrac<F>  (F's dot -> 'p').
#   4. Writes condor/scan.dag chaining the three phases: train → apply → combine.
#   5. condor_submit_dag condor/scan.dag.
#
# The DAG guarantees every model is trained before any apply job runs, and every
# apply job finishes before the combine/evaluate step for its fraction.
#
# Usage:
#   bash batch_submit.sh            # generate params + DAG, then submit
#   bash batch_submit.sh --dry-run  # generate params + DAG only; do not submit
#
# Run from anywhere — paths are resolved relative to this script's location.

set -euo pipefail

# ── Tunable parameters ────────────────────────────────────────────────────────
FRACTIONS=(0.2)                                 # --train-goodRunList-fraction values
RUNS_PER_JOB=5                                # runs per apply job (processed sequentially
                                              # within the job — each run is a separate
                                              # python process either way, so grouping
                                              # saves scheduler load, not compute).
                                              # Lower it for more parallelism at the cost
                                              # of more Condor jobs; 1 = one job per run.
EOS_PREFIX="/eos/experiment/milliqan/run3_MilliMon/slab/"
MODEL_TAG_PREFIX="condor_scan"                # BASE_TAG = <prefix>_trainFrac<F>
RUN_LIST_NAME="all_run_list_EXTENDED.txt"     # apply list (under data/) to draw run numbers from
# ──────────────────────────────────────────────────────────────────────────────

DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=true
elif [ -n "${1:-}" ]; then
    echo "ERROR: unknown argument '$1' (only --dry-run is accepted)" >&2
    exit 1
fi

# Resolve locations relative to this script so it works from any cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # isolation_forest/
REPO_ROOT="$(dirname "${SCRIPT_DIR}")"                       # autoDQM/
RUN_LIST="${REPO_ROOT}/data/${RUN_LIST_NAME}"
CONDOR_DIR="${SCRIPT_DIR}/condor"
TRAIN_PARAMS="${CONDOR_DIR}/scan_train_params.txt"
APPLY_PARAMS="${CONDOR_DIR}/scan_apply_params.txt"
COMBINE_PARAMS="${CONDOR_DIR}/scan_combine_params.txt"
DAG_FILE="${CONDOR_DIR}/scan.dag"

if [ ! -f "${RUN_LIST}" ]; then
    echo "ERROR: apply run-list not found: ${RUN_LIST}" >&2
    exit 1
fi

mkdir -p "${CONDOR_DIR}/logs"

# ── Step 1: extract run numbers from the apply list ───────────────────────────
# Each real line looks like  <prefix>/1600/Digitizer_run1601_subrun*.csv
# — pull the integer after "Digitizer_run".
RUNS=()
while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
        "${EOS_PREFIX}"*) ;;      # a real EOS glob line
        *) continue ;;            # comment, blank, or commented-out run
    esac
    run="${line##*Digitizer_run}"   # -> "1601_subrun*.csv"
    run="${run%%_*}"                # -> "1601"
    case "$run" in
        ''|*[!0-9]*) continue ;;    # skip anything that is not a bare integer
    esac
    RUNS+=("$run")
done < "${RUN_LIST}"

num_runs=${#RUNS[@]}
if [ "$num_runs" -eq 0 ]; then
    echo "ERROR: no run numbers found in ${RUN_LIST} (prefix '${EOS_PREFIX}')" >&2
    exit 1
fi

# ── Step 2: group run numbers into '+'-joined chunks of $RUNS_PER_JOB ─────────
RUN_GROUPS=()
chunk=""
count=0
for run in "${RUNS[@]}"; do
    if [ -z "$chunk" ]; then chunk="$run"; else chunk="${chunk}+${run}"; fi
    count=$((count + 1))
    if [ "$count" -eq "$RUNS_PER_JOB" ]; then
        RUN_GROUPS+=("$chunk")
        chunk=""
        count=0
    fi
done
# Flush the final partial chunk (guard with an if so set -e is not tripped when
# the run count is an exact multiple of $RUNS_PER_JOB and $chunk is empty).
if [ -n "$chunk" ]; then
    RUN_GROUPS+=("$chunk")
fi
num_groups=${#RUN_GROUPS[@]}

# ── Step 3: write the three parameter files ───────────────────────────────────
: > "${TRAIN_PARAMS}"
: > "${APPLY_PARAMS}"
: > "${COMBINE_PARAMS}"

for frac in "${FRACTIONS[@]}"; do
    frac_tag="${frac//./p}"
    base_tag="${MODEL_TAG_PREFIX}_trainFrac${frac_tag}"
    printf '%s, %s\n' "$base_tag" "$frac" >> "${TRAIN_PARAMS}"
    printf '%s\n'     "$base_tag"          >> "${COMBINE_PARAMS}"
    for g in "${RUN_GROUPS[@]}"; do
        printf '%s, %s\n' "$base_tag" "$g" >> "${APPLY_PARAMS}"
    done
done

# ── Step 4: write the DAG (train → apply → combine) ───────────────────────────
cat > "${DAG_FILE}" <<'EOF'
# autoDQM training-fraction scan — generated by batch_submit.sh.
# Three phases run strictly in order; every job of a node completes before the
# next node starts.
JOB   train    condor/submit_scan_train.sub
JOB   apply    condor/submit_scan_apply.sub
JOB   combine  condor/submit_scan_combine.sub

PARENT train  CHILD apply
PARENT apply  CHILD combine
EOF

n_train=${#FRACTIONS[@]}
n_apply=$(( num_groups * ${#FRACTIONS[@]} ))
n_combine=${#FRACTIONS[@]}

echo "============================================================"
echo "  autoDQM training-fraction scan"
echo "  Apply run-list : ${RUN_LIST}"
echo "  Run numbers    : ${num_runs}"
echo "  Runs per job   : ${RUNS_PER_JOB}  ->  ${num_groups} apply groups"
echo "  Fractions      : ${FRACTIONS[*]}"
echo "  Model tags     : ${MODEL_TAG_PREFIX}_trainFrac<F>"
echo "  Jobs           : ${n_train} train  +  ${n_apply} apply  +  ${n_combine} combine"
echo "  Params         : ${TRAIN_PARAMS}"
echo "                   ${APPLY_PARAMS}"
echo "                   ${COMBINE_PARAMS}"
echo "  DAG            : ${DAG_FILE}"
echo "============================================================"

if [ "$DRY_RUN" = true ]; then
    echo "[--dry-run] Files generated. Not submitting."
    echo "[--dry-run] To submit: cd '${SCRIPT_DIR}' && condor_submit_dag condor/scan.dag"
    exit 0
fi

# ── Step 5: submit the DAG (from isolation_forest/ so relative paths resolve) ─
cd "${SCRIPT_DIR}"

# Refuse to submit while a DAGMan for this DAG is still in the queue: a second
# instance would die on the lock file, and cleaning the bookkeeping below would
# blind the running one.
if condor_q -nobatch 2>/dev/null | grep -q "condor/scan.dag"; then
    echo "ERROR: a DAGMan for condor/scan.dag is already in the queue." >&2
    echo "       condor_rm it (or let it finish) before resubmitting."   >&2
    exit 1
fi

# Remove stale DAGMan bookkeeping from previous submissions.  In particular a
# leftover scan.dag.nodes.log (worst case truncated mid-write by a full AFS
# volume) blinds the new DAGMan to its own job events — it then waits forever
# on jobs that already finished.  Rescue files are deliberately KEPT: they are
# what lets a resubmission skip already-completed phases.
rm -f condor/scan.dag.condor.sub condor/scan.dag.dagman.out condor/scan.dag.dagman.log \
      condor/scan.dag.lib.out condor/scan.dag.lib.err condor/scan.dag.metrics \
      condor/scan.dag.nodes.log condor/scan.dag.lock

condor_submit_dag condor/scan.dag
