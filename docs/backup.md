# Backup Flow & Operations

The backup system executes real WordPress backups with database dumps, file compression, and S3 upload.

## Stage-Based Backup Flow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  backup_db   │ -> │ backup_files │ -> │ create_bundle│ -> │upload_remote │ -> │   cleanup    │
│  (mysqldump) │    │ (wp-content) │    │  (tar.zst)   │    │    (S3)      │    │ (temp files) │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

### Stage Details

| Stage | Description | Output |
|-------|-------------|--------|
| `backup_db` | MySQL dump with `--single-transaction` | `database.sql` (e.g., 126 MB) |
| `backup_files` | Copy `wp-content` (excludes cache, wflogs) | `wp-content/` folder |
| `create_bundle` | Compress with zstd multi-threaded | `site_YYYYMMDD_HHMMSS.tar.zst` |
| `upload_remote` | Upload to S3 using presigned credentials | S3 path with UUIDs |
| `cleanup` | Remove temp directory | Disk space freed |

---

## Starting a Backup

### Via API (Recommended)
```bash
POST /api/v1/sites/{id}/backup/start
Authorization: Bearer <token>
```

### Via Shell Script
```bash
cd /path/to/wordpress-backup/scripts
./start_backup.sh <site_id>
./monitor_backup.sh <site_id>  # Watch progress
```

---

## Progress Tracking

Progress is stored in the database and available via:

```bash
GET /api/v1/sites/{id}/backup/status
```

**Response includes:**
- `status`: idle, running, completed, failed, stopped
- `progress`: 0-100%
- `stage`: Current stage name
- `stage_detail`: Detailed message (e.g., "Database dumped (126.4 MB)")
- `error`: Error message if failed

---

## S3 Storage Path Structure

Backups are stored using UUID-based paths for security:

```
s3://<bucket>/<node_uuid>/<site_uuid>/<filename>
```

Example:
```
s3://backups/3d298266-633b-48b6-9662-07a1d9ee1c44/a840cad8-9322-4ed1-a2ea-f65b1b14afa7/zimpricecheck.com_20251228_075128.tar.zst
```

---

## Archive Format

Filename: `{site_name}_{YYYYMMDD}_{HHMMSS}.tar.zst`

Contents:
```
.
├── database.sql       # Full SQL Dump
└── wp-content/        # Themes, Plugins, Uploads
```

---

## Restore Procedure

1. **Get Download URL**: 
   ```bash
   GET /api/v1/backups/backups/{id}/download
   ```
   Returns presigned S3 URL (valid 1 hour).

2. **Download**:
   ```bash
   wget -O backup.tar.zst "<presigned_url>"
   ```

3. **Extract**:
   ```bash
   zstd -d backup.tar.zst
   tar -xf backup.tar
   ```

4. **Restore Database**:
   ```bash
   mysql -u user -p db_name < database.sql
   ```

5. **Restore Files**:
   ```bash
   rsync -av wp-content/ /var/www/site/wp-content/
   ```

---

## Error Handling

The backup system is resilient:
- **Stage failures**: Cleanup runs even on failure
- **User stops**: Cleanup runs before exit
- **Daemon crash**: Orphaned temp dirs cleaned on restart

### Resetting Stuck Backups
```bash
POST /api/v1/daemon/backup/reset/{site_id}
```
This resets status to `idle` and cleans up temp files.

---

## Quota Management

Before backup, the system can check quota:
```bash
GET /api/v1/sites/{id}/quota/check
```

Returns `can_proceed: true/false` based on projected usage.
