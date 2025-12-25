# Configuration Reference

The `configure.sh` script provides an interactive wizard for managing all configuration. It supports both menu-driven and flag-based operation.

## Usage

```bash
./configure.sh [OPTIONS]
```

## Command Line Options

| Flag | Description |
|------|-------------|
| `--sites` | Jump directly to site management menu |
| `--deploy` | Configure deployment settings only |
| `--env` | Configure global credentials (Mega, SMTP, D1) |
| `--systemd` | Generate systemd service files (typically run on remote) |
| (no flags) | Launch interactive menu |

## Interactive Menu

When run without flags, the wizard presents:

```
==================================================
   Backup Configuration Wizard (SaaS Ready)
==================================================
 1. Manage WordPress Sites
 2. Configure Global Credentials (Mega, Email, D1)
 3. Configure Deployment Settings (SSH)
 4. Configure Backup Schedule & Retention
 5. Generate Systemd Files
 0. Exit
```

---

## Configuration Files

### `.env` — Global Settings

Contains credentials and settings shared across all sites:

```env
# Mega.nz Accounts
MEGA_EMAIL_1="your@email.com"
MEGA_PASSWORD_1="password"
MEGA_STORAGE_LIMIT_GB="19.5"

# SMTP Email
SMTP_SERVER="smtp.example.com"
SMTP_PORT="587"
SMTP_USER="notifications@example.com"
SMTP_PASSWORD="password"
SMTP_SENDER_EMAIL="backup@example.com"

# Backup Settings
BACKUP_DIR="/opt/wordpress-backup/backups"
BACKUP_FREQUENCY="daily"
BACKUP_TIME="00:00"
RETENTION_LOCAL_DAYS="2"
RETENTION_MEGA_DAYS="7"

# Cloudflare D1 (Optional)
CLOUDFLARE_ACCOUNT_ID=""
CLOUDFLARE_API_TOKEN=""
CLOUDFLARE_D1_DATABASE_ID=""

# Deployment Target
REMOTE_HOST="your-server.com"
REMOTE_USER="ubuntu"
REMOTE_PORT="22"
REMOTE_DIR="/opt/wordpress-backup"
```

### `sites.json` — Site Definitions

See [Managing Sites](sites.md) for details.

---

## Backup Frequency Options

| Value | Schedule |
|-------|----------|
| `daily` | Once per day at specified time |
| `twice` | Twice per day (midnight and noon) |
| `every-6h` | Every 6 hours |
| `every-2h` | Every 2 hours |

---

## Systemd Generation

The `--systemd` flag generates service files in `./systemd/`:

- `wordpress-backup.service` — Backup execution unit
- `wordpress-backup.timer` — Scheduled trigger
- `wordpress-report.service` — Daily email report
- `wordpress-report.timer` — Report schedule (8 AM)

**Important**: Run `--systemd` on the **remote server** after deployment to ensure paths are correct.

```bash
# On remote server
cd /opt/wordpress-backup
./configure.sh --systemd
sudo cp systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wordpress-backup.timer
```
