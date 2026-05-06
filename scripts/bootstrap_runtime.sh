#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-$ROOT_DIR/.pycache}"

if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3.13 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.13)"
  elif command -v python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.12)"
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "Python 3.10+ is required. Set PYTHON_BIN to a newer interpreter, e.g. /opt/homebrew/bin/python3.12" >&2
  exit 1
fi

"$PYTHON_BIN" -m venv .venv
mkdir -p "$PYTHONPYCACHEPREFIX"
.venv/bin/pip install --no-compile -r requirements.txt

mkdir -p data/db data/downloads data/transcripts data/models data/shownotes

echo "Runtime ready. Activate with: source .venv/bin/activate"
