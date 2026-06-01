#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/venv/bin/python3"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: venv not found at $PROJECT_ROOT/venv"
    echo "Please create a virtual environment first."
    exit 1
fi

"$VENV_PYTHON" -c "import fastapi" 2>/dev/null || {
    echo "Installing GUI dependencies..."
    "$VENV_PYTHON" -m pip install fastapi uvicorn
}

echo "Starting VeraGrid GUI at http://localhost:8550"
exec "$VENV_PYTHON" "$SCRIPT_DIR/dashboard.py"
