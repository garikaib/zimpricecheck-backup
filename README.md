# WordPress Backup System (Multi-Site SaaS Edition)

Automated backup solution supporting **multiple WordPress sites**. Backups are uploaded to Mega.nz and logs synchronized with Cloudflare D1.

## Features

- **Multi-Site Support**: Back up unlimited WordPress sites from a single installation.
- **Centralized Management**: All sites configured in `sites.json`.
- **Configurable Deployment**: Deploy to any server using `.env` settings.
- **MariaDB Support**: Uses `mysqldump` with `--add-drop-table`.
- **Multi-Mega Storage**: Up to 3 Mega.nz accounts (each 19.5 GB usable).
- **Smart Rotation**: Automatically deletes oldest archives when accounts are full.
- **Cloudflare D1 Integration**: Syncs logs with D1 using batched queries (Free Tier optimized).
- **Daily Reports**: Email summary with backup details.

## Quick Start

### 1. Clone & Configure

```bash
git clone <repo-url>
cd wordpress-backup
./configure.sh
```

The interactive wizard will guide you through:
- **Managing Sites** (Add/Remove WordPress sites)
- **Global Credentials** (Mega, SMTP, Cloudflare D1)
- **Deployment Settings** (Remote server SSH details)
- **Backup Schedule & Retention**

### 2. Add WordPress Sites

Run `./configure.sh --sites` or select "Manage WordPress Sites" from the menu.

Each site requires:
- **Site Name**: Unique identifier (e.g., `zimpricecheck`)
- **wp-config.php path**: `/var/www/site.com/wp-config.php`
- **wp-content path**: `/var/www/site.com/htdocs/wp-content`
- **Database credentials** (optional - auto-extracted from wp-config)

Sites are stored in `sites.json`:
```json
{
  "sites": [
    {
      "name": "zimpricecheck",
      "wp_config_path": "/var/www/zimpricecheck.com/wp-config.php",
      "wp_content_path": "/var/www/zimpricecheck.com/htdocs/wp-content",
      "db_host": "",
      "db_name": "",
      "db_user": "",
      "db_password": ""
    }
  ]
}
```

### 3. Configure Deployment Target

Run `./configure.sh --deploy` to set:
- `REMOTE_HOST` - Server IP or domain
- `REMOTE_USER` - SSH user (default: `ubuntu`)
- `REMOTE_PORT` - SSH port (default: `22`)
- `REMOTE_DIR` - Installation path (default: `/opt/wordpress-backup`)

### 4. Deploy

```bash
./deploy.sh
```

This will:
- Bundle code and configuration
- Upload to your configured remote server
- Install dependencies and systemd services
- Trigger initial D1 sync

## Usage

### Run Backup (All Sites)

```bash
./run.sh           # Background mode
./run.sh -f        # Foreground mode
```

### Manual D1 Sync

```bash
./run.sh --db-sync
```

### Check Status

```bash
systemctl status wordpress-backup.timer
journalctl -u wordpress-backup.service -n 50
```

## Configuration Files

| File | Purpose |
|------|---------|
| `.env` | Global credentials (Mega, SMTP, D1, Deployment) |
| `sites.json` | WordPress site configurations |
| `backups.db` | Local SQLite tracking database |

## File Structure

```
/opt/wordpress-backup/
├── configure.sh           # Config wrapper
├── deploy.sh              # Deployment script (uses .env)
├── run.sh                 # Backup runner
├── .env                   # Global config (secrets)
├── sites.json             # Site definitions
├── lib/
│   ├── backup_manager.py  # Multi-site backup logic
│   ├── configure.py       # Interactive wizard
│   ├── d1_manager.py      # D1 sync (batched)
│   └── report_manager.py  # Email reports
├── systemd/               # Generated service files
└── backups/               # Local archive storage
```

## Database Schema

Tables include `site_name` column for multi-site tracking:

- **backup_log**: `id, timestamp, status, details, site_name`
- **mega_archives**: `id, filename, mega_account, file_size, upload_timestamp, site_name`
- **daily_emails**: `id, date, email_sent, backup_count`

## License

MIT License
