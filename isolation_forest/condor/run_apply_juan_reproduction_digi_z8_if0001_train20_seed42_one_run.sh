#!/bin/bash
# Apply the frozen good-training sample for exactly one run.

set -euo pipefail

CONFIG=${1:?Usage: run_apply_juan_reproduction_digi_z8_if0001_train20_seed42_one_run.sh <config> <run>}
RUN=${2:?}

SCRIPT_DIR="/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/condor"
INSTALLATION_PATH="/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest"
SAMPLED_TSV="${SCRIPT_DIR}/apply_good_training_sampled_paths_seed42_frac40.tsv"

cd "${INSTALLATION_PATH}"

if [[ ! "${RUN}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: RUN must be an integer; got '${RUN}'." >&2
    exit 1
fi
if [ ! -f "${CONFIG}" ]; then
    echo "ERROR: config not found: ${CONFIG}" >&2
    exit 1
fi

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
export PYTHONUSERBASE="${HOME}/.local"
export PATH="${HOME}/.local/bin:${PATH}"
export PYTHONPATH="${HOME}/.local/lib/python${PYVER}/site-packages:${INSTALLATION_PATH}:${PYTHONPATH:-}"

python3 -c "import pandas, sklearn, numpy, scipy, watchdog, yaml" || {
    echo "ERROR: required Python dependencies are not importable." >&2
    exit 1
}

MODEL_TAG=$(python3 -c 'import sys; from src.config import load_config; print(load_config(sys.argv[1])["model_tag"])' "${CONFIG}")
EXPECTED_MODEL_TAG="juan_reproduction_digi_z8_if0001_train20_seed42"
if [ "${MODEL_TAG}" != "${EXPECTED_MODEL_TAG}" ]; then
    echo "ERROR: base model_tag '${MODEL_TAG}' does not match '${EXPECTED_MODEL_TAG}'." >&2
    exit 1
fi

ACTUAL_TAG="juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig"
MODEL_DIR="${INSTALLATION_PATH}/models/${ACTUAL_TAG}"
if [ ! -f "${MODEL_DIR}/reference.npz" ] || [ ! -f "${MODEL_DIR}/detector.pkl" ]; then
    echo "ERROR: trained model files are missing from ${MODEL_DIR}." >&2
    exit 1
fi
if [ ! -f "${SAMPLED_TSV}" ]; then
    echo "ERROR: sampled-path TSV not found: ${SAMPLED_TSV}" >&2
    exit 1
fi

LOCAL_TMP="${TMPDIR:-/tmp}/apply_good_training_${RUN}_$$"
TEMP_APPLY_LIST="${LOCAL_TMP}/apply_run_${RUN}.txt"
LOCAL_LOGS="${LOCAL_TMP}/logs"
PUBLISH_CSV_TMP=""
PUBLISH_PATHS_TMP=""

cleanup() {
    rm -rf "${LOCAL_TMP}"
    if [ -n "${PUBLISH_CSV_TMP}" ]; then rm -f "${PUBLISH_CSV_TMP}"; fi
    if [ -n "${PUBLISH_PATHS_TMP}" ]; then rm -f "${PUBLISH_PATHS_TMP}"; fi
}
trap cleanup EXIT
mkdir -p "${LOCAL_TMP}" "${LOCAL_LOGS}"

python3 -c '
import sys
from pathlib import Path
from src.run_list import extract_run_number, run_subrun_sort_key

tsv_path, run_text, output_path = sys.argv[1:]
run = int(run_text)
selected = []
for lineno, raw in enumerate(Path(tsv_path).read_text().splitlines(), start=1):
    fields = raw.split("\t")
    if len(fields) != 2:
        raise RuntimeError(f"Malformed TSV line {lineno}: {raw!r}")
    row_run = int(fields[0])
    if row_run == run:
        selected.append(fields[1])
if not selected:
    raise RuntimeError(f"No sampled paths found for run {run}")
if len(selected) != len(set(selected)):
    raise RuntimeError(f"Duplicate sampled paths found for run {run}")
for path in selected:
    path_obj = Path(path)
    if not path_obj.is_absolute():
        raise RuntimeError(f"Non-absolute path for run {run}: {path}")
    if not path_obj.is_file():
        raise FileNotFoundError(f"Sampled CSV is missing: {path}")
    if extract_run_number(path) != run:
        raise RuntimeError(f"Path belongs to another run: {path}")
selected = sorted(selected, key=run_subrun_sort_key)
Path(output_path).write_text("".join(f"{path}\n" for path in selected))
' "${SAMPLED_TSV}" "${RUN}" "${TEMP_APPLY_LIST}"

python3 -m src.pipeline \
    --config "${CONFIG}" \
    --model-tag "${MODEL_TAG}" \
    --skip-train \
    --apply-list "${TEMP_APPLY_LIST}" \
    --skip-evaluate \
    --skip-report \
    --skip-all-plots \
    --logs-dir "${LOCAL_LOGS}" \
    --no-trigger \
    --no-trigger-LVDS \
    --no-trigger-config

LOCAL_CSV="${LOCAL_LOGS}/${ACTUAL_TAG}.csv"
LOCAL_PATHS="${LOCAL_LOGS}/${ACTUAL_TAG}_paths.txt"
if [ ! -s "${LOCAL_CSV}" ] || [ ! -s "${LOCAL_PATHS}" ]; then
    echo "ERROR: pipeline outputs are missing or empty." >&2
    exit 1
fi

python3 -c '
import csv
import sys
from pathlib import Path
from src.run_list import extract_run_number

apply_list_path, cache_path, csv_path, run_text = sys.argv[1:]
run = int(run_text)
expected = Path(apply_list_path).read_text().splitlines()
cached = Path(cache_path).read_text().splitlines()
if len(cached) != len(expected) or set(cached) != set(expected):
    raise RuntimeError("Pipeline path cache does not match the temporary apply list")
if any(extract_run_number(path) != run for path in cached):
    raise RuntimeError("Pipeline path cache contains another run")
with open(csv_path, newline="") as handle:
    filenames = {row["filename"] for row in csv.DictReader(handle)}
if len(filenames) != len(expected):
    raise RuntimeError(
        f"CSV unique filename count {len(filenames)} != expected {len(expected)}"
    )
' "${TEMP_APPLY_LIST}" "${LOCAL_PATHS}" "${LOCAL_CSV}" "${RUN}"

AFS_RUN_LOG_DIR="${INSTALLATION_PATH}/logs/${ACTUAL_TAG}"
FINAL_CSV="${AFS_RUN_LOG_DIR}/${ACTUAL_TAG}_run${RUN}.csv"
FINAL_PATHS="${AFS_RUN_LOG_DIR}/${ACTUAL_TAG}_run${RUN}_paths.txt"
mkdir -p "${AFS_RUN_LOG_DIR}"
PUBLISH_CSV_TMP="${AFS_RUN_LOG_DIR}/.${ACTUAL_TAG}_run${RUN}.csv.tmp.$$"
PUBLISH_PATHS_TMP="${AFS_RUN_LOG_DIR}/.${ACTUAL_TAG}_run${RUN}_paths.txt.tmp.$$"
cp -p "${LOCAL_CSV}" "${PUBLISH_CSV_TMP}"
cp -p "${LOCAL_PATHS}" "${PUBLISH_PATHS_TMP}"
mv -f "${PUBLISH_PATHS_TMP}" "${FINAL_PATHS}"
PUBLISH_PATHS_TMP=""
mv -f "${PUBLISH_CSV_TMP}" "${FINAL_CSV}"
PUBLISH_CSV_TMP=""

echo "Published validated run ${RUN} outputs to ${AFS_RUN_LOG_DIR}"
