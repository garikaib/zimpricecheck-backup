#!/bin/bash
# Deployment Script (SaaS Ready)
# Reads deployment target from .env

set -e

# Load configuration from .env
if [ -f ".env" ]; then
    # Parse .env safely (handles quotes)
    export $(grep -v '^#' .env | sed 's/"//g' | xargs)
fi

# Deployment Settings (with defaults)
REMOTE_HOST="${REMOTE_HOST:-wp.zimpricecheck.com}"
REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_PORT="${REMOTE_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:-/opt/wordpress-backup}"

# Full SSH target
SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"

# 0. Check Local Config
if [ ! -f ".env" ]; then
    echo "Configuration missing. Running setup wizard..."
    ./configure.sh
    if [ ! -f ".env" ]; then
        echo "Setup aborted."
        exit 1
    fi
    # Reload after configuration
    export $(grep -v '^#' .env | sed 's/"//g' | xargs)
    REMOTE_HOST="${REMOTE_HOST:-wp.zimpricecheck.com}"
    REMOTE_USER="${REMOTE_USER:-ubuntu}"
    REMOTE_PORT="${REMOTE_PORT:-22}"
    REMOTE_DIR="${REMOTE_DIR:-/opt/wordpress-backup}"
    SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"
fi

echo "============================================="
echo "  Deploying to ${SSH_TARGET}:${REMOTE_PORT}"
echo "  Remote Dir: ${REMOTE_DIR}"
echo "============================================="

# 1. Bundle Files with ZSTD
echo "[*] Creating compressed bundle..."
if ! command -v zstd &> /dev/null; then
    echo "Error: zstd is not installed. Run: sudo apt install zstd"
    exit 1
fi

# Create tarball (exclude venv, git, pycache, backups, db)
tar --exclude='./venv' \
    --exclude='./.git' \
    --exclude='./__pycache__' \
    --exclude='./backups' \
    --exclude='*.tar.zst' \
    --exclude='*.pyc' \
    --exclude='backups.db' \
    -c . | zstd - > bundle.tar.zst

# 2. Generate remote setup script
cat > remote_setup.sh << 'REMOTE_SCRIPT'
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

echo "[*] Generating Systemd configuration..."
./configure.sh --systemd

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
REMOTE_SCRIPT

chmod +x remote_setup.sh

# 3. Upload
echo "[*] Uploading to ${SSH_TARGET}:${REMOTE_DIR}..."
ssh -p ${REMOTE_PORT} -t ${SSH_TARGET} "sudo mkdir -p ${REMOTE_DIR} && sudo chown ${REMOTE_USER}:${REMOTE_USER} ${REMOTE_DIR}"
scp -P ${REMOTE_PORT} bundle.tar.zst remote_setup.sh ${SSH_TARGET}:${REMOTE_DIR}/

# 4. Remote Setup
echo "[*] Running remote setup..."
ssh -p ${REMOTE_PORT} -t ${SSH_TARGET} "cd ${REMOTE_DIR} && sudo bash remote_setup.sh ${REMOTE_DIR}"

# Cleanup
rm -f bundle.tar.zst remote_setup.sh

echo ""
echo "============================================="
echo "        Deployment Complete!"
echo "============================================="
