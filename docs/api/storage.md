# Storage API

Storage provider management, health monitoring, and reconciliation.

## Endpoints Overview

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/storage/summary` | Storage summary | Node Admin+ |
| GET | `/storage/health` | Health status | Node Admin+ |
| POST | `/storage/reconcile` | Sync with S3 | Super Admin |
| POST | `/storage/cleanup` | Manual cleanup | Super Admin |
| GET | `/storage/providers` | List providers | Super Admin |
| POST | `/storage/providers` | Create provider | Super Admin |
| PUT | `/storage/providers/{id}` | Update provider | Super Admin |
| DELETE | `/storage/providers/{id}` | Delete provider | Super Admin |
| POST | `/storage/providers/{id}/test` | Test connection | Super Admin |

---

## GET /storage/health

Get storage health status for dashboard displays. Returns over-quota sites, warnings, and pending deletions.

### Request

```bash
curl -X GET "https://api.example.com/api/v1/storage/health" \
  -H "Authorization: Bearer <token>"
```

### Response

```json
{
  "healthy": true,
  "total_sites": 5,
  "total_used_gb": 12.5,
  "over_quota_count": 0,
  "over_quota_sites": [],
  "warning_count": 1,
  "warning_sites": [
    {
      "site_id": 3,
      "site_name": "example.com",
      "usage_percent": 85.2
    }
  ],
  "scheduled_deletions": 0,
  "provider": {
    "name": "iDrive E2",
    "bucket": "backups",
    "is_active": true
  },
  "timestamp": "2025-12-27T10:42:21.511392"
}
```

---

## POST /storage/reconcile

Sync database storage tracking with actual S3 usage. Corrects drift between DB records and real storage.

### Request

```bash
curl -X POST "https://api.example.com/api/v1/storage/reconcile?dry_run=false" \
  -H "Authorization: Bearer <token>"
```

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dry_run` | bool | false | If true, only reports without fixing |

### Response

```json
{
  "success": true,
  "dry_run": false,
  "timestamp": "2025-12-27T10:45:00.000000",
  "duration_seconds": 2.5,
  "sites_checked": 5,
  "nodes_checked": 1,
  "sites_with_drift": 1,
  "total_drift_bytes": 1048576,
  "total_drift_gb": 0.01,
  "errors": 0,
  "sites": [
    {
      "site_id": 1,
      "site_name": "example.com",
      "db_bytes": 3612358215,
      "actual_bytes": 3612358215,
      "drift_bytes": 0,
      "has_drift": false
    }
  ],
  "nodes": [
    {
      "node_id": 1,
      "hostname": "node1.example.com",
      "has_drift": false
    }
  ]
}
```

---

## POST /storage/cleanup

Manually trigger cleanup of backups past their scheduled deletion date.

### Request

```bash
curl -X POST "https://api.example.com/api/v1/storage/cleanup" \
  -H "Authorization: Bearer <token>"
```

### Response

```json
{
  "deleted_count": 2,
  "freed_bytes": 7340032000,
  "freed_gb": 6.84,
  "errors": [],
  "timestamp": "2025-12-27T10:50:00.000000"
}
```

---

## GET /storage/summary

Get overall storage summary with per-node breakdown.

### Response

```json
{
  "total_quota_gb": 100,
  "total_used_gb": 12.5,
  "total_available_gb": 87.5,
  "usage_percentage": 12.5,
  "nodes_count": 1,
  "nodes_summary": [
    {
      "node_id": 1,
      "hostname": "node1.example.com",
      "quota_gb": 100,
      "used_gb": 12.5,
      "available_gb": 87.5,
      "usage_percentage": 12.5,
      "status": "active"
    }
  ],
  "storage_providers": [
    {
      "id": 1,
      "name": "iDrive E2",
      "type": "s3",
      "bucket": "backups",
      "is_default": true,
      "storage_limit_gb": 100,
      "used_gb": 12.5
    }
  ]
}
```
