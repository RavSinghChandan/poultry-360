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


LAN_IP=$("$PY" - <<'PYEOF'
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("8.8.8.8", 80)); print(s.getsockname()[0])
except OSError:
    print("127.0.0.1")
finally:
    s.close()
PYEOF
)

echo
echo "=================================================="
echo "  POULTRY 360 IS RUNNING"
echo "=================================================="
echo "  On this Mac : http://localhost:8000/"
echo "  On a phone  : http://$LAN_IP:8000/"
echo
echo "  The phone must be on the SAME Wi-Fi as this Mac."
echo "  Not mobile data, and not a guest network."
echo
echo "  If the phone cannot load it, open this on the"
echo "  phone to see what it can reach:"
echo "    http://$LAN_IP:8000/api/whoami"
echo "=================================================="
echo
if ! "$PY" -c "import uvicorn" 2>/dev/null; then
  echo "ERROR: uvicorn not importable by $PY" >&2
  echo "Run: $PY -m pip install -r backend/requirements.txt" >&2
  exit 1
fi

cd backend
# Bind to every interface, not just loopback. On 127.0.0.1 the app is
# unreachable from a phone on the same Wi-Fi, which is the main way it is
# actually used - a farmer standing in a shed, not someone at this desk.
exec "../$PY" -m uvicorn api.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
