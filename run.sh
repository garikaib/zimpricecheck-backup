#!/bin/bash

# Get directory of this script to ensure we run from the right place
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Run using the virtual environment python
# This handles setting up the python path and dependencies automatically
# because we use the venv's python binary directly.

# Parse arguments
FOREGROUND=false
ARGS=""

for arg in "$@"; do
    case $arg in
        -f|--foreground)
        FOREGROUND=true
        shift
        ;;
        *)
        ARGS="$ARGS $arg"
        ;;
    esac
done

if [ -f "$DIR/venv/bin/python3" ]; then
    # Helper to check status
    check_status() {
        "$DIR/venv/bin/python3" "$DIR/backup_manager.py" --check
    }
    
    if [ "$FOREGROUND" = true ]; then
        echo "[*] Running WordPress Backup Manager (Foreground)..."
        "$DIR/venv/bin/python3" "$DIR/backup_manager.py" $ARGS
    else
        # Check if running
        STATUS_OUT=$(check_status)
        if echo "$STATUS_OUT" | grep -q "Backup is running"; then
             echo "[!] $STATUS_OUT"
             echo "    Please wait for it to finish."
             exit 0
        fi

        echo "[*] Starting WordPress Backup Manager in background..."
        nohup "$DIR/venv/bin/python3" "$DIR/backup_manager.py" $ARGS > /dev/null 2>&1 &
        echo "[+] Process started. PID: $!"
        echo "    You will receive an email upon completion."
        echo "    Run this script again to see status."
    fi
else
    echo "[!] Virtual environment not found in $DIR/venv"
    echo "    Please run deploy.sh or set up the venv manually."
    exit 1
fi
