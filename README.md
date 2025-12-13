# MongoDB Sync & Backup System

Automated solution for backing up a primary MongoDB instance, restoring to a secondary instance (sync), uploading encrypted archives to Mega.nz, and reporting activity.

## Features
- **Backup**: Dumps MongoDB to compressed `bzip2` archives.
- **Sync**: Restores archive to a destination MongoDB server (with `--drop` to ensure sync).
- **Offsite**: Uploads encrypted backup to Mega.nz.
- **Retention**: Keeps 2 days locally, 7 days on Mega.
- **Reporting**: Daily email summary of all jobs (Africa/Harare time). Fails are emailed immediately.
- **Resilience**: Retries network operations via `tenacity`.
- **Skip Backup**: Ability to sync using the latest existing backup (`--skip-backup`).

## Installation

### 1. Requirements
- Linux Server (Ubuntu recommended)
- Python 3.12+
- `systemd`

### 2. Local Setup
1.  Clone this repository.
2.  Run `./deploy.sh`

The deployment script will:
- Check for local configuration.
- Run `configure.py` (Wizard) if needed.
- Bundle the code.
- Upload to your remote server (`51.195.252.90`).
- Install dependencies and systemd services remotely.

### 3. Configuration
The `configure.py` wizard will generate a `.env` file. You can edit this file manually if needed:

```env
MONGO_SOURCE_URI="..."
MONGO_DEST_URI="..."
MEGA_EMAIL="..."
MEGA_PASSWORD="..."
SMTP_SERVER="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USER="..."
SMTP_PASSWORD="..."
SMTP_SENDER_EMAIL="business@zimpricecheck.com"
```

## Usage

### Automatic
- **Backups**: Run every 2 hours (via `mongodb-backup.timer`).
- **Reports**: Run daily at 08:00 AM (via `mongodb-report.timer`).

### Manual
To run manually on the server:

```bash
cd /opt/mongo-sync-backup
sudo ./run.sh
```

To retry a sync using the *latest* existing backup (skip dumping):

```bash
sudo ./run.sh --skip-backup
```

### Checking Status
```bash
systemctl status mongodb-backup.timer
systemctl status mongodb-report.timer
```

## Troubleshooting
- **Logs**: Check `systemctl status mongodb-backup.service` or the `backups.db` SQLite file.
- **Permission Denied**: Ensure you run `run.sh` with `sudo` or as the `ubuntu` user, as the `backups/` directory belongs to `ubuntu`.
