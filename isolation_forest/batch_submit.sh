#!/bin/bash
# batch_submit.sh — generate and submit the pengy-equivalent reproduction DAG.
#
# Goal: reproduce pengy's 3.5% FP method exactly, parallelized like his setup:
# train ONE IsolationForest on 20% of good_list (good_run_list_TRAINING.txt,
# seed 42, pinned params in configs/repro_pengy_exact.yaml), then apply that
# SAME model to his frozen seed42/frac40 manifest
# (condor/apply_good_training_sampled_paths_seed42_frac40.tsv, from
# branch_peng), sharded one Condor job per run.  The per-run outputs are merged
# back into a single log with the pipeline's --combine-specific-run-outputs
# step and evaluated against the training good list (text-list ground truth) —
# the same accounting behind his 473/13432 = 3.5%.
#
# What this script does:
#   1. Reads the run numbers from column 1 of the frozen manifest (the
#      authoritative source: exactly the runs pengy applied to).
#   2. Groups those run numbers into chunks of $RUNS_PER_JOB (a '+'-joined list
#      per chunk). Default is 1 — one Condor apply job per run, run in parallel,
#      so the apply step finishes in ~one run's wall time instead of days.
#   3. Writes three Condor parameter files under condor/:
#        scan_train_params.txt    BASE_TAG, TRAINFRAC          (1 line / fraction)
#        scan_apply_params.txt    BASE_TAG, RUN_GROUP          (fractions × groups)
#        scan_combine_params.txt  BASE_TAG                     (1 line / fraction)
#      with BASE_TAG = <prefix>_trainFrac<F>  (F's dot -> 'p').
#   4. Writes condor/repro_pengy.dag chaining the three phases: train → apply → combine.
#      (Own DAG filename: the old scan.dag rescue files must never make DAGMan
#      skip nodes of this different experiment.)
#   5. condor_submit_dag condor/repro_pengy.dag.
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
FRACTIONS=(0.2)                               # training fractions (pengy: 0.2, seed 42)
RUNS_PER_JOB=1                                # runs per apply job (processed sequentially
                                              # within the job — each run is a separate
                                              # python process either way, so grouping
                                              # saves scheduler load, not compute).
                                              # 1 = one job per run, pengy's sharding.
MODEL_TAG_PREFIX="repro_pengy"                # BASE_TAG = <prefix>_trainFrac<F>; deliberately
                                              # distinct from condor_scan_* so the fresh
                                              # retrain never wipes the earlier scan models.
MANIFEST_NAME="apply_good_training_sampled_paths_seed42_frac40.tsv"  # pengy's frozen 40%
                                              # per-run sample (under condor/, from branch_peng):
                                              # column 1 = run number, column 2 = subrun path.
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
CONDOR_DIR="${SCRIPT_DIR}/condor"
MANIFEST="${CONDOR_DIR}/${MANIFEST_NAME}"
TRAIN_PARAMS="${CONDOR_DIR}/scan_train_params.txt"
APPLY_PARAMS="${CONDOR_DIR}/scan_apply_params.txt"
COMBINE_PARAMS="${CONDOR_DIR}/scan_combine_params.txt"
DAG_FILE="${CONDOR_DIR}/repro_pengy.dag"

if [ ! -f "${MANIFEST}" ]; then
    echo "ERROR: frozen manifest not found: ${MANIFEST}" >&2
    echo "       git checkout origin/branch_peng -- condor/${MANIFEST_NAME}" >&2
    exit 1
fi

mkdir -p "${CONDOR_DIR}/logs"

# ── Step 1: extract run numbers from the frozen manifest ──────────────────────
# Column 1 of the TSV is the run number; unique + sorted = the exact run set
# pengy applied to.  run_scan.sh's apply phase re-reads the manifest to get
# each run's frozen subrun paths, so this list and the applied paths can never
# disagree.
RUNS=()
while IFS= read -r run; do
    case "$run" in
        ''|*[!0-9]*) continue ;;    # skip anything that is not a bare integer
    esac
    RUNS+=("$run")
done < <(cut -f1 "${MANIFEST}" | sort -un)

num_runs=${#RUNS[@]}
if [ "$num_runs" -eq 0 ]; then
    echo "ERROR: no run numbers found in manifest ${MANIFEST}" >&2
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
# autoDQM pengy-equivalent reproduction — generated by batch_submit.sh.
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
echo "  autoDQM pengy-equivalent reproduction (frozen manifest)"
echo "  Apply manifest : ${MANIFEST}  ($(wc -l < "${MANIFEST}") frozen paths)"
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
    echo "[--dry-run] To submit: cd '${SCRIPT_DIR}' && condor_submit_dag condor/repro_pengy.dag"
    exit 0
fi

# ── Step 5: submit the DAG (from isolation_forest/ so relative paths resolve) ─
cd "${SCRIPT_DIR}"

# Refuse to submit while a DAGMan for this DAG is still in the queue: a second
# instance would die on the lock file, and cleaning the bookkeeping below would
# blind the running one.
if condor_q -nobatch 2>/dev/null | grep -q "condor/repro_pengy.dag"; then
    echo "ERROR: a DAGMan for condor/repro_pengy.dag is already in the queue." >&2
    echo "       condor_rm it (or let it finish) before resubmitting."   >&2
    exit 1
fi

# Remove stale DAGMan bookkeeping from previous submissions.  In particular a
# leftover scan.dag.nodes.log (worst case truncated mid-write by a full AFS
# volume) blinds the new DAGMan to its own job events — it then waits forever
# on jobs that already finished.  Rescue files are deliberately KEPT: they are
# what lets a resubmission skip already-completed phases.
rm -f condor/repro_pengy.dag.condor.sub condor/repro_pengy.dag.dagman.out condor/repro_pengy.dag.dagman.log \
      condor/repro_pengy.dag.lib.out condor/repro_pengy.dag.lib.err condor/repro_pengy.dag.metrics \
      condor/repro_pengy.dag.nodes.log condor/repro_pengy.dag.lock

condor_submit_dag condor/repro_pengy.dag
