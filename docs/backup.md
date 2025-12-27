# Backup Flow & Operations

Automated backup operations are handled by the **Backup Daemon** (`backupd`).

## How it Works

1.  **Schedule**: The daemon wakes up according to its internal scheduler (or systemd timer).
2.  **Job Creation**: A backup "Job" is instantiated for each active site.
3.  **Quota Check**:
    - The daemon queries the Master API (`GET /sites/{id}/quota/check`).
    - If `can_proceed` is `false`, the backup is aborted (SKIPPED).
4.  **Execution**:
    - **Database**: `mysqldump` -> `.sql`
    - **Files**: `tar` of `wp-content` (excluding cache/node_modules) -> `.tar`
    - **Config**: `wp-config.php` copied.
5.  **Compression**: All artifacts combined into a single Zstandard archive (`.tar.zst`).
6.  **Upload**:
    - Daemon fetches encrypted storage credentials from Master (`GET /nodes/config`).
    - Decrypts credentials in memory.
    - Uploads directly to S3 (no relay through Master) to path `/{node_uuid}/{site_uuid}/{filename}`.
7.  **Reporting**:
    - On success: Sends `POST /backups/` to Master with metadata (`size_bytes`, `s3_path`).
    - On failure: Sends error status.
8.  **Cleanup**: Local temporary files are deleted.

## Manually Triggering Backups

### Via API (Dashboard)

**Preferred Method**

```bash
POST /api/v1/sites/{id}/backup/start
```

This queues a job on the node (via WebSocket/Command channel, pending implementation of realtime push) or via polling. *Currently, daemon polls for jobs or runs on schedule.*

### Via CLI (On Node)

You can manually trigger the daemon logic for debugging.

```bash
# SSH into Node
ssh ubuntu@node-ip

# Navigate to dir
cd /opt/wordpress-backup

# Run specific module
sudo ./venv/bin/python3 -m daemon.main --run-once
```

## Archive Format

Filename: `{site_name}_{YYYYMMDD}_{HHMMSS}.tar.zst`

Contents:
```
.
├── database.sql       # Full SQL Dump
├── wp-config.php      # Auth keys and DB config
└── wp-content/        # Themes, Plugins, Uploads
```

## Restore Procedure

1.  **Download**: Get Presigned URL from Dashboard (`GET /backups/{id}/download`).
2.  **Download to Server**: `wget -O backup.tar.zst "<presigned_url>"`
3.  **Extract**:
    ```bash
    zstd -d backup.tar.zst
    tar -xf backup.tar
    ```
4.  **Import DB**: `mysql -u user -p dbname < database.sql`
5.  **Restore Files**: `rsync -av wp-content/ /var/www/site/wp-content/`
