# Deployment Guide

The `deploy.sh` script handles packaging and deploying the backup system to a remote server.

## Configuration

Set deployment target in `.env` or via wizard:

```bash
./configure.sh --deploy
```

### Deployment Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `REMOTE_HOST` | Server IP or hostname | `wp.zimpricecheck.com` |
| `REMOTE_USER` | SSH username | `ubuntu` |
| `REMOTE_PORT` | SSH port | `22` |
| `REMOTE_DIR` | Installation directory | `/opt/wordpress-backup` |

Example `.env`:
```env
REMOTE_HOST="192.168.1.100"
REMOTE_USER="ubuntu"
REMOTE_PORT="22"
REMOTE_DIR="/opt/wordpress-backup"
```

## Running Deployment

```bash
./deploy.sh
```

### What It Does

1. **Bundles files** — Creates `bundle.tar.zst` (excludes `venv`, `.git`, `backups`)
2. **Uploads** — Transfers bundle via SCP
3. **Extracts** — Unpacks on remote server
4. **Sets up Python** — Creates venv, installs dependencies (including `boto3` for S3)
5. **Resets logs** — Clears `backups.db` for a fresh start
6. **Generates systemd** — Runs `./configure.sh --systemd`
7. **Enables timers** — Configures automatic scheduling
8. **Triggers D1 sync** — Pulls/pushes database records

> [!IMPORTANT]  
> **Log Reset**: Each deployment clears the local `backups.db` database. This is intentional to start fresh with S3 storage. Historical data in Cloudflare D1 remains intact.

### Output Example

```
=============================================
  Deploying to ubuntu@192.168.1.100:22
  Remote Dir: /opt/wordpress-backup
=============================================
[*] Creating compressed bundle...
[*] Uploading to ubuntu@192.168.1.100:/opt/wordpress-backup...
[*] Running remote setup...
[*] Extracting bundle...
[*] Setting up Python virtual environment...
[*] Installing Python dependencies...
[*] Resetting logs database (fresh start)...
[+] Logs cleared.
[*] Generating Systemd configuration...
[*] Installing systemd services...
[*] Triggering D1 Sync...
[D1] Syncing table backup_log...
[D1] Sync complete.

Timer Status:
● wordpress-backup.timer - WordPress Backup Timer
     Loaded: loaded (/etc/systemd/system/wordpress-backup.timer; enabled)
     Active: active (waiting)

=============================================
        Deployment Complete!
=============================================
```

## Prerequisites

### Local Machine
- `zstd` installed
- SSH key configured for passwordless login

### Remote Server
- SSH access
- `sudo` privileges for the user
- Python 3.10+

## Troubleshooting

### Permission Denied
Ensure your SSH key is added:
```bash
ssh-copy-id -p 22 ubuntu@your-server.com
```

### Port Issues
If using non-standard SSH port:
```bash
./configure.sh --deploy
# Set REMOTE_PORT to your port
```

### Bundle Too Large
The bundle excludes:
- `venv/` — Virtual environment
- `.git/` — Git history
- `backups/` — Local archives
- `*.tar.zst` — Previous bundles
- `backups.db` — Local database

If still large, check for unexpected files in the project directory.
