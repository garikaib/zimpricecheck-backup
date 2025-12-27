# Installation Guide

The platform is designed to be deployed via the `deploy.sh` script.

## Quick Start

### 1. Prerequisites
- **Controller Machine**: Linux/macOS with SSH access to targets.
- **Target Servers**: Ubuntu 22.04+ (Fresh install recommended).

### 2. Clone Repo
```bash
git clone <repo_url>
cd wordpress-backup
```

### 3. Deploy Master Server
This hosts the API, Database, and Dashboard.

```bash
# Configure environment
cp .env.example .env
nano .env  # Set POSTGRES_PASSWORD, SECRET_KEY, etc.

# Deploy
./deploy.sh master
```

**Verify:**
Visit `https://<master-ip>:8081` (API Docs) or `https://<master-ip>:8000`.

### 4. Deploy Node Agent
This runs on the VPS hosting the WordPress sites.

```bash
# Edit .env to point to Master
nano .env
# Set:
# MODE=node
# MASTER_URL=https://<master-ip>:8001
# REMOTE_HOST=<node-ip>

# Deploy
./deploy.sh node
```

**Post-Deploy:**
1.  SSH into Node.
2.  Get the Join Code (displayed in logs or via `daemon.main`).
3.  Approve Node in Master Dashboard.

## Manual Setup (Development)

See [Deployment Details](deployment.md) for advanced configurations.
