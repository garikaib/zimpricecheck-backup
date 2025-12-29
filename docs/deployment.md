# Deployment Guide

The `deploy.sh` script supports two distinct deployment targets: **Master** and **Node**.

## Quick Start

```bash
# Interactive menu (recommended for first-time setup)
./deploy.sh

# Direct deployment with flags
./deploy.sh master              # Deploy to saved master target
./deploy.sh master --new        # Fresh master deployment with prompts  
./deploy.sh node                # Deploy to saved node target
./deploy.sh node --new          # Fresh node deployment with prompts
```

## Prerequisites

- **Local Machine**: Linux/Mac with `ssh`, `scp`, `python3`, `zstd`
- **Remote Server**: Ubuntu 20.04/22.04 LTS (recommended)
- **SSH Access**: Must have SSH access to the target server

---

## Interactive Menu

When run without arguments, `./deploy.sh` shows an interactive menu:

```
╔═══════════════════════════════════════════════════╗
║       WordPress Backup Deployment Tool            ║
╚═══════════════════════════════════════════════════╝

1. Deploy Master
2. Deploy Node
3. View Saved Targets
0. Exit
```

**Features:**
- **Saved Targets**: Deployment targets are saved in `.deploy_targets.json`
- **Confirm/Edit Workflow**: Shows current config, asks [Y/n/e(dit)]
- **Fresh Deployments**: New targets automatically prompt for config

---

## 1. Deploying the Master Server

The Master Server hosts the API, Database (SQLite), and Scheduler.

### Fresh Deployment
```bash
./deploy.sh master --new
```

Prompts for:
- Admin email (default: garikaib@gmail.com)
- Generates random admin password (displayed once)

### Update Deployment
```bash
./deploy.sh master
```

Updates code without reinitializing credentials.

### What Happens
1. Uploads Master code (`master/`) and Daemon (`daemon/`)
2. Installs dependencies (`master/requirements.txt`)
3. Runs `init_db.py`:
   - Schema Integrity Check (auto-adds missing columns)
   - Creates Superuser (random password if new)
   - Creates Master Node record (quota: 0)
   - **Note**: Email channels are NOT auto-seeded. Use `./admin.sh` to configure.
4. Sets up `systemd` service: `wordpress-master.service`

### Verify
```bash
curl https://<master-domain>/api/v1/storage/health
```

---

## 2. Deploying a Backup Node

Nodes are the servers running WordPress that perform the actual backups.

### Fresh Deployment
```bash
./deploy.sh node --new
```

Prompts for:
- Master API URL (e.g., `https://wp.zimpricecheck.com:8081`)
- Node hostname

### Update Deployment
```bash
./deploy.sh node
```

### What Happens
1. Uploads Daemon code (`daemon/`)
2. Installs dependencies (`daemon/requirements.txt`)
3. Configures `systemd` service: `wordpress-backup.service`
4. Node registers with Master in **PENDING** state

### Activation
Admin must approve the node via:
- Dashboard: Nodes → Approve
- CLI: `./admin.sh` → Node Management → Approve

---

## 3. Admin CLI

The `admin.sh` script provides direct database access (bypasses FastAPI):

```bash
./admin.sh                      # Interactive menu
./admin.sh reset-password user@example.com
./admin.sh disable-mfa user@example.com
./admin.sh list-users
./admin.sh status
```

### Menu Options
1. **User Management**: Reset password, disable MFA, create admin
2. **Storage Management**: Add S3 provider, set limits
3. **Node Management**: Approve, block, set quotas
4. **System**: Status, reset quotas, danger zone

---

## 4. Storage Quotas

**Important**: Storage quotas start at **0** by default.

- No allocations until remote storage is configured
- Use `./admin.sh` → Storage Management → Add S3 provider
- Then allocate quotas to nodes via `./admin.sh` or dashboard

---

## 5. Database Management

The Master Server uses a robust self-healing database strategy.

- **Integrity Check**: On every deployment, `init_db.py` validates schema
- **Auto-Migration**: Missing tables/columns are automatically added
- **Permissions**: `deploy.sh` enforces correct file ownership

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "no such column" | Re-run deployment to trigger integrity check |
| "readonly database" | Redeploy with `./deploy.sh master` |
| Service failures | `journalctl -u wordpress-master -f` |
| No email sending | Configure channels via `./admin.sh` |
