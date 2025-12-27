# Sites API

Site management, quota control, and backup operations.

## Endpoints Overview

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/sites/` | List sites | All Users |
| GET | `/sites/{id}` | Get site details | All Users |
| POST | `/sites/` | Create site | Node Admin+ |
| PUT | `/sites/{id}` | Update site | Node Admin+ |
| DELETE | `/sites/{id}` | Delete site | Super Admin |
| PUT | `/sites/{id}/quota` | Update quota | Node Admin+ |
| GET | `/sites/{id}/quota/status` | Quota status | All Users |
| GET | `/sites/{id}/quota/check` | Pre-backup check | All Users |
| POST | `/sites/{id}/backup/start` | Start backup | Node Admin+ |

---

## GET /sites/{id}/quota/status

Get comprehensive quota status for a site. Used by frontend for quota displays.

### Request

```bash
curl -X GET "https://api.example.com/api/v1/sites/1/quota/status" \
  -H "Authorization: Bearer <token>"
```

### Response

```json
{
  "site_id": 1,
  "site_name": "example.com",
  "used_bytes": 3612358215,
  "used_gb": 3.36,
  "quota_gb": 15,
  "usage_percent": 22.4,
  "is_over_quota": false,
  "quota_exceeded_at": null,
  "pending_deletion": null,
  "node_id": 1,
  "node_quota_gb": 100,
  "node_used_gb": 3.36,
  "node_usage_percent": 3.4,
  "can_backup": true,
  "estimated_next_backup_gb": 3.36
}
```

### Response with Pending Deletion

```json
{
  "site_id": 1,
  "is_over_quota": true,
  "quota_exceeded_at": "2025-12-25T10:00:00",
  "pending_deletion": {
    "backup_id": 42,
    "filename": "backup_2025-12-20.tar.gz",
    "scheduled_for": "2025-12-28T10:00:00"
  },
  "can_backup": false
}
```

---

## GET /sites/{id}/quota/check

Pre-flight quota check before starting a backup. Returns whether backup can proceed.

### Request

```bash
curl -X GET "https://api.example.com/api/v1/sites/1/quota/check" \
  -H "Authorization: Bearer <token>"
```

### Response (Can Proceed)

```json
{
  "site_id": 1,
  "can_proceed": true,
  "current_used_gb": 3.36,
  "quota_gb": 15,
  "estimated_backup_gb": 3.36,
  "projected_used_gb": 6.73,
  "would_exceed_site_quota": false,
  "would_exceed_node_quota": false,
  "warning": null
}
```

### Response (Would Exceed)

```json
{
  "site_id": 1,
  "can_proceed": false,
  "current_used_gb": 13.5,
  "quota_gb": 15,
  "estimated_backup_gb": 3.5,
  "projected_used_gb": 17.0,
  "would_exceed_site_quota": true,
  "would_exceed_node_quota": false,
  "warning": "Backup would exceed quota"
}
```

---

## PUT /sites/{id}/quota

Update site storage quota. Validates against node limits.

### Request

```bash
curl -X PUT "https://api.example.com/api/v1/sites/1/quota?quota_gb=20" \
  -H "Authorization: Bearer <token>"
```

### Response (Success)

```json
{
  "success": true,
  "message": "Quota updated from 15 GB to 20 GB",
  "site_id": 1,
  "old_quota_gb": 15,
  "new_quota_gb": 20,
  "remaining_node_quota_gb": 80
}
```

### Response (Validation Error)

```json
{
  "detail": {
    "message": "Site quota (50 GB) cannot exceed node quota (100 GB)",
    "max_allowed_gb": 100
  }
}
```

---

## GET /sites/

List all sites with pagination.

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | int | 0 | Offset |
| `limit` | int | 100 | Max results |
| `node_id` | int | null | Filter by node |

### Response

```json
{
  "sites": [
    {
      "id": 1,
      "uuid": "a840cad8-9322-4ed1-a2ea-f65b1b14afa7",
      "name": "example.com",
      "wp_path": "/var/www/example.com",
      "db_name": "wp_example",
      "node_id": 1,
      "node_uuid": "3d298266-633b-48b6-9662-07a1d9ee1c44",
      "status": "active",
      "storage_used_bytes": 3612358215,
      "storage_quota_gb": 15,
      "storage_used_gb": 3.36,
      "last_backup": "2025-12-27T08:00:00"
    }
  ],
  "total": 1
}
```

---

## POST /sites/{id}/backup/start

Start a manual backup for a site.

### Request

```bash
curl -X POST "https://api.example.com/api/v1/sites/1/backup/start" \
  -H "Authorization: Bearer <token>"
```

### Response

```json
{
  "success": true,
  "message": "Backup started for site 'example.com'",
  "site_id": 1,
  "backup_status": "running"
}
```
