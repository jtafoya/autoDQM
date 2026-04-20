#!/usr/bin/env bash
# setup.sh — install Python dependencies for the isolation_forest subproject
# Run once before using train.py or monitor.py:
#   source setup.sh
# or:
#   bash setup.sh

set -e

# Load central path configuration
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

PYTHON=${PYTHON:-python3}

echo "Python: $($PYTHON --version)"

# Install into the user's local site-packages (no root needed, works on CERN lxplus/AFS)
$PYTHON -m pip install --user \
    "pandas>=1.5" \
    "scikit-learn>=1.0" \
    "numpy>=1.23" \
    "scipy>=1.9" \
    "watchdog>=3.0" \
    "pyyaml>=6.0"

echo ""
echo "Dependencies installed. Verify with:"
echo "  $PYTHON -c \"import pandas, sklearn, numpy, scipy, watchdog, yaml; print('OK')\""
