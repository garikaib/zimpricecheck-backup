# Backups API

Backup management, downloads, and scheduled deletions.

## Endpoints Overview

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/backups/sites/{site_id}/backups` | List site backups | Node Admin+ |
| GET | `/backups/backups/{id}` | Get backup details | Node Admin+ |
| DELETE | `/backups/backups/{id}` | Delete backup | Super Admin |
| GET | `/backups/backups/{id}/download` | Get download URL | Node Admin+ |
| GET | `/backups/scheduled-deletions` | List scheduled | Node Admin+ |
| DELETE | `/backups/backups/{id}/cancel-deletion` | Cancel deletion | Node Admin+ |

---

## GET /backups/scheduled-deletions

List all backups scheduled for automatic deletion. Used by dashboard for warnings.

### Request

```bash
curl -X GET "https://api.example.com/api/v1/backups/scheduled-deletions" \
  -H "Authorization: Bearer <token>"
```

### Response

```json
{
  "count": 2,
  "backups": [
    {
      "backup_id": 42,
      "filename": "backup_2025-12-20_120000.tar.gz",
      "size_gb": 3.36,
      "site_id": 1,
      "site_name": "example.com",
      "scheduled_deletion": "2025-12-28T10:00:00",
      "days_remaining": 1,
      "created_at": "2025-12-20T12:00:00"
    },
    {
      "backup_id": 38,
      "filename": "backup_2025-12-18_080000.tar.gz",
      "size_gb": 3.32,
      "site_id": 2,
      "site_name": "other-site.com",
      "scheduled_deletion": "2025-12-29T08:00:00",
      "days_remaining": 2,
      "created_at": "2025-12-18T08:00:00"
    }
  ]
}
```

---

## DELETE /backups/backups/{id}/cancel-deletion

Cancel a scheduled deletion for a backup.

### Request

```bash
curl -X DELETE "https://api.example.com/api/v1/backups/backups/42/cancel-deletion" \
  -H "Authorization: Bearer <token>"
```

### Response

```json
{
  "success": true,
  "message": "Cancelled scheduled deletion for backup_2025-12-20.tar.gz",
  "backup_id": 42,
  "was_scheduled_for": "2025-12-28T10:00:00"
}
```

---

## DELETE /backups/backups/{id}

Delete a backup. By default also deletes from S3.

### Request

```bash
curl -X DELETE "https://api.example.com/api/v1/backups/backups/42?delete_remote=true" \
  -H "Authorization: Bearer <token>"
```

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `delete_remote` | bool | true | Also delete from S3 |

### Response

```json
{
  "success": true,
  "message": "Backup 'backup_2025-12-20.tar.gz' for site 'example.com' deleted",
  "s3_deleted": true,
  "freed_bytes": 3612358215,
  "freed_gb": 3.36
}
```

---

## GET /backups/backups/{id}/download

Generate a presigned download URL for a backup.

### Request

```bash
curl -X GET "https://api.example.com/api/v1/backups/backups/42/download" \
  -H "Authorization: Bearer <token>"
```

### Response

```json
{
  "backup_id": 42,
  "filename": "backup_2025-12-20_120000.tar.gz",
  "download_url": "https://s3.example.com/backups/node-uuid/site-uuid/backup.tar.gz?X-Amz-...",
  "expires_in_seconds": 3600
}
```

---

## GET /backups/sites/{site_id}/backups

List all backups for a site.

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | int | 0 | Offset |
| `limit` | int | 50 | Max results |

### Response

```json
{
  "backups": [
    {
      "id": 42,
      "site_id": 1,
      "site_name": "example.com",
      "filename": "backup_2025-12-20_120000.tar.gz",
      "size_bytes": 3612358215,
      "size_gb": 3.36,
      "s3_path": "node-uuid/site-uuid/backup.tar.gz",
      "created_at": "2025-12-20T12:00:00",
      "backup_type": "full",
      "status": "SUCCESS",
      "storage_provider": "iDrive E2"
    }
  ],
  "total": 1
}
```
