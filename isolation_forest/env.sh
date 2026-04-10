#!/usr/bin/env bash
# env.sh — central path configuration for the autoDQM isolation_forest pipeline.
#
# Source this file in every script that touches the file system:
#   source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
#
# All paths are absolute so scripts work regardless of the working directory
# (i.e. safe to run from Condor worker nodes, cron jobs, or arbitrary shells).

# ── Installation root ──────────────────────────────────────────────────────────
export INSTALLATION_PATH="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest"

# ── Input data ────────────────────────────────────────────────────────────────
export DATA_PATH="/afs/cern.ch/user/t/tafoyava/autoDQM/data"
export GOOD_RUN_LIST="${DATA_PATH}/good_run_list_EOS.txt"
export ALL_RUN_LIST="${DATA_PATH}/all_run_list_EOS.txt"

# ── Output directories ────────────────────────────────────────────────────────
export MODELS_DIR="${INSTALLATION_PATH}/models"
export LOGS_DIR="${INSTALLATION_PATH}/logs"
export REPORTS_DIR="${INSTALLATION_PATH}/reports"
export PLOTS_DIR="${INSTALLATION_PATH}/plots"

# ── Source code ───────────────────────────────────────────────────────────────
export SRC_DIR="${INSTALLATION_PATH}/src"
