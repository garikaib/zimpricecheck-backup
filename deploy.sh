#!/bin/bash
# Deployment Script

REMOTE_HOST="ubuntu@wp.zimpricecheck.com"
REMOTE_PORT="2200"
REMOTE_DIR="/opt/wordpress-backup"

# 0. Check Local Config
if [ ! -f ".env" ]; then
    echo "Configuration missing. Running setup wizard locally..."
    ./configure.sh
    if [ ! -f ".env" ]; then
        echo "Setup aborted."
        exit 1
    fi
fi

echo "Deploying to $REMOTE_HOST:$REMOTE_PORT..."

# 1. Bundle Files with ZSTD
echo "Creating compressed ZSTD bundle..."
if ! command -v zstd &> /dev/null; then
    echo "Error: zstd is not installed locally. Please run: sudo apt install zstd"
    exit 1
fi

# Create tarball compressed with zstd
# Explicitly include .env, lib, configure.sh, run.sh, requirements.txt
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

INSTALL_DIR="/opt/wordpress-backup"

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
chmod +x run.sh configure.sh lib/*.py

echo "[*] Generating Systemd configuration..."
# Generate systemd files on the remote server to ensure paths are correct
./configure.sh --systemd

echo "[*] Installing MEGAcmd if not present..."
if ! command -v mega-login &> /dev/null; then
    echo "Installing MEGAcmd..."
    wget -q https://mega.nz/linux/repo/xUbuntu_22.04/amd64/megacmd-xUbuntu_22.04_amd64.deb -O /tmp/megacmd.deb
    sudo apt-get update -qq
    sudo apt-get install -y /tmp/megacmd.deb
    rm -f /tmp/megacmd.deb
fi

echo "[*] Installing systemd services..."
if [ -d "systemd" ]; then
    sudo cp systemd/wordpress-backup.service /etc/systemd/system/
    sudo cp systemd/wordpress-backup.timer /etc/systemd/system/
    sudo cp systemd/wordpress-report.service /etc/systemd/system/
    sudo cp systemd/wordpress-report.timer /etc/systemd/system/

    echo "[*] Reloading systemd..."
    sudo systemctl daemon-reload
    
    echo "[*] Enabling timers..."
    sudo systemctl enable wordpress-backup.timer
    sudo systemctl enable wordpress-report.timer
    
    echo "[*] Starting timers..."
    sudo systemctl start wordpress-backup.timer
    sudo systemctl start wordpress-report.timer
else
    echo "WARNING: systemd directory not found after configuration!"
fi

echo "[*] Ensuring Directories..."
sudo mkdir -p "$INSTALL_DIR/backups"
sudo mkdir -p /var/tmp/wp-backup-work
sudo chown -R ubuntu:ubuntu /var/tmp/wp-backup-work
sudo chmod 775 /var/tmp/wp-backup-work

echo "[*] Triggering D1 Sync (if configured)..."
# Using the venv python to ensure requests is available
./venv/bin/python3 lib/d1_manager.py || echo "[!] D1 Sync encountered an error (or not configured)."

echo ""
echo "Timer Status:"
systemctl status wordpress-backup.timer --no-pager || true
echo ""
REMOTE_SCRIPT

chmod +x remote_setup.sh

# 3. Ensure remote directory & Upload
echo "Uploading bundle and setup script to $REMOTE_DIR..."
# Ensure directory exists
ssh -p $REMOTE_PORT -t $REMOTE_HOST "sudo mkdir -p $REMOTE_DIR && sudo chown ubuntu:ubuntu $REMOTE_DIR"
scp -P $REMOTE_PORT bundle.tar.zst remote_setup.sh $REMOTE_HOST:$REMOTE_DIR/

# 4. Remote Setup
echo "Running remote setup..."
ssh -p $REMOTE_PORT -t $REMOTE_HOST "cd $REMOTE_DIR && sudo bash remote_setup.sh"

# Cleanup local
rm -f bundle.tar.zst remote_setup.sh

echo ""
echo "=========================================="
echo "        Deployment Complete!"
echo "=========================================="
