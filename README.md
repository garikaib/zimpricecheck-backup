# WordPress Backup System

Automated backup solution for WordPress sites including database, wp-config.php, and wp-content. Backups are uploaded to Mega.nz for offsite storage with support for up to 3 accounts.

## Features

- **Complete WordPress Backup**: Backs up database, wp-config.php, and wp-content
- **MariaDB Support**: Uses `mysqldump` with `--add-drop-table` for clean restores
- **Multi-Mega Storage**: Supports up to 3 Mega.nz accounts (each 19.5 GB usable)
- **Smart Rotation**: Automatically deletes oldest archives across all accounts when full
- **Configurable Schedule**: Daily at midnight (Africa/Harare) by default, configurable
- **Daily Reports**: Email summary with file sizes and storage account info
- **Failure Alerts**: Immediate email notification on backup failures
- **Compression**: Uses `zstd` for efficient compression

## Storage Accounts

| Account | Email | Usable Space |
|---------|-------|--------------|
| Primary | garikai@zimpricecheck.com | 19.5 GB |
| Secondary | (Optional) | 19.5 GB |
| Tertiary | (Optional) | 19.5 GB |

> **Note**: Mega free accounts have 20 GB storage. We use 19.5 GB to allow 500 MB overhead.

## WordPress Paths

| Component | Path |
|-----------|------|
| wp-config.php | `/var/www/zimpricecheck.com/wp-config.php` |
| wp-content | `/var/www/zimpricecheck.com/htdocs/wp-content` |
| Temp Directory | `/var/tmp/wp-backup-work` |

## Installation

### Requirements

- Ubuntu Server (tested on 22.04+)
- Python 3.10+
- MariaDB client tools (`mysqldump`)
- `systemd`
- `zstd` compression utility
- `MEGAcmd` CLI tools (automatically installed by deploy script if missing)

### Quick Deploy

1. Clone this repository locally:
   ```bash
   git clone <repo-url>
   cd wordpress-backup
   ```

2. Run the configuration wizard:
   ```bash
   python3 configure.py
   ```

3. Deploy to remote server:
   ```bash
   ./deploy.sh
   ```

The deploy script will:
- Bundle the code
- Upload to `ubuntu@wp.zimpricecheck.com:2200`
- Install to `/opt/wordpress-backup`
- Set up systemd timers

### Manual Installation

```bash
# On remote server
sudo mkdir -p /opt/wordpress-backup
cd /opt/wordpress-backup

# Copy files and setup venv
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Install systemd services
sudo cp wordpress-backup.service /etc/systemd/system/
sudo cp wordpress-backup.timer /etc/systemd/system/
sudo cp wordpress-report.service /etc/systemd/system/
sudo cp wordpress-report.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wordpress-backup.timer
sudo systemctl enable --now wordpress-report.timer
```

## Configuration

Edit `.env` file to configure:

```env
# WordPress Paths
WP_CONFIG_PATH="/var/www/zimpricecheck.com/wp-config.php"
WP_CONTENT_PATH="/var/www/zimpricecheck.com/htdocs/wp-content"

# MariaDB (leave empty to auto-extract from wp-config.php)
DB_HOST=""
DB_NAME=""
DB_USER=""
DB_PASSWORD=""

# Mega Accounts
MEGA_EMAIL_1="garikai@zimpricecheck.com"
MEGA_PASSWORD_1="your-password"
MEGA_EMAIL_2=""  # Optional
MEGA_EMAIL_3=""  # Optional

# Backup Schedule
BACKUP_FREQUENCY="daily"  # daily, twice, every-6h, every-2h
BACKUP_TIME="00:00"       # Africa/Harare timezone

# Retention
RETENTION_LOCAL_DAYS=2
RETENTION_MEGA_DAYS=7
```

## Usage

### Automatic Backups

Backups run automatically based on the configured schedule:
- Default: Daily at midnight (Africa/Harare, UTC+2)

### Manual Backup

```bash
cd /opt/wordpress-backup
sudo ./run.sh
```

### Dry Run

Test configuration without creating actual backups:

```bash
sudo ./run.sh --dry-run
```

### Check Status

```bash
# Timer status
systemctl status wordpress-backup.timer

# Next scheduled run
systemctl list-timers wordpress-backup.timer

# View recent logs
journalctl -u wordpress-backup.service -n 50
```

## Backup Contents

Each backup archive (`wp-backup-YYYYMMDD-HHMMSS.tar.zst`) contains:

1. **database.sql** - Full MariaDB dump with DROP TABLE statements
2. **wp-config.php** - WordPress configuration file
3. **wp-content.tar** - Tarball of the wp-content directory (themes, plugins, uploads)

## Restore Procedure

```bash
# 1. Download backup from Mega.nz or use local copy

# 2. Extract archive
mkdir restore && cd restore
zstd -d wp-backup-YYYYMMDD-HHMMSS.tar.zst
tar -xf wp-backup-YYYYMMDD-HHMMSS.tar

# 3. Restore database
mysql -u your_user -p your_database < database.sql

# 4. Restore wp-config.php
cp wp-config.php /var/www/zimpricecheck.com/

# 5. Restore wp-content
cd /var/www/zimpricecheck.com/htdocs
tar -xf /path/to/restore/wp-content.tar
chown -R www-data:www-data wp-content
```

## Email Notifications

- **Daily Report**: Sent at 08:00 AM (Africa/Harare) with summary of all backups
- **Failure Alert**: Sent immediately when a backup fails

The daily report includes:
- Archive filenames
- File sizes (human-readable)
- Mega account used for each backup
- Activity log

## Troubleshooting

### Check Logs

```bash
# Systemd service logs
journalctl -u wordpress-backup.service -f

# SQLite database
sqlite3 /opt/wordpress-backup/backups.db "SELECT * FROM backup_log ORDER BY timestamp DESC LIMIT 20;"
```

### Common Issues

1. **Permission Denied**: Ensure the script runs as `ubuntu` user with access to WordPress files
2. **mysqldump Failed**: Check MariaDB credentials in `.env` or ensure wp-config.php is readable
3. **Mega Upload Failed**: Verify Mega credentials and account storage space
4. **wp-content Too Large**: Consider excluding cache directories

### Verify Mega Storage

```python
# Check Mega account usage
from mega import Mega
m = Mega().login("email", "password")
space = m.get_storage_space()
print(f"Used: {space['used'] / 1024**3:.2f} GB")
print(f"Total: {space['total'] / 1024**3:.2f} GB")
```

## File Structure

```
/opt/wordpress-backup/
├── backup_manager.py      # Main backup script
├── configure.py           # Configuration wizard
├── report_manager.py      # Daily report generator
├── run.sh                 # Convenience runner
├── deploy.sh              # Deployment script
├── requirements.txt       # Python dependencies
├── .env                   # Configuration (not in git)
├── backups.db             # SQLite tracking database
├── backups/               # Local backup storage
└── venv/                  # Python virtual environment
```

## License

MIT License - forked from mongo-sync-backup
