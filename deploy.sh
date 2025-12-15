#!/bin/bash

REMOTE_HOST="ubuntu@wp.zimpricecheck.com"
REMOTE_PORT="2200"
REMOTE_DIR="/opt/wordpress-backup"

# 0. Check Local Config
if [ ! -f ".env" ] || [ ! -f "wordpress-backup.service" ]; then
    echo "Configuration missing. Running setup wizard locally..."
    python3 configure.py
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

# Create tarball compressed with zstd, excluding unwanted files
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
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "[*] Setting permissions..."
chmod +x run.sh deploy.sh

echo "[*] Creating backup directory..."
mkdir -p "$INSTALL_DIR/backups"

echo "[*] Ensuring temp directory permissions..."
# Ensure default temp dir exists and is owned by ubuntu
mkdir -p /var/tmp/wp-backup-work
chown -R ubuntu:ubuntu /var/tmp/wp-backup-work
chmod 775 /var/tmp/wp-backup-work

echo "[*] Installing MEGAcmd if not present..."
if ! command -v mega-login &> /dev/null; then
    echo "[*] Downloading MEGAcmd..."
    wget -q https://mega.nz/linux/repo/xUbuntu_22.04/amd64/megacmd-xUbuntu_22.04_amd64.deb -O /tmp/megacmd.deb
    apt-get update -qq
    apt-get install -y /tmp/megacmd.deb
    rm -f /tmp/megacmd.deb
    echo "[+] MEGAcmd installed"
else
    echo "[+] MEGAcmd already installed"
fi

echo "[*] Installing systemd services..."
cp wordpress-backup.service /etc/systemd/system/
cp wordpress-backup.timer /etc/systemd/system/
cp wordpress-report.service /etc/systemd/system/
cp wordpress-report.timer /etc/systemd/system/

echo "[*] Reloading systemd..."
systemctl daemon-reload

echo "[*] Enabling timers..."
systemctl enable wordpress-backup.timer
systemctl enable wordpress-report.timer

echo "[*] Starting timers..."
systemctl start wordpress-backup.timer
systemctl start wordpress-report.timer

echo "[*] Cleaning up..."
rm -f bundle.tar.zst remote_setup.sh

echo ""
echo "=== Deployment Complete ==="
echo "Timer Status:"
systemctl status wordpress-backup.timer --no-pager || true
echo ""
echo "Next scheduled backup:"
systemctl list-timers wordpress-backup.timer --no-pager || true
REMOTE_SCRIPT

chmod +x remote_setup.sh

# 3. Ensure remote directory & Upload
echo "Uploading bundle and setup script to $REMOTE_DIR..."
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
echo ""
echo "Remote server: $REMOTE_HOST:$REMOTE_PORT"
echo "Install path:  $REMOTE_DIR"
echo ""
echo "To check status:"
echo "  ssh -p $REMOTE_PORT $REMOTE_HOST 'systemctl status wordpress-backup.timer'"
echo ""
echo "To run backup manually:"
echo "  ssh -p $REMOTE_PORT $REMOTE_HOST 'cd $REMOTE_DIR && sudo ./run.sh'"
