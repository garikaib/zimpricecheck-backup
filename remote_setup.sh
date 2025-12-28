#!/bin/bash
set -e
INSTALL_DIR="$1"
REMOTE_USER="$2"
FLAG="$3"

echo "[*] Extracting MASTER bundle..."
cd "$INSTALL_DIR"
zstd -d -c bundle.tar.zst | tar -xf -

echo "[*] Clearing Python cache..."
find . -name '*.pyc' -delete 2>/dev/null || true
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo "[*] Setting up Master venv..."
if [ ! -d "venv" ]; then python3 -m venv venv; fi
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r master/requirements.txt --upgrade

echo "[*] Running Database Migrations..."
PYTHONPATH=. ./venv/bin/python3 -c "
import uuid
from sqlalchemy import text
from master.db.session import engine

with engine.connect() as conn:
    # Add uuid column to nodes
    try:
        conn.execute(text('ALTER TABLE nodes ADD COLUMN uuid VARCHAR(36)'))
        conn.commit()
        print('  Added uuid to nodes')
    except: pass
    
    # Add uuid column to sites
    try:
        conn.execute(text('ALTER TABLE sites ADD COLUMN uuid VARCHAR(36)'))
        conn.commit()
        print('  Added uuid to sites')
    except: pass
    
    # Add storage_used_bytes to nodes
    try:
        conn.execute(text('ALTER TABLE nodes ADD COLUMN storage_used_bytes INTEGER DEFAULT 0'))
        conn.commit()
        print('  Added storage_used_bytes to nodes')
    except: pass
    
    # Add storage_quota_gb to sites
    try:
        conn.execute(text('ALTER TABLE sites ADD COLUMN storage_quota_gb INTEGER DEFAULT 10'))
        conn.commit()
        print('  Added storage_quota_gb to sites')
    except: pass
    
    # Add quota_exceeded_at to sites
    try:
        conn.execute(text('ALTER TABLE sites ADD COLUMN quota_exceeded_at DATETIME'))
        conn.commit()
        print('  Added quota_exceeded_at to sites')
    except: pass
    
    # Add scheduled_deletion to backups
    try:
        conn.execute(text('ALTER TABLE backups ADD COLUMN scheduled_deletion DATETIME'))
        conn.commit()
        print('  Added scheduled_deletion to backups')
    except: pass

    # Add MFA fields
    try:
        conn.execute(text('ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN DEFAULT 0'))
        conn.commit()
        print('  Added mfa_enabled')
    except: pass
    
    try:
        conn.execute(text('ALTER TABLE users ADD COLUMN mfa_channel_id INTEGER REFERENCES communication_channels(id)'))
        conn.commit()
        print('  Added mfa_channel_id')
    except: pass
    
    try:
        conn.execute(text('ALTER TABLE users ADD COLUMN login_otp VARCHAR'))
        conn.commit()
        print('  Added login_otp')
    except: pass
    
    try:
        conn.execute(text('ALTER TABLE users ADD COLUMN login_otp_expires DATETIME'))
        conn.commit()
        print('  Added login_otp_expires')
    except: pass
    
    # Generate UUIDs for existing records
    for row in conn.execute(text('SELECT id FROM nodes WHERE uuid IS NULL')):
        conn.execute(text('UPDATE nodes SET uuid = :u WHERE id = :i'), {'u': str(uuid.uuid4()), 'i': row[0]})
        print(f'  Node {row[0]} assigned UUID')
    conn.commit()
    
    for row in conn.execute(text('SELECT id FROM sites WHERE uuid IS NULL')):
        conn.execute(text('UPDATE sites SET uuid = :u WHERE id = :i'), {'u': str(uuid.uuid4()), 'i': row[0]})
        print(f'  Site {row[0]} assigned UUID')
    conn.commit()
"

echo "[*] Initializing Database..."
PYTHONPATH=. ./venv/bin/python3 master/init_db.py

echo "[*] Super Admin: admin@example.com (created during init)"

echo "[*] Creating Systemd Service..."
cat > wordpress-master.service <<EOF
[Unit]
Description=WordPress Backup Master Server
After=network.target

[Service]
User=$REMOTE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/uvicorn master.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo mv wordpress-master.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wordpress-master.service

echo "[*] Restarting Master Server..."
sudo systemctl restart wordpress-master.service
sleep 2

echo "[*] Verifying service status..."
if sudo systemctl is-active --quiet wordpress-master.service; then
    echo "[+] Service is running!"
else
    echo "[!] Service failed to start. Checking logs..."
    sudo journalctl -u wordpress-master.service -n 20 --no-pager
    exit 1
fi

echo "[*] Fixing permissions..."
sudo chown -R "$REMOTE_USER":"$REMOTE_USER" "$INSTALL_DIR"

    # Web Setup (Optional)
    if [ "$FLAG" == "--web" ]; then
        echo "[*] Initializing Web Layer (Nginx + SSL)..."
        chmod +x master/setup_web.sh
        sudo ./master/setup_web.sh
    fi

echo "[+] Master Server deployed and running on port 8000!"
