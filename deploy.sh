#!/bin/bash
# Deployment Script (SaaS Ready)
# Usage: ./deploy.sh [node|master]

set -e

MODE="${1:-node}"
TEST_FLAG="$2"

if [[ "$MODE" != "node" && "$MODE" != "master" ]]; then
    echo "Usage: ./deploy.sh [node|master] [--test]"
    exit 1
fi

# Load configuration from .env
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | sed 's/"//g' | xargs)
fi

# Deployment Settings (Defaults)
REMOTE_HOST="${REMOTE_HOST:-wp.zimpricecheck.com}"
REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_PORT="${REMOTE_PORT:-22}"

# Different defaults based on mode
if [ "$MODE" == "master" ]; then
    REMOTE_DIR="${REMOTE_DIR:-/opt/wordpress-backup-master}"
else
    REMOTE_DIR="${REMOTE_DIR:-/opt/wordpress-backup}"
fi

SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"

echo "============================================="
echo "  Deploying [$MODE] to ${SSH_TARGET}:${REMOTE_PORT}"
echo "  Remote Dir: ${REMOTE_DIR}"
echo "============================================="

# Ensure ZSTD logic
if ! command -v zstd &> /dev/null; then
    echo "Error: zstd is not installed. Run: sudo apt install zstd"
    exit 1
fi

deploy_node() {
    echo "[*] Creating NODE bundle..."
    
    # Bundle Agent Files
    tar --exclude='./venv' \
        --exclude='venv' \
        --exclude='./.git' \
        --exclude='./master' \
        --exclude='./__pycache__' \
        --exclude='./backups' \
        --exclude='*.tar.zst' \
        --exclude='*.pyc' \
        --exclude='backups.db' \
        -c . | zstd - > bundle.tar.zst

    # Generate Node Setup Script
    cat > remote_setup.sh << 'REMOTE_SCRIPT'
#!/bin/bash
set -e
INSTALL_DIR="$1"
REMOTE_USER="$2"

echo "[*] Extracting NODE bundle..."
cd "$INSTALL_DIR"
zstd -d -c bundle.tar.zst | tar -xf -

echo "[*] Setting up Python venv..."
if [ ! -d "venv" ]; then python3 -m venv venv; fi
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q

chmod +x run.sh configure.sh lib/*.py 2>/dev/null || true

echo "[*] Resetting logs database..."
rm -f backups.db

echo "[*] Running configuration..."
./venv/bin/python3 lib/configure.py --systemd

echo "[*] Installing services..."
if [ -d "systemd" ]; then
    sudo cp systemd/*.service /etc/systemd/system/ 2>/dev/null || true
    sudo cp systemd/*.timer /etc/systemd/system/ 2>/dev/null || true
    sudo systemctl daemon-reload
    sudo systemctl enable wordpress-backup.timer wordpress-report.timer 2>/dev/null || true
    sudo systemctl start wordpress-backup.timer wordpress-report.timer 2>/dev/null || true
fi

sudo mkdir -p "$INSTALL_DIR/backups" /var/tmp/wp-backup-work
sudo rm -f /var/tmp/wp-backup.pid /var/tmp/wp-backup.status

echo "[*] Triggering D1 Sync..."
sudo -u "$REMOTE_USER" ./venv/bin/python3 lib/d1_manager.py || echo "[!] D1 Sync skipped."

echo "[*] Fixing permissions..."
sudo chown -R "$REMOTE_USER":"$REMOTE_USER" /var/tmp/wp-backup-work "$INSTALL_DIR"
REMOTE_SCRIPT
}

deploy_master() {
    echo "[*] Creating MASTER bundle..."
    
    # Bundle Master Files
    # Note: We exclude 'master/venv' explicitly
    tar --exclude='master/venv' \
        --exclude='master/.env' \
        --exclude='venv' \
        --exclude='./.git' \
        --exclude='./lib' \
        --exclude='./docs' \
        --exclude='./backups' \
        --exclude='*.tar.zst' \
        --exclude='*.pyc' \
        --exclude='__pycache__' \
        --exclude='master.db' \
        -c master .env | zstd - > bundle.tar.zst

    # Generate Master Setup Script
    cat > remote_setup.sh << 'REMOTE_SCRIPT'
#!/bin/bash
set -e
INSTALL_DIR="$1"
REMOTE_USER="$2"

echo "[*] Extracting MASTER bundle..."
cd "$INSTALL_DIR"
zstd -d -c bundle.tar.zst | tar -xf -

echo "[*] Setting up Master venv..."
if [ ! -d "venv" ]; then python3 -m venv venv; fi
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r master/requirements.txt -q

echo "[*] Initializing Database..."
PYTHONPATH=. ./venv/bin/python3 master/init_db.py

echo "[*] Verifying Super Admins..."
./venv/bin/python3 lib/configure.py --add-admin <<EOF
2
EOF
# Note: The above runs add-admin interactively but instantly exits (Option 2) to trigger the list_admins() print.

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
sudo systemctl enable --now wordpress-master.service

echo "[*] Fixing permissions..."
sudo chown -R "$REMOTE_USER":"$REMOTE_USER" "$INSTALL_DIR"

echo "[+] Master Server deployed and running on port 8000!"
REMOTE_SCRIPT
}

# Execute Mode
if [ "$MODE" == "node" ]; then
    deploy_node
else
    deploy_master
fi

chmod +x remote_setup.sh

# Upload & Run
echo "[*] Uploading to ${SSH_TARGET}:${REMOTE_DIR}..."
ssh -p ${REMOTE_PORT} -t ${SSH_TARGET} "sudo mkdir -p ${REMOTE_DIR} && sudo chown ${REMOTE_USER}:${REMOTE_USER} ${REMOTE_DIR}"
scp -P ${REMOTE_PORT} bundle.tar.zst remote_setup.sh ${SSH_TARGET}:${REMOTE_DIR}/

echo "[*] Executing remote setup..."
ssh -p ${REMOTE_PORT} -t ${SSH_TARGET} "cd ${REMOTE_DIR} && sudo bash remote_setup.sh ${REMOTE_DIR} ${REMOTE_USER}"

# Cleanup
rm -f bundle.tar.zst remote_setup.sh

echo ""
echo "============================================="
echo "        Deployment Complete!"
echo "============================================="

# Test Mode: Create Tunnel
if [[ "$MODE" == "master" && "$TEST_FLAG" == "--test" ]]; then
    echo ""
    echo "[*] TEST MODE: Establishing SSH Tunnel..."
    echo "    Forwarding localhost:8001 -> ${REMOTE_HOST}:8000"
    echo "    You can now access the API at http://localhost:8001"
    echo "    Press Ctrl+C to stop the tunnel."
    
    # Check if port 8001 is already in use
    if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null ; then
        echo "[!] Port 8001 is already in use. Killing old tunnel..."
        lsof -ti:8001 | xargs kill -9 2>/dev/null || true
    fi
    
    ssh -N -L 8001:localhost:8000 -p ${REMOTE_PORT} ${SSH_TARGET}
fi
