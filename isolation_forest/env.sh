#!/usr/bin/env bash
# env.sh — shell-level path configuration for the autoDQM isolation_forest pipeline.
#
# Source this file in shell scripts that need filesystem paths:
#   source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
#
# Pipeline configuration (run lists, output dirs, thresholds, …) lives in
# config.json — edit that file instead of this one for anything the Python
# code reads.  Only variables that are purely shell-level belong here.

# ── Installation root ─────────────────────────────────────────────────────────
export INSTALLATION_PATH="/afs/cern.ch/user/t/tafoyava/autoDQM/isolation_forest"
