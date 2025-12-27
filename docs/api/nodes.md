# Nodes API

Node management and quota status.

## Endpoints Overview

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/nodes/` | List nodes | All Users |
| GET | `/nodes/{id}` | Get node details | Node Admin+ |
| PUT | `/nodes/{id}/quota` | Update quota | Super Admin |
| GET | `/nodes/{id}/quota/status` | Quota status | Node Admin+ |
| GET | `/nodes/{id}/sites` | List node sites | Node Admin+ |
| GET | `/nodes/{id}/backups` | List node backups | Node Admin+ |
| POST | `/nodes/join-request` | Request join | Public |
| POST | `/nodes/approve/{id}` | Approve node | Super Admin |

---

## GET /nodes/{id}/quota/status

Get comprehensive quota status with site breakdown.

### Request

```bash
curl -X GET "https://api.example.com/api/v1/nodes/1/quota/status" \
  -H "Authorization: Bearer <token>"
```

### Response

```json
{
  "node_id": 1,
  "hostname": "wp.zimpricecheck.com",
  "used_gb": 12.5,
  "quota_gb": 100,
  "usage_percent": 12.5,
  "is_over_quota": false,
  "sites_count": 3,
  "sites_over_quota": 0,
  "sites_warning": 1,
  "sites_breakdown": [
    {
      "site_id": 1,
      "site_name": "example.com",
      "used_gb": 5.2,
      "quota_gb": 15,
      "usage_percent": 34.7,
      "is_over_quota": false
    },
    {
      "site_id": 2,
      "site_name": "blog.example.com",
      "used_gb": 4.1,
      "quota_gb": 10,
      "usage_percent": 41.0,
      "is_over_quota": false
    },
    {
      "site_id": 3,
      "site_name": "shop.example.com",
      "used_gb": 3.2,
      "quota_gb": 4,
      "usage_percent": 80.0,
      "is_over_quota": false
    }
  ]
}
```

---

## PUT /nodes/{id}/quota

Update node storage quota (Super Admin only).

### Request

```bash
curl -X PUT "https://api.example.com/api/v1/nodes/1/quota" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"storage_quota_gb": 200}'
```

### Response

```json
{
  "id": 1,
  "hostname": "wp.zimpricecheck.com",
  "uuid": "3d298266-633b-48b6-9662-07a1d9ee1c44",
  "status": "active",
  "storage_quota_gb": 200,
  "storage_used_bytes": 0
}
```

---

## GET /nodes/{id}

Get node details with stats.

### Response

```json
{
  "id": 1,
  "hostname": "wp.zimpricecheck.com",
  "ip_address": "127.0.0.1",
  "status": "active",
  "storage_quota_gb": 100,
  "total_available_gb": 500,
  "storage_used_gb": 12.5,
  "sites_count": 3,
  "backups_count": 15
}
```
