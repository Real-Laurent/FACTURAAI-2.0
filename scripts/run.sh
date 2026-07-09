#!/usr/bin/env bash
# Wrapper called by the launchd agent on macOS. Runs main.py via the venv's python.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PY="$PROJECT_DIR/.venv/bin/python3"

if [ ! -f "$VENV_PY" ]; then
  echo "ERROR: venv not found at $VENV_PY — run 'python3 scripts/install.py' first" >&2
  exit 1
fi

exec "$VENV_PY" "$PROJECT_DIR/main.py"
