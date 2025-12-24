# WordPress Backup System

Automated backup solution for WordPress sites including database, wp-config.php, and wp-content. Backups are uploaded to Mega.nz for offsite storage and logs are synchronized with Cloudflare D1 for unified tracking.

## Features

- **Complete WordPress Backup**: Backs up database, wp-config.php, and wp-content.
- **MariaDB Support**: Uses `mysqldump` with `--add-drop-table` for clean restores.
- **Multi-Mega Storage**: Supports up to 3 Mega.nz accounts (each 19.5 GB usable).
- **Smart Rotation**: Automatically deletes oldest archives across all accounts when full.
- **Organized Storage**: Archives are stored in `Year/Month` folders (e.g., `2024/12/`).
- **Cloudflare D1 Integration**: Synchronizes backup logs and email records with a remote Cloudflare D1 database.
  - **Optimized for Free Tier**: Uses ruthless batching strategies to minimize parameters and queries, staying well within Cloudflare's free limits (max 100 parameters per query).
- **Configurable Schedule**: Daily at midnight (Africa/Harare) by default, fully configurable.
- **Daily Reports**: Email summary with file sizes and storage account info.
- **Background Execution**: Runs in background by default with status tracking.

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

1. **Clone this repository locally:**
   ```bash
   git clone <repo-url>
   cd wordpress-backup
   ```

2. **Run the configuration wizard:**
   ```bash
   ./configure.sh
   # Follow the prompts to configure Mega, SMTP, Database, and Cloudflare D1
   ```
   
   You can also configure specific sections:
   ```bash
   ./configure.sh --cloudflare  # Configure only D1 settings
   ./configure.sh --email       # Configure only Email
   ```

3. **Deploy to remote server:**
   ```bash
   ./deploy.sh
   ```

The deploy script will:
- Bundle your code and **local .env configuration** (so you don't need to reconfigure on the server).
- Upload to `ubuntu@wp.zimpricecheck.com:2200`.
- Install to `/opt/wordpress-backup`.
- Generate systemd unit files on the remote server with correct paths.
- **Automatically trigger a D1 sync** to pull any missing local data from the cloud.

### Manual Installation (Remote)

If you prefer to install manually:

```bash
# On remote server
sudo mkdir -p /opt/wordpress-backup
cd /opt/wordpress-backup

# Copy files here (use rsync or scp)
# ...

# Run setup
./configure.sh --systemd  # Generates service files in ./systemd/ directory

# Install systemd services
sudo cp systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wordpress-backup.timer
sudo systemctl enable --now wordpress-report.timer
```

## Configuration Setup

The configuration is stored in `.env`. You can manage it via the wizard:

```bash
./configure.sh [options]
```

Options:
- `--paths`: WordPress paths
- `--db`: Database credentials
- `--mega`: Mega.nz accounts
- `--email`: SMTP settings
- `--backup`: Scheduling & Retention
- `--cloudflare`: Cloudflare D1 Account ID, Token, DB ID
- `--systemd`: **Generate systemd service files** (This is usually done on the server side)

## Usage

### Automatic Backups

Backups run automatically based on the configured schedule (default: Daily at midnight, Africa/Harare).

### Manual Backup

Run manually in the background (default):

```bash
cd /opt/wordpress-backup
sudo ./run.sh
```

Run in foreground (for debugging):

```bash
sudo ./run.sh -f
```

### Manual Cloudflare D1 Sync

If you need to manually force a synchronization between your local SQLite database and Cloudflare D1:

```bash
sudo ./run.sh --db-sync
```

This will:
1. Push new local records to Cloudflare (using batched inserts).
2. Pull missing records from Cloudflare to local (using batched selects).

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

## Cloudflare D1 Structure

The system synchronizes three tables with Cloudflare D1:

1. **backup_log**: History of all backup jobs (success/failure).
2. **mega_archives**: Metadata of files uploaded to Mega.nz.
3. **daily_emails**: Tracking of sent daily reports.

**Optimized Sync Strategy:**
To stay within Cloudflare's free tier limits, the sync engine uses:
- **Batching**: Inserts and Selects are grouped. 
- **Parameter Check**: Ensures < 100 parameters per SQL query.
- **Efficient Pulls**: Checks remote IDs first, then pulls only what is missing.

## File Structure

```
/opt/wordpress-backup/
├── configure.sh           # Main configuration wrapper
├── deploy.sh              # Deployment script
├── run.sh                 # Runtime wrapper
├── requirements.txt       # Python dependencies
├── .env                   # Configuration file (secrets)
├── backups.db             # Local SQLite database
├── lib/                   # Python application code
│   ├── backup_manager.py  # Core backup logic
│   ├── configure.py       # Config wizard implementation
│   ├── d1_manager.py      # Cloudflare D1 sync engine (Batched)
│   └── report_manager.py  # Daily reporter
├── systemd/               # Systemd unit files (generated)
│   ├── wordpress-backup.service
│   ├── wordpress-backup.timer
│   ├── wordpress-report.service
│   └── wordpress-report.timer
├── backups/               # Local backup storage (archives)
└── venv/                  # Python virtual environment
```

## License

MIT License - based on custom deployment requirements.
