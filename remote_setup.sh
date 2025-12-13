#!/bin/bash
set -e

DIR="/opt/mongo-sync-backup"
cd "$DIR"

echo "[*] Unpacking bundle..."
if [ -f bundle.tar.zst ]; then
    zstd -d bundle.tar.zst --stdout | tar -x
    rm bundle.tar.zst
fi

echo "[*] Setting up Python Environment..."
python3 -m venv venv
source venv/bin/activate

# Fix dependencies
pip install "tenacity>=8.2.0" "python-dotenv" "requests" "pycryptodome" "pytz"
pip install "mega.py==1.0.8" --no-deps
# pycrypto is often installed by mega.py deps but conflicts with pycryptodome
if pip show pycrypto > /dev/null 2>&1; then
    pip uninstall -y pycrypto
fi

echo '[+] Dependencies installed.'

echo '[*] Installing Systemd Services...'
# Install Backup Service
cp mongodb-backup.service /etc/systemd/system/
cp mongodb-backup.timer /etc/systemd/system/

# Install Report Service
cp mongodb-report.service /etc/systemd/system/
cp mongodb-report.timer /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now mongodb-backup.timer
systemctl enable --now mongodb-report.timer
chmod +x run.sh

# Ensure permissions
mkdir -p "$DIR/backups"
chown -R ubuntu:ubuntu "$DIR"

echo '[+] Systemd timers started.'
systemctl status mongodb-backup.timer --no-pager
systemctl status mongodb-report.timer --no-pager
