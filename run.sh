#!/bin/bash

# Get directory of this script to ensure we run from the right place
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Run using the virtual environment python
# This handles setting up the python path and dependencies automatically
# because we use the venv's python binary directly.

if [ -f "$DIR/venv/bin/python3" ]; then
    echo "[*] Running Backup Manager..."
    "$DIR/venv/bin/python3" "$DIR/backup_manager.py" "$@"
else
    echo "[!] Virtual environment not found in $DIR/venv"
    echo "    Please run deploy.sh or set up the venv manually."
    exit 1
fi
