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
ENV_FILE="$SCRIPT_DIR/.env"

echo "============================================="
echo "  Migration: server_id = '$SERVER_ID'"
echo "============================================="
echo ""

# Set SERVER_ID in .env (append or update)
if [ -f "$ENV_FILE" ]; then
    if grep -q "^SERVER_ID=" "$ENV_FILE"; then
        sed -i "s/^SERVER_ID=.*/SERVER_ID=\"$SERVER_ID\"/" "$ENV_FILE"
        echo "[+] Updated SERVER_ID in .env"
    else
        echo "SERVER_ID=\"$SERVER_ID\"" >> "$ENV_FILE"
        echo "[+] Added SERVER_ID to .env"
    fi
else
    echo "SERVER_ID=\"$SERVER_ID\"" > "$ENV_FILE"
    echo "[+] Created .env with SERVER_ID"
fi

# Activate venv if present
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Run DB migration
echo ""
echo "[1/2] Running database migration..."
python3 "$SCRIPT_DIR/migrate_db_server_id.py" "$SERVER_ID" <<< "y"

echo ""

# Run Mega storage migration
echo "[2/2] Running Mega storage migration..."
python3 "$SCRIPT_DIR/migrate_mega_storage.py" "$SERVER_ID" <<< "y"

echo ""
echo "============================================="
echo "  Migration Complete!"
echo "  SERVER_ID='$SERVER_ID' saved to .env"
echo "============================================="
echo ""
echo "[*] Cleaning up migration files..."

# Self-destruct: delete migration scripts
rm -f "$SCRIPT_DIR/migrate_db_server_id.py"
rm -f "$SCRIPT_DIR/migrate_mega_storage.py"
rm -f "$SCRIPT_DIR/migrate.sh"

echo "[+] Migration files deleted."
echo ""
echo "Future backups/syncs will use server_id='$SERVER_ID'"
