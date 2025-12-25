#!/bin/bash
set -e

INSTALL_DIR="$1"

echo "[*] Extracting bundle..."
cd "$INSTALL_DIR"
zstd -d -c bundle.tar.zst | tar -xf -

echo "[*] Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

echo "[*] Installing Python dependencies..."
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q

echo "[*] Setting permissions..."
chmod +x run.sh configure.sh lib/*.py 2>/dev/null || true

echo "[*] Running remote configuration wizard..."
# This will auto-detect WordPress sites and generate systemd files
./venv/bin/python3 lib/configure.py

echo "[*] Installing MEGAcmd if not present..."
if ! command -v mega-login &> /dev/null; then
    wget -q https://mega.nz/linux/repo/xUbuntu_22.04/amd64/megacmd-xUbuntu_22.04_amd64.deb -O /tmp/megacmd.deb
    sudo apt-get update -qq
    sudo apt-get install -y /tmp/megacmd.deb
    rm -f /tmp/megacmd.deb
fi

echo "[*] Installing systemd services..."
if [ -d "systemd" ]; then
    sudo cp systemd/*.service /etc/systemd/system/ 2>/dev/null || true
    sudo cp systemd/*.timer /etc/systemd/system/ 2>/dev/null || true
    sudo systemctl daemon-reload
    sudo systemctl enable wordpress-backup.timer wordpress-report.timer 2>/dev/null || true
    sudo systemctl start wordpress-backup.timer wordpress-report.timer 2>/dev/null || true
fi

echo "[*] Ensuring directories..."
sudo mkdir -p "$INSTALL_DIR/backups"
sudo mkdir -p /var/tmp/wp-backup-work
sudo chown -R ubuntu:ubuntu /var/tmp/wp-backup-work "$INSTALL_DIR"

echo "[*] Triggering D1 Sync..."
./venv/bin/python3 lib/d1_manager.py || echo "[!] D1 Sync skipped or failed."

echo ""
echo "Timer Status:"
systemctl status wordpress-backup.timer --no-pager || true
