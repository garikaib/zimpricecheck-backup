# Architecture

## File Structure

```
/opt/wordpress-backup/
├── configure.sh           # Config wrapper script
├── deploy.sh              # Deployment script
├── run.sh                 # Backup execution script
├── requirements.txt       # Python dependencies

├── .env                   # Global configuration (secrets)
├── .env.sample            # Template for .env
├── sites.json             # Site definitions (secrets)
├── sites.json.sample      # Template for sites.json
├── backups.db             # Local SQLite database

├── lib/                   # Python application code
│   ├── backup_manager.py  # Multi-site backup orchestration
│   ├── configure.py       # Interactive configuration wizard
│   ├── d1_manager.py      # Cloudflare D1 sync engine
│   ├── s3_manager.py      # S3-compatible storage manager
│   ├── report_manager.py  # Daily email report generator
│   └── migrate_legacy.py  # Legacy migration utilities

├── systemd/               # Generated systemd unit files
│   ├── wordpress-backup.service
│   ├── wordpress-backup.timer
│   ├── wordpress-report.service
│   └── wordpress-report.timer

├── backups/               # Local backup archive storage
│   └── {site}-backup-{timestamp}.tar.zst

├── venv/                  # Python virtual environment

└── docs/                  # Documentation
    ├── installation.md
    ├── configuration.md
    ├── sites.md
    ├── deployment.md
    ├── backup.md
    ├── cloudflare-d1.md
    ├── s3-storage.md
    ├── architecture.md
    └── troubleshooting.md
```

## Configuration Files

| File | Purpose | In Git? |
|------|---------|---------|
| `.env` | Credentials and global settings | No |
| `.env.sample` | Template showing all options | Yes |
| `sites.json` | WordPress site configurations | No |
| `sites.json.sample` | Template for sites | Yes |
| `backups.db` | SQLite tracking database | No |

## Database Schema

### Local SQLite (`backups.db`)

#### `backup_log`
Tracks all backup operations.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `timestamp` | DATETIME | When backup occurred |
| `status` | TEXT | START, INFO, SUCCESS, ERROR, FATAL |
| `details` | TEXT | Message |
| `site_name` | TEXT | Which site (multi-site support) |
| `server_id` | TEXT | Which server instance |

#### `s3_archives`
Tracks files uploaded to S3-compatible storage.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `filename` | TEXT | Remote path (SERVER_ID/Year/Month/Day/file.tar.zst) |
| `s3_endpoint` | TEXT | Which S3 endpoint |
| `s3_bucket` | TEXT | Which S3 bucket |
| `file_size` | INTEGER | Size in bytes |
| `upload_timestamp` | DATETIME | When uploaded |
| `site_name` | TEXT | Which site |
| `server_id` | TEXT | Which server instance |

#### `daily_emails`
Tracks daily report emails.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `date` | TEXT | Date (YYYY-MM-DD) |
| `email_sent` | INTEGER | 0 or 1 |
| `backup_count` | INTEGER | Backups that day |

## Data Flow

```
┌─────────────────┐
│   sites.json    │ ←── Site definitions
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│ backup_manager  │────▶│   mysqldump  │ ── database.sql
│     .py         │     └──────────────┘
└────────┬────────┘
         │              ┌──────────────┐
         ├─────────────▶│     tar      │ ── wp-content.tar
         │              └──────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│      zstd       │────▶│  .tar.zst    │
└────────┬────────┘     └──────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│   s3_manager    │────▶│ S3 Storage   │
│   (boto3)       │     │ (iDrive E2)  │
└────────┬────────┘     └──────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│   backups.db    │────▶│ Cloudflare   │
│   (SQLite)      │     │     D1       │
└─────────────────┘     └──────────────┘
```

## Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| `run.sh` | Entry point, arg parsing, venv activation |
| `configure.sh` | Wrapper for lib/configure.py |
| `deploy.sh` | Bundle, upload, remote setup, log reset |
| `backup_manager.py` | Orchestrates multi-site backups |
| `s3_manager.py` | Uploads to S3-compatible storage |
| `d1_manager.py` | Bidirectional D1 sync with batching |
| `configure.py` | Interactive wizard, file management |
| `report_manager.py` | Generates daily email summaries |
