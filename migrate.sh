#!/bin/bash
# Migration Script Runner
# Runs DB and Mega storage migrations, then SELF-DESTRUCTS on success.
#
# Usage: ./migrate.sh <SERVER_ID>
# Example: ./migrate.sh wp

set -e

if [ -z "$1" ]; then
    echo "Usage: ./migrate.sh <SERVER_ID>"
    echo "Example: ./migrate.sh wp"
    exit 1
fi

SERVER_ID="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================="
echo "  Migration: server_id = '$SERVER_ID'"
echo "============================================="
echo ""

# Activate venv if present
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Run DB migration
echo "[1/2] Running database migration..."
python3 "$SCRIPT_DIR/migrate_db_server_id.py" "$SERVER_ID" <<< "y"

echo ""

# Run Mega storage migration
echo "[2/2] Running Mega storage migration..."
python3 "$SCRIPT_DIR/migrate_mega_storage.py" "$SERVER_ID" <<< "y"

echo ""
echo "============================================="
echo "  Migration Complete!"
echo "============================================="
echo ""
echo "[*] Cleaning up migration files..."

# Self-destruct: delete migration scripts
rm -f "$SCRIPT_DIR/migrate_db_server_id.py"
rm -f "$SCRIPT_DIR/migrate_mega_storage.py"
rm -f "$SCRIPT_DIR/migrate.sh"

echo "[+] Migration files deleted."
echo ""
echo "You can now run: ./deploy.sh"
