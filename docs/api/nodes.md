# Nodes API

Node management, registration, and quota status.

## Endpoints Overview

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/nodes/join-request` | Node requests to join cluster | **Public** |
| GET | `/nodes/status/code/{code}` | Node polls for approval status | **Public** |
| POST | `/nodes/approve/{id}` | Approve pending node | Super Admin |
| POST | `/nodes/register-by-code` | Approve node by entering code | Super Admin |
| GET | `/nodes/` | List all nodes (includes pending) | All Users |
| GET | `/nodes/{id}` | Get node details | Node Admin+ |
| PUT | `/nodes/{id}/quota` | Update quota | Super Admin |
| GET | `/nodes/{id}/quota/status` | Quota status | Node Admin+ |
| GET | `/nodes/{id}/sites` | List node sites | Node Admin+ |
| GET | `/nodes/{id}/backups` | List node backups | Node Admin+ |
| **SSE** | `/metrics/nodes/stats/stream` | Real-time stats for ALL nodes | Node Admin+ |
| **SSE** | `/metrics/nodes/{id}/stats/stream` | Real-time stats for single node | Node Admin+ |

---

## Node Registration Flow

### 1. POST /nodes/join-request

Node calls this on startup to register with the cluster. No authentication required.

**Request:**
```json
{
  "hostname": "api.example.com",
  "ip_address": "192.168.1.100",
  "system_info": "Ubuntu 22.04"
}
```

**Response:**
```json
{
  "request_id": "42",
  "registration_code": "XK7M2",
  "message": "Join request submitted. Give code XK7M2 to admin."
}
```

### 2. GET /nodes/status/code/{code}

Node polls this endpoint to check if approved.

**Response (Pending):**
```json
{
  "status": "pending",
  "api_key": null
}
```

**Response (Approved):**
```json
{
  "status": "active",
  "api_key": "eyJ0eXAiOiJKV1Q..."
}
```

> **Note:** The registration code is cleared after the API key is retrieved.

### 3. POST /nodes/approve/{id}

Admin approves a pending node by ID.

**Response:** `NodeResponse` with status `active`.

---

## SSE /metrics/nodes/stats/stream (Unified Stats Stream)

Stream real-time metrics for **ALL nodes** in a single unified format.

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | string | required | JWT token for authentication |
| `interval` | int | 5 | Update interval in seconds (1-60) |

### Usage

```javascript
const token = 'your-jwt-token';
const source = new EventSource(`/api/v1/metrics/nodes/stats/stream?token=${token}&interval=5`);

source.onmessage = (event) => {
  const data = JSON.parse(event.data);
  data.nodes.forEach(node => {
    console.log(`${node.hostname}: CPU ${node.cpu_percent}%, Disk ${node.disk_percent}%`);
  });
};
```

### Response (SSE Event)

```json
{
  "timestamp": "2025-12-29T07:00:00Z",
  "nodes": [
    {
      "id": 2,
      "hostname": "api.zimpricecheck.com",
      "status": "online",
      "is_master": false,
      "cpu_percent": 12,
      "memory_percent": null,
      "disk_percent": 51,
      "uptime_seconds": null,
      "active_backups": 0,
      "last_seen": "2025-12-29T06:59:30Z"
    },
    {
      "id": 3,
      "hostname": "wp.zimpricecheck.com",
      "status": "online",
      "is_master": true,
      "cpu_percent": 5.0,
      "memory_percent": 72.8,
      "disk_percent": 51.5,
      "uptime_seconds": 447000,
      "active_backups": 1,
      "last_seen": null
    }
  ]
}
```

### Node Status Values

| Status | Description |
|--------|-------------|
| `online` | Node is reporting stats actively |
| `stale` | Node hasn't reported in >5 minutes |
| `offline` | No stats ever received |

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

## GET /nodes/
List all nodes.

### Response
```json
[
  {
    "id": 1,
    "hostname": "wp.zimpricecheck.com",
    "status": "active",
    "storage_quota_gb": 100,
    "stats": [
        {
            "cpu_usage": 15,
            "disk_usage": 45,
            "active_backups": 0
        }
    ]
  }
]
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
  "backups_count": 15,
  "stats": [
    {
      "cpu_usage": 12,
      "disk_usage": 42,
      "active_backups": 1
    }
  ]
}
```

---

## GET /nodes/{id}/backups

List backups for a node.

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | int | 0 | Offset |
| `limit` | int | 50 | Max results |
| `site_id` | int | null | Filter by site |

### Response

```json
{
  "backups": [
    {
      "id": 1,
      "site_id": 1,
      "site_name": "example.com",
      "filename": "example.com_20251227_082133.tar.zst",
      "size_bytes": 3612358215,
      "size_gb": 3.36,
      "s3_path": "s3://bucket/example.com_20251227_082133.tar.zst",
      "created_at": "2025-12-27T08:22:04.588990",
      "backup_type": "full",
      "status": "SUCCESS",
      "storage_provider": "iDrive E2 Shared"
    }
  ],
  "total": 1
}
```
