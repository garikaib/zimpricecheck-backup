#!/bin/bash

REMOTE_HOST="ubuntu@51.195.252.90"
REMOTE_DIR="/opt/mongo-sync-backup"

# 0. Check Local Config
if [ ! -f ".env" ] || [ ! -f "mongodb-backup.service" ]; then
    echo "Configuration missing. Running setup wizard locally..."
    python3 configure.py
    if [ ! -f ".env" ]; then
        echo "Setup aborted."
        exit 1
    fi
fi

echo "Deploying to $REMOTE_HOST..."

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
    -c . | zstd - > bundle.tar.zst

# 2. Ensure remote directory & Upload
echo "Uploading bundle and setup script to $REMOTE_DIR..."
ssh -t $REMOTE_HOST "sudo mkdir -p $REMOTE_DIR && sudo chown ubuntu:ubuntu $REMOTE_DIR"
scp bundle.tar.zst remote_setup.sh $REMOTE_HOST:$REMOTE_DIR/

# 3. Remote Setup
echo "Running remote setup..."
# We use sudo bash to run the setup script with root privileges for systemd/pip/permissions
ssh -t $REMOTE_HOST "cd $REMOTE_DIR && sudo bash remote_setup.sh"

# Cleanup local
rm bundle.tar.zst
rm remote_setup.sh

echo "Deployment complete."
