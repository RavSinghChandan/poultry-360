#!/usr/bin/env bash
# One process: FastAPI serves the API and the farmer UI on a single port.
set -euo pipefail
cd "$(dirname "$0")"

# Use the project venv, so the server always runs with the deps that were
# installed for it rather than whichever python happens to be first on PATH.
PY="${PYTHON:-.venv/bin/python}"
if [ ! -x "$PY" ]; then
  echo "==> Creating venv and installing dependencies"
  python3.12 -m venv .venv
  .venv/bin/pip install -q -r backend/requirements.txt
  PY=.venv/bin/python
fi

if ! "$PY" -c "import uvicorn" 2>/dev/null; then
  echo "ERROR: uvicorn not importable by $PY" >&2
  echo "Run: $PY -m pip install -r backend/requirements.txt" >&2
  exit 1
fi

cd backend
exec "../$PY" -m uvicorn api.main:app --host 127.0.0.1 --port "${PORT:-8000}"
