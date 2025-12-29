#!/bin/bash
# Deployment Script (SaaS Ready)
# Usage: ./deploy.sh [node|master] [--new] [--auto-approve]
#        ./deploy.sh  (interactive menu)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGETS_FILE="$SCRIPT_DIR/.deploy_targets.json"

# Initialize targets file if missing
if [ ! -f "$TARGETS_FILE" ]; then
    echo '{"masters":[],"nodes":[]}' > "$TARGETS_FILE"
fi

# Parse arguments
MODE="$1"
ARG2="$2"
ARG3="$3"

# Parse flags
IS_NEW=false
AUTO_APPROVE=false
for arg in "$@"; do
    case $arg in
        --new) IS_NEW=true ;;
        --auto-approve) AUTO_APPROVE=true ;;
    esac
done

# ==================== INTERACTIVE MENU ====================
show_main_menu() {
    clear
    echo "╔═══════════════════════════════════════════════════╗"
    echo "║       WordPress Backup Deployment Tool            ║"
    echo "╚═══════════════════════════════════════════════════╝"
    echo ""
    echo "1. Deploy Master"
    echo "2. Deploy Node"
    echo "3. View Saved Targets"
    echo "0. Exit"
    echo ""
    read -p "Select option: " MENU_CHOICE
    
    case $MENU_CHOICE in
        1) select_master_target ;;
        2) select_node_target ;;
        3) view_saved_targets ;;
        0) exit 0 ;;
        *) show_main_menu ;;
    esac
}

view_saved_targets() {
    echo ""
    echo "=== Saved Deployment Targets ==="
    echo ""
    echo "Masters:"
    cat "$TARGETS_FILE" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f'  - {m[\"name\"]}: {m[\"user\"]}@{m[\"host\"]}:{m[\"port\"]}') for m in d.get('masters',[])]" 2>/dev/null || echo "  (none)"
    echo ""
    echo "Nodes:"
    cat "$TARGETS_FILE" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f'  - {n[\"name\"]}: {n[\"user\"]}@{n[\"host\"]}:{n[\"port\"]}') for n in d.get('nodes',[])]" 2>/dev/null || echo "  (none)"
    echo ""
    read -p "Press Enter to continue..."
    show_main_menu
}

select_master_target() {
    echo ""
    echo "=== Deploy Master ==="
    
    # Load saved masters
    MASTERS=$(cat "$TARGETS_FILE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('masters',[])))" 2>/dev/null || echo "0")
    
    if [ "$MASTERS" -gt 0 ]; then
        echo ""
        echo "Saved masters:"
        cat "$TARGETS_FILE" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for i,m in enumerate(d.get('masters',[]),1):
    print(f'  {i}. {m[\"name\"]} ({m[\"user\"]}@{m[\"host\"]}:{m[\"port\"]})')
"
        echo "  N. Add new master"
        echo "  0. Back"
        echo ""
        read -p "Select: " SEL
        
        if [ "$SEL" = "0" ]; then
            show_main_menu
            return
        elif [ "$SEL" = "N" ] || [ "$SEL" = "n" ]; then
            add_new_master
            return
        else
            # Load selected master config
            eval $(cat "$TARGETS_FILE" | python3 -c "
import sys,json
d=json.load(sys.stdin)
idx=int('$SEL')-1
if 0 <= idx < len(d.get('masters',[])):
    m=d['masters'][idx]
    print(f'REMOTE_HOST=\"{m[\"host\"]}\"')
    print(f'REMOTE_USER=\"{m[\"user\"]}\"')
    print(f'REMOTE_PORT=\"{m[\"port\"]}\"')
    print(f'REMOTE_DIR=\"{m.get(\"dir\",\"/opt/wordpress-backup\")}\"')
")
            confirm_and_deploy "master"
        fi
    else
        add_new_master
    fi
}

add_new_master() {
    echo ""
    echo "=== Add New Master Target ==="
    read -p "Name (e.g., 'production'): " TARGET_NAME
    read -p "Host [wp.zimpricecheck.com]: " REMOTE_HOST
    REMOTE_HOST="${REMOTE_HOST:-wp.zimpricecheck.com}"
    read -p "User [ubuntu]: " REMOTE_USER
    REMOTE_USER="${REMOTE_USER:-ubuntu}"
    read -p "SSH Port [2200]: " REMOTE_PORT
    REMOTE_PORT="${REMOTE_PORT:-2200}"
    read -p "Remote Dir [/opt/wordpress-backup]: " REMOTE_DIR
    REMOTE_DIR="${REMOTE_DIR:-/opt/wordpress-backup}"
    
    # Save to targets file
    python3 -c "
import json
with open('$TARGETS_FILE','r') as f: d=json.load(f)
d.setdefault('masters',[]).append({'name':'$TARGET_NAME','host':'$REMOTE_HOST','user':'$REMOTE_USER','port':'$REMOTE_PORT','dir':'$REMOTE_DIR'})
with open('$TARGETS_FILE','w') as f: json.dump(d,f,indent=2)
"
    echo "✅ Saved target: $TARGET_NAME"
    
    IS_NEW=true
    confirm_and_deploy "master"
}

select_node_target() {
    echo ""
    echo "=== Deploy Node ==="
    
    NODES=$(cat "$TARGETS_FILE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('nodes',[])))" 2>/dev/null || echo "0")
    
    if [ "$NODES" -gt 0 ]; then
        echo ""
        echo "Saved nodes:"
        cat "$TARGETS_FILE" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for i,n in enumerate(d.get('nodes',[]),1):
    print(f'  {i}. {n[\"name\"]} ({n[\"user\"]}@{n[\"host\"]}:{n[\"port\"]})')
"
        echo "  N. Add new node"
        echo "  0. Back"
        echo ""
        read -p "Select: " SEL
        
        if [ "$SEL" = "0" ]; then
            show_main_menu
            return
        elif [ "$SEL" = "N" ] || [ "$SEL" = "n" ]; then
            add_new_node
            return
        else
            eval $(cat "$TARGETS_FILE" | python3 -c "
import sys,json
d=json.load(sys.stdin)
idx=int('$SEL')-1
if 0 <= idx < len(d.get('nodes',[])):
    n=d['nodes'][idx]
    print(f'REMOTE_HOST=\"{n[\"host\"]}\"')
    print(f'REMOTE_USER=\"{n[\"user\"]}\"')
    print(f'REMOTE_PORT=\"{n[\"port\"]}\"')
    print(f'REMOTE_DIR=\"{n.get(\"dir\",\"/opt/wordpress-backup\")}\"')
")
            confirm_and_deploy "node"
        fi
    else
        add_new_node
    fi
}

add_new_node() {
    echo ""
    echo "=== Add New Node Target ==="
    read -p "Name (e.g., 'node-api'): " TARGET_NAME
    read -p "Host: " REMOTE_HOST
    read -p "User [ubuntu]: " REMOTE_USER
    REMOTE_USER="${REMOTE_USER:-ubuntu}"
    read -p "SSH Port [22]: " REMOTE_PORT
    REMOTE_PORT="${REMOTE_PORT:-22}"
    read -p "Remote Dir [/opt/wordpress-backup]: " REMOTE_DIR
    REMOTE_DIR="${REMOTE_DIR:-/opt/wordpress-backup}"
    
    python3 -c "
import json
with open('$TARGETS_FILE','r') as f: d=json.load(f)
d.setdefault('nodes',[]).append({'name':'$TARGET_NAME','host':'$REMOTE_HOST','user':'$REMOTE_USER','port':'$REMOTE_PORT','dir':'$REMOTE_DIR'})
with open('$TARGETS_FILE','w') as f: json.dump(d,f,indent=2)
"
    echo "✅ Saved target: $TARGET_NAME"
    
    IS_NEW=true
    confirm_and_deploy "node"
}

confirm_and_deploy() {
    local deploy_mode="$1"
    echo ""
    echo "=== Deployment Configuration ==="
    echo "  Mode: $deploy_mode"
    echo "  Host: $REMOTE_USER@$REMOTE_HOST:$REMOTE_PORT"
    echo "  Dir:  $REMOTE_DIR"
    [ "$IS_NEW" = true ] && echo "  Fresh: YES (will prompt for config)"
    echo ""
    read -p "Deploy now? [Y/n/e(dit)]: " CONFIRM
    
    case $CONFIRM in
        n|N) show_main_menu ;;
        e|E) 
            read -p "Host [$REMOTE_HOST]: " NEW_HOST
            REMOTE_HOST="${NEW_HOST:-$REMOTE_HOST}"
            read -p "User [$REMOTE_USER]: " NEW_USER
            REMOTE_USER="${NEW_USER:-$REMOTE_USER}"
            read -p "Port [$REMOTE_PORT]: " NEW_PORT
            REMOTE_PORT="${NEW_PORT:-$REMOTE_PORT}"
            confirm_and_deploy "$deploy_mode"
            ;;
        *)
            MODE="$deploy_mode"
            export REMOTE_HOST REMOTE_USER REMOTE_PORT REMOTE_DIR
            ;;
    esac
}

# Show menu if no arguments provided
if [ -z "$MODE" ]; then
    show_main_menu
fi

# Validate mode if provided via CLI
if [[ "$MODE" != "node" && "$MODE" != "master" ]]; then
    echo "Usage: ./deploy.sh [node|master] [--new] [--auto-approve]"
    echo "       ./deploy.sh  (interactive menu)"
    echo ""
    echo "Flags:"
    echo "  --new          Fresh deployment with interactive config"
    echo "  --auto-approve Auto-approve node registration (node only)"
    exit 1
fi

# Fresh deployment prompts
prompt_master_config() {
    echo ""
    echo "=== Fresh Master Deployment ==="
    echo ""
    
    # SSH Target (where to deploy)
    echo "--- SSH Target (where to deploy code) ---"
    read -p "Master host [wp.zimpricecheck.com]: " REMOTE_HOST
    REMOTE_HOST="${REMOTE_HOST:-wp.zimpricecheck.com}"
    read -p "SSH User [ubuntu]: " REMOTE_USER
    REMOTE_USER="${REMOTE_USER:-ubuntu}"
    read -p "SSH Port [2200]: " REMOTE_PORT
    REMOTE_PORT="${REMOTE_PORT:-2200}"
    read -p "Remote Dir [/opt/wordpress-backup]: " REMOTE_DIR
    REMOTE_DIR="${REMOTE_DIR:-/opt/wordpress-backup}"
    
    echo ""
    echo "--- Admin Configuration ---"
    read -p "Admin email [garikaib@gmail.com]: " ADMIN_EMAIL
    ADMIN_EMAIL="${ADMIN_EMAIL:-garikaib@gmail.com}"
    
    # Generate random password
    ADMIN_PASSWORD=$(openssl rand -base64 12)
    
    echo ""
    echo "=== Summary ==="
    echo "  Deploy to: $REMOTE_USER@$REMOTE_HOST:$REMOTE_PORT"
    echo "  Remote Dir: $REMOTE_DIR"
    echo "  Admin email: $ADMIN_EMAIL"
    echo "  Admin password: $ADMIN_PASSWORD"
    echo ""
    echo "  ⚠️  Save this password - it won't be shown again!"
    echo ""
    read -p "Proceed? [Y/n]: " CONFIRM
    if [ "$CONFIRM" = "n" ] || [ "$CONFIRM" = "N" ]; then
        exit 0
    fi
    
    # Export for init_db.py
    export INIT_ADMIN_EMAIL="$ADMIN_EMAIL"
    export INIT_ADMIN_PASSWORD="$ADMIN_PASSWORD"
    # Mark that we have SSH target set
    export REMOTE_HOST REMOTE_USER REMOTE_PORT REMOTE_DIR
}

prompt_node_config() {
    echo ""
    echo "=== Fresh Node Deployment ==="
    echo ""
    
    # SSH Target (where to deploy)
    echo "--- SSH Target (where to deploy code) ---"
    read -p "Node host (e.g., api.zimpricecheck.com): " REMOTE_HOST
    if [ -z "$REMOTE_HOST" ]; then
        echo "Error: Node host is required"
        exit 1
    fi
    read -p "SSH User [ubuntu]: " REMOTE_USER
    REMOTE_USER="${REMOTE_USER:-ubuntu}"
    read -p "SSH Port [22]: " REMOTE_PORT
    REMOTE_PORT="${REMOTE_PORT:-22}"
    read -p "Remote Dir [/opt/wordpress-backup]: " REMOTE_DIR
    REMOTE_DIR="${REMOTE_DIR:-/opt/wordpress-backup}"
    
    echo ""
    echo "--- Daemon Configuration ---"
    read -p "Master API URL [https://wp.zimpricecheck.com:8081]: " MASTER_URL
    MASTER_URL="${MASTER_URL:-https://wp.zimpricecheck.com:8081}"
    
    read -p "Node hostname [$REMOTE_HOST]: " NODE_HOSTNAME
    NODE_HOSTNAME="${NODE_HOSTNAME:-$REMOTE_HOST}"
    
    echo ""
    echo "=== Summary ==="
    echo "  Deploy to: $REMOTE_USER@$REMOTE_HOST:$REMOTE_PORT"
    echo "  Remote Dir: $REMOTE_DIR"
    echo "  Master URL: $MASTER_URL"
    echo "  Node hostname: $NODE_HOSTNAME"
    echo ""
    read -p "Proceed? [Y/n]: " CONFIRM
    if [ "$CONFIRM" = "n" ] || [ "$CONFIRM" = "N" ]; then
        exit 0
    fi
    
    # Export for daemon config
    export BACKUPD_MASTER_URL="$MASTER_URL"
    export BACKUPD_HOSTNAME="$NODE_HOSTNAME"
    # Mark that we have SSH target set
    export REMOTE_HOST REMOTE_USER REMOTE_PORT REMOTE_DIR
}

# Run prompts if --new flag
if [ "$IS_NEW" = true ]; then
    if [ "$MODE" == "master" ]; then
        prompt_master_config
    else
        prompt_node_config
    fi
fi

# Load configuration from .env ONLY if not using --new flag
# (--new prompts set everything explicitly)
if [ "$IS_NEW" != true ] && [ -f ".env" ]; then
    export $(grep -v '^#' .env | sed 's/"//g' | xargs)
fi

# If REMOTE_HOST not set (CLI mode without interactive menu), prompt for it
if [ -z "$REMOTE_HOST" ]; then
    echo ""
    echo "=== Deployment Target ==="
    if [ "$MODE" == "master" ]; then
        read -p "Master host [wp.zimpricecheck.com]: " REMOTE_HOST
        REMOTE_HOST="${REMOTE_HOST:-wp.zimpricecheck.com}"
        read -p "SSH Port [2200]: " REMOTE_PORT
        REMOTE_PORT="${REMOTE_PORT:-2200}"
    else
        read -p "Node host (e.g., api.zimpricecheck.com): " REMOTE_HOST
        if [ -z "$REMOTE_HOST" ]; then
            echo "Error: Node host is required"
            exit 1
        fi
        read -p "SSH Port [22]: " REMOTE_PORT
        REMOTE_PORT="${REMOTE_PORT:-22}"
    fi
    read -p "SSH User [ubuntu]: " REMOTE_USER
    REMOTE_USER="${REMOTE_USER:-ubuntu}"
    read -p "Remote Dir [/opt/wordpress-backup]: " REMOTE_DIR
    REMOTE_DIR="${REMOTE_DIR:-/opt/wordpress-backup}"
fi

# Apply remaining defaults only if still unset
REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_PORT="${REMOTE_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:-/opt/wordpress-backup}"

SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"

echo "============================================="
echo "  Deploying [$MODE] to ${SSH_TARGET}:${REMOTE_PORT}"
echo "  Remote Dir: ${REMOTE_DIR}"
if [ "$IS_NEW" = true ]; then
    echo "  Mode: FRESH DEPLOYMENT"
fi
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

echo "[*] Checking prerequisites..."

echo "[*] Checking prerequisites..."

# Detect Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
echo "    Python version: $PYTHON_VERSION"

# Check for required packages
MISSING_PKGS=""
# Check for ensurepip specifically (often missing in bare python3)
if ! python3 -c "import ensurepip" 2>/dev/null; then
    MISSING_PKGS="$MISSING_PKGS python${PYTHON_VERSION}-venv"
fi
if ! command -v zstd &>/dev/null; then
    MISSING_PKGS="$MISSING_PKGS zstd"
fi
if ! command -v pip3 &>/dev/null; then
    MISSING_PKGS="$MISSING_PKGS python3-pip"
fi

# Build dependencies function (only installed if needed)
install_build_deps() {
    echo "[!] pip install failed. Likely missing build tools for Python $PYTHON_VERSION wheels."
    echo "[*] Installing build dependencies (cargo, rustc, dev tools)..."
    MISSING_DEPS=""
    if ! command -v cargo &>/dev/null; then MISSING_DEPS="$MISSING_DEPS cargo rustc"; fi
    if ! dpkg -s build-essential &>/dev/null; then MISSING_DEPS="$MISSING_DEPS build-essential"; fi
    if ! dpkg -s python3-dev &>/dev/null; then MISSING_DEPS="$MISSING_DEPS python3-dev"; fi
    
    if [ -n "$MISSING_DEPS" ]; then
        sudo apt-get update -qq
        sudo apt-get install -y $MISSING_DEPS
    fi
}

echo "[*] Installing dependencies..."
./venv/bin/pip install --upgrade pip -q
if ! ./venv/bin/pip install -r requirements.txt -q; then
    install_build_deps
    echo "[*] Retrying installation with build tools..."
    ./venv/bin/pip install -r requirements.txt -q
fi

if [ -f "daemon/requirements.txt" ]; then
    if ! ./venv/bin/pip install -r daemon/requirements.txt -q; then
        install_build_deps
        echo "[*] Retrying daemon deps with build tools..."
        ./venv/bin/pip install -r daemon/requirements.txt -q
    fi
fi

echo "[*] Creating work directories..."
sudo mkdir -p "$INSTALL_DIR/backups" /var/tmp/wp-backup-work
sudo rm -f /var/tmp/wp-backup.pid /var/tmp/wp-backup.status

echo "[*] Triggering D1 Sync..."
sudo -u "$REMOTE_USER" ./venv/bin/python3 lib/d1_manager.py 2>/dev/null || echo "    D1 Sync skipped (not configured)."

echo "[*] Fixing permissions..."
sudo chown -R "$REMOTE_USER":"$REMOTE_USER" /var/tmp/wp-backup-work "$INSTALL_DIR"

echo "[+] Node setup complete!"
echo "    Next: Configure systemd service and start daemon"
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
        --exclude='master.db' \
        -c master daemon .env lib scripts alembic alembic.ini | zstd - > bundle.tar.zst

    # Generate Master Setup Script
    cat > remote_setup.sh << 'REMOTE_SCRIPT'
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

    echo "[*] Running Alembic Migrations..."
    if [ -f "alembic.ini" ]; then
        ./venv/bin/alembic upgrade head || echo "[!] Alembic migration failed, continuing..."
    fi

# Fix permissions BEFORE init_db (SQLite needs write on directory + file for journal)
echo "[*] Setting database permissions..."
sudo chown -R "$REMOTE_USER":"$REMOTE_USER" "$INSTALL_DIR"
chmod 755 "$INSTALL_DIR"
[ -f "$INSTALL_DIR/master.db" ] && chmod 664 "$INSTALL_DIR/master.db"

echo "[*] Initializing Database..."
PYTHONPATH=. ./venv/bin/python3 master/init_db.py

# Ensure database is writable after init creates it
[ -f "$INSTALL_DIR/master.db" ] && chmod 664 "$INSTALL_DIR/master.db"

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

echo "[*] Final permission check..."
sudo chown -R "$REMOTE_USER":"$REMOTE_USER" "$INSTALL_DIR"
# Ensure database is writable by the service user
[ -f "$INSTALL_DIR/master.db" ] && chmod 664 "$INSTALL_DIR/master.db"

    # Web Setup (Optional)
    if [ "$FLAG" == "--web" ]; then
        echo "[*] Initializing Web Layer (Nginx + SSL)..."
        chmod +x master/setup_web.sh
        sudo ./master/setup_web.sh
    fi

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
ssh -p ${REMOTE_PORT} -t ${SSH_TARGET} "cd ${REMOTE_DIR} && sudo bash remote_setup.sh ${REMOTE_DIR} ${REMOTE_USER} ${ARG2}"

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
