#!/bin/bash
# WordPress Backup Admin CLI
# Direct database access - bypasses FastAPI

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${SCRIPT_DIR}/venv"
PYTHON="${VENV_PATH}/bin/python"

# Check if venv exists
if [ ! -f "$PYTHON" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH"
    echo "Please run deploy.sh first to set up the environment."
    exit 1
fi

# Run the Python admin CLI
cd "$SCRIPT_DIR"
exec "$PYTHON" -m scripts.admin_cli "$@"
