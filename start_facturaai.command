#!/usr/bin/env bash
# One-click start (macOS Finder double-click): launches main.py (folder
# watcher + Gmail poller + dashboard, all together), then opens the
# dashboard in your browser once it's actually up.
#
# First time only: this file needs the executable bit set —
#   chmod +x start_facturaai.command
# (git doesn't preserve that bit across a Windows dev machine, so it has
# to be set once on the Mac this actually runs on.)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PY="$SCRIPT_DIR/.venv/bin/python3"

if [ ! -f "$VENV_PY" ]; then
  echo "ERROR: venv not found at $VENV_PY"
  echo "Run this first:  python3 scripts/install.py"
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

echo "Starting FacturaAI..."
"$VENV_PY" main.py &

"$VENV_PY" scripts/open_dashboard.py
if [ $? -ne 0 ]; then
  read -n 1 -s -r -p "Press any key to close..."
fi
