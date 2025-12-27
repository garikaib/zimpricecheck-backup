# SaaS Master API Reference

This document provides extensive documentation for the Master Server API, intended for building Admin Panels or integrating third-party tools.

## Base URL

| Environment | URL |
|-------------|-----|
| **Production** | `https://wp.zimpricecheck.com:8081/api/v1` |
| **Local Tunnel** | `http://localhost:8001/api/v1` (via `./deploy.sh master --test`) |

## CORS Configuration

The API supports Cross-Origin Resource Sharing (CORS) for frontend development.

**Allowed Origins:**
- `http://localhost:*` (any port)
- `https://zimpricecheck.com`
- `https://wp.zimpricecheck.com`

**Allowed Headers:**
- `Authorization`
- `Content-Type`
- `X-API-KEY`

**Credentials:** Enabled (`Access-Control-Allow-Credentials: true`)

---

## Authentication

The API uses **JWT Bearer Tokens** for Admin authentication and **API Keys** for Node authentication.

### 1. Admin Login (JWT)
**Endpoint**: `POST /auth/login`
**Content-Type**: `application/json`

**Body:**
```json
{
  "username": "admin@example.com",
  "password": "yourpassword"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer"
}
```

**Using the Token:**
Include the token in subsequent requests:
```
Authorization: Bearer <access_token>
```

> **Note:** Login will fail with `403 Forbidden` if the user's email is not verified.

### 2. Magic Link Login (Passwordless)

#### Request Magic Link
**Endpoint**: `POST /auth/magic-link`
**Content-Type**: `application/json`

**Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "If the email exists, a login link will be sent."
}
```

#### Login via Magic Link
**Endpoint**: `GET /auth/magic-link/{token}`
**Auth**: None (Public)

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer"
}
```

**Errors:**
- `400 Bad Request`: Invalid or expired token

### 3. Node Authentication
Nodes do not log in. They include their API Key in the header of every request.
*   **Header**: `X-API-KEY: <node_api_key>`

---

## Node Management Endpoints

### List All Nodes
**Endpoint**: `GET /nodes/`
**Auth**: Bearer Token (Super Admin)

**Response (200 OK):**
```json
[
  {
    "hostname": "client-vps-1",
    "ip_address": "1.2.3.4",
    "id": 1,
    "status": "active",
    "storage_quota_gb": 100
  },
  {
    "hostname": "client-vps-2",
    "ip_address": "5.6.7.8",
    "id": 2,
    "status": "pending",
    "storage_quota_gb": 100
  }
]
```

### Approve a Node
**Endpoint**: `POST /nodes/approve/{node_id}`
**Auth**: Bearer Token (Super Admin)

**Response (200 OK):**
```json
{
    "hostname": "client-vps-2",
    "id": 2,
    "status": "active",
    "api_key": "generated_secret_key...", 
    ...
}
```

### Get Node Status (Public Polling)
**Endpoint**: `GET /nodes/status/{request_id}`
**Auth**: None (Public)

**Response (200 OK):**
```json
{
  "status": "active",
  "api_key": "secret_key_returned_once" 
}
```

### Register Node by Code
**Endpoint**: `POST /nodes/register-by-code`
**Auth**: Bearer Token (Super Admin)
**Query Params**:
- `code` (string): 5-character registration code
- `ip_address` (string): Node's IP address

**Response:**
```json
{
  "id": 3,
  "hostname": "new-node",
  "status": "active",
  "ip_address": "1.2.3.4"
}
```

---

## User Management Endpoints

### Get Current User
**Endpoint**: `GET /users/me`
**Auth**: Bearer Token (Any authenticated user)

**Response (200 OK):**
```json
{
  "id": 1,
  "email": "admin@example.com",
  "full_name": "Admin User",
  "is_active": true,
  "role": "super_admin"
}
```

### List Users
**Endpoint**: `GET /users/`
**Auth**: Bearer Token (Node Admin+)
**Query Params**: `skip` (int), `limit` (int)

**Response (200 OK):**
```json
{
  "users": [
    {
      "id": 1,
      "email": "admin@example.com",
      "full_name": "Admin",
      "is_active": true,
      "role": "super_admin"
    }
  ],
  "total": 1
}
```

### Create User
**Endpoint**: `POST /users/`
**Auth**: Bearer Token (Super Admin only)

**Body:**
```json
{
  "email": "newuser@example.com",
  "password": "securepassword",
  "full_name": "New User",
  "role": "site_admin"
}
```

> **Note:** New users receive a verification email with a 6-character alphanumeric code. They must verify before logging in.

**Response includes:**
```json
{
  "id": 2,
  "email": "newuser@example.com",
  "is_verified": false,
  "pending_email": null
}
```

### Get User by ID
**Endpoint**: `GET /users/{user_id}`
**Auth**: Bearer Token (Node Admin+)

### Update User
**Endpoint**: `PUT /users/{user_id}`
**Auth**: Bearer Token (Node Admin+)

**Body:**
```json
{
  "full_name": "Updated Name",
  "is_active": false
}
```

### Delete User
**Endpoint**: `DELETE /users/{user_id}`
**Auth**: Bearer Token (Super Admin only)

> **Note:** Users cannot delete themselves.

### Update Own Profile
**Endpoint**: `PUT /users/me`
**Auth**: Bearer Token (Any authenticated)

Users can update their own profile (email, full_name, password) but cannot change their role.

### Verify Email
**Endpoint**: `POST /users/{user_id}/verify-email`
**Auth**: Bearer Token (Node Admin+)

**Body:**
```json
{
  "code": "A3X9K2"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Email verified successfully"
}
```

### Resend Verification
**Endpoint**: `POST /users/{user_id}/resend-verification`
**Auth**: Bearer Token (Node Admin+)

Generates a new code and sends it to the user's email.

### Force Verify (Super Admin)
**Endpoint**: `POST /users/{user_id}/force-verify`
**Auth**: Bearer Token (Super Admin only)

**Body:**
```json
{
  "code": "",
  "force_verify": true
}
```

> **Warning:** Super Admins cannot force-verify their own email changes.

---

## Node/Site Assignment Endpoints

Manage which nodes and sites users can access. Super Admin only.

### Get User's Nodes
**Endpoint**: `GET /users/{user_id}/nodes`
**Auth**: Bearer Token (Super Admin)

**Response:**
```json
[
  { "id": 1, "hostname": "node-1", "ip_address": "1.2.3.4", "status": "active" }
]
```

### Assign Nodes to User
**Endpoint**: `POST /users/{user_id}/nodes`
**Auth**: Bearer Token (Super Admin)

**Body:**
```json
{ "node_ids": [1, 3, 5] }
```

**Response:**
```json
{ "message": "Nodes assigned", "assigned": [1, 3, 5] }
```

### Remove Node from User
**Endpoint**: `DELETE /users/{user_id}/nodes/{node_id}`
**Auth**: Bearer Token (Super Admin)
**Response**: `204 No Content`

### Get User's Sites
**Endpoint**: `GET /users/{user_id}/sites`
**Auth**: Bearer Token (Super Admin)

### Assign Sites to User
**Endpoint**: `POST /users/{user_id}/sites`
**Auth**: Bearer Token (Super Admin)

**Body:**
```json
{ "site_ids": [1, 2] }
```

### Remove Site from User
**Endpoint**: `DELETE /users/{user_id}/sites/{site_id}`
**Auth**: Bearer Token (Super Admin)
**Response**: `204 No Content`

---

## Communication Channels Endpoints

Manage email, SMS, and other communication providers. Super Admin only.

### List Channels
**Endpoint**: `GET /communications/channels`
**Auth**: Bearer Token (Super Admin)

**Response:**
```json
{
  "channels": [
    {
      "id": 1,
      "name": "SendPulse API",
      "channel_type": "email",
      "provider": "sendpulse_api",
      "allowed_roles": ["verification", "notification", "alert", "login_link"],
      "is_default": true,
      "is_active": true,
      "priority": 1
    }
  ],
  "total": 1
}
```

### Create Channel
**Endpoint**: `POST /communications/channels`
**Auth**: Bearer Token (Super Admin)

**Body:**
```json
{
  "name": "Backup SMTP",
  "channel_type": "email",
  "provider": "smtp",
  "config": {
    "host": "smtp.example.com",
    "port": 587,
    "encryption": "tls",
    "username": "user@example.com",
    "password": "secret",
    "from_email": "noreply@example.com",
    "from_name": "My App"
  },
  "allowed_roles": ["verification", "notification"],
  "is_default": false,
  "priority": 10
}
```

### Update/Delete Channel
- `PUT /communications/channels/{id}` - Update
- `DELETE /communications/channels/{id}` - Delete

### Test Channel
**Endpoint**: `POST /communications/channels/{id}/test`
**Auth**: Bearer Token (Super Admin)

**Body:**
```json
{
  "to": "test@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Test message sent successfully",
  "provider": "SendPulse API"
}
```

### Available Providers

| Channel Type | Provider | Description |
|--------------|----------|-------------|
| `email` | `sendpulse_api` | SendPulse REST API (recommended) |
| `email` | `smtp` | Standard SMTP (fallback) |
| `sms` | (future) | Twilio, Nexmo |
| `whatsapp` | (future) | WhatsApp Business |
| `push` | (future) | Firebase Cloud Messaging |

### Message Roles

| Role | Description |
|------|-------------|
| `verification` | Email/phone verification codes |
| `notification` | General notifications |
| `alert` | Urgent alerts (backup failures) |
| `marketing` | Bulk promotional emails |
| `transactional` | Order confirmations, receipts |
| `login_link` | Magic login links |

---

## Activity Logs Endpoints

All actions are automatically logged with IP address (Cloudflare-aware), user agent, and timestamp. Keeps last 100 logs per user.

### Get My Logs
**Endpoint**: `GET /activity-logs/me`
**Auth**: Bearer Token (Any authenticated)

**Response:**
```json
{
  "logs": [
    {
      "id": 1,
      "user_id": 1,
      "user_email": "admin@example.com",
      "action": "login",
      "target_type": null,
      "target_id": null,
      "target_name": null,
      "details": "{\"role\": \"super_admin\"}",
      "ip_address": "104.28.219.41",
      "user_agent": "Mozilla/5.0 ...",
      "created_at": "2025-12-26T01:58:12"
    }
  ],
  "total": 1
}
```

### List All Logs
**Endpoint**: `GET /activity-logs/`
**Auth**: Bearer Token (Node Admin+)
**Query Params**: `user_id`, `action`, `skip`, `limit`

**Access Control:**
- **Super Admin**: All logs, all users
- **Node Admin**: Own logs + Site Admins on their nodes

### Get User's Logs
**Endpoint**: `GET /activity-logs/user/{user_id}`
**Auth**: Bearer Token (Node Admin+)

**Access Control:**
- **Super Admin**: Any user
- **Node Admin**: Site Admins on their nodes only

### Logged Actions
| Action | Description |
|--------|-------------|
| `login` | Successful login |
| `login_failed` | Failed login attempt |
| `user_create` | New user created |
| `user_update` | User updated |
| `user_delete` | User deleted |
| `profile_update` | User updated own profile |
| `node_approve` | Node approved |
| `node_quota_update` | Node quota changed |
| `backup_delete` | Backup deleted |

---

## Settings Endpoints

### List Settings
**Endpoint**: `GET /settings/`
**Auth**: Bearer Token (Super Admin only)

**Response:**
```json
{
  "settings": [
    {
      "key": "turnstile_secret",
      "value": "0x4AAA...",
      "description": "Cloudflare Turnstile Secret Key",
      "updated_at": "2025-12-26T05:00:00"
    }
  ]
}
```

### Get Setting
**Endpoint**: `GET /settings/{key}`
**Auth**: Bearer Token (Super Admin only)

### Update Setting
**Endpoint**: `PUT /settings/{key}`
**Auth**: Bearer Token (Super Admin only)

**Body:**
```json
{
  "value": "new_value",
  "description": "Optional description"
}
```

### Get Turnstile Site Key (Public)
**Endpoint**: `GET /settings/public/turnstile-site-key`
**Auth**: None (Public)

**Response:**
```json
{
  "site_key": "0x4AAAAAACJHWhQujsonWxQ-",
  "enabled": false
}
```

### Turnstile Settings
| Key | Description |
|-----|-------------|
| `turnstile_secret` | Cloudflare Turnstile Secret Key |
| `turnstile_site_key` | Cloudflare Turnstile Site Key |
| `turnstile_enabled` | `"true"` or `"false"` to enable/disable |

---

## Storage Management Endpoints

### Storage Summary
**Endpoint**: `GET /storage/summary`
**Auth**: Bearer Token (Node Admin+)

Returns aggregate storage across all nodes with per-node breakdown.

**Response:**
```json
{
  "total_quota_gb": 500,
  "total_used_gb": 312.5,
  "total_available_gb": 187.5,
  "usage_percentage": 62.5,
  "nodes_count": 5,
  "nodes_summary": [
    {
      "node_id": 1,
      "hostname": "backup-node-1",
      "quota_gb": 100,
      "used_gb": 75.2,
      "available_gb": 24.8,
      "usage_percentage": 75.2,
      "status": "active"
    }
  ],
  "storage_providers": [
    {
      "id": 1,
      "name": "S3 Prod",
      "type": "s3",
      "bucket": "backups-prod",
      "storage_limit_gb": 1000,
      "used_gb": 312.5,
      "is_default": true,
      "is_active": true
    }
  ]
}
```

### List Storage Providers
**Endpoint**: `GET /storage/providers`
**Auth**: Bearer Token (Super Admin)

### Add Storage Provider
**Endpoint**: `POST /storage/providers`
**Auth**: Bearer Token (Super Admin)

**Body:**
```json
{
  "name": "Primary S3",
  "type": "s3",
  "bucket": "backup-bucket",
  "region": "us-east-1",
  "endpoint": null,
  "access_key": "AKIAIOSFODNN7EXAMPLE",
  "secret_key": "wJalrXUtnFEMI/K7MDENG...",
  "is_default": true,
  "storage_limit_gb": 500
}
```

**Errors:**
- `400 Bad Request`: If provider name exists OR if configuration (type+bucket+endpoint) duplicates an existing provider.

### Update/Delete Provider
- `PUT /storage/providers/{id}` - Update provider
- `DELETE /storage/providers/{id}` - Delete provider (Super Admin)

### Test Connection
**Endpoint**: `POST /storage/providers/{id}/test`
**Auth**: Bearer Token (Super Admin)

**Response:**
```json
{
  "success": true,
  "message": "Connection successful",
  "available_space_gb": null
}
```

### Node Storage Config
**Endpoint**: `GET /nodes/storage-config`
**Auth**: X-API-KEY (Node)

Returns decrypted storage credentials for backup operations.

### Provider Types
| Type | Description |
|------|-------------|
| `s3` | AWS S3 or S3-compatible |
| `b2` | Backblaze B2 |
| `mega` | Mega.nz |
| `local` | Local filesystem |

---


## Jobs Management Endpoints

### List Available Modules
**Endpoint**: `GET /jobs/modules`
**Auth**: `Bearer Token` (Node Admin+)

**Response:**
```json
{
  "modules": ["wordpress", "mongodb"]
}
```

### List Jobs
**Endpoint**: `GET /jobs`
**Auth**: `Bearer Token` (Node Admin+)
**Query Params**:
- `status` (optional): `pending`, `running`, `completed`, `failed`
- `module` (optional): Filter by module name
- `limit` (default: 50)

**Response:**
```json
{
  "jobs": [
    {
      "id": "uuid-string",
      "module": "wordpress",
      "target_id": 1,
      "target_name": "My Site",
      "status": "completed",
      "priority": 0,
      "progress_percent": 100
    }
  ],
  "total": 1
}
```

### Create Job
**Endpoint**: `POST /jobs`
**Auth**: `Bearer Token` (Node Admin+)

**Body:**
```json
{
  "module": "wordpress",
  "target_id": 1,
  "target_name": "My Site",
  "priority": 5
}
```

### Get Job Details
**Endpoint**: `GET /jobs/{job_id}`
**Auth**: `Bearer Token` (Node Admin+)

### Cancel Job
**Endpoint**: `DELETE /jobs/{job_id}`
**Auth**: `Bearer Token` (Node Admin+)

---

## Statistics Endpoints

### Report Node Stats
**Endpoint**: `POST /stats/`
**Auth**: `X-API-KEY` (Node)

**Body:**
```json
{
  "cpu_usage": 45,       // Integer (0-100)
  "disk_usage": 60,      // Integer (0-100)
  "active_backups": 1    // Count of currently running jobs
}
```

**Response (200 OK):**
```json
{
  "status": "recorded",
  "node": "client-vps-1"
}
```

---

## Enumerations

### NodeStatus
*   `pending`: Initial state after Join Request.
*   `active`: Approved and functional.
*   `blocked`: Explicitly denied access.

### UserRole
*   `super_admin`: Full access to all users, nodes, and sites.
*   `node_admin`: Can manage nodes and Site Admins assigned to their nodes.
*   `site_admin`: Can only view own profile via `/users/me`.

---

## WordPress Site Detection

### Scan for Sites
**Endpoint**: `GET /daemon/scan`
**Auth**: Bearer Token (Super Admin)
**Query Params**: `base_path` (default: `/var/www`)

Scans for WordPress installations by looking for `wp-content/` and `wp-config.php`.

**Response:**
```json
{
  "success": true,
  "node_id": 1,
  "sites": [
    {
      "name": "example.com",
      "path": "/var/www/example.com",
      "has_wp_config": true,
      "has_wp_content": true,
      "db_name": "wp_example",
      "is_complete": true
    }
  ],
  "total": 1
}
```

### Manually Add Site
**Endpoint**: `POST /sites/manual`
**Auth**: Bearer Token (Super Admin only)

Manually add a site by providing its filesystem path. The system verifies the path contains a valid WordPress installation (`wp-content`) and extracts metadata (DB name, Site Name, URL) from `wp-config.php` and the database.

**Body:**
```json
{
  "path": "/var/www/my-site",
  "wp_config_path": "/var/www/wp-config.php",  // Optional
  "node_id": 1,                                // Optional (defaults to master)
  "name": "Custom Name"                        // Optional (auto-discovered if omitted)
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Site 'My Blog' added successfully",
  "site": {
    "id": 10,
    "name": "My Blog",
    "url": "https://myblog.com",
    "wp_path": "/var/www/my-site",
    "node_id": 1
  }
}
```

**Errors:**
- `400 Bad Request`: Invalid site (missing `wp-content` or path does not exist).
- `422 Unprocessable Entity`: `wp-config.php` not found (returns hint to provide explicit path).


### Import Discovered Site
**Endpoint**: `POST /sites/import`
**Auth**: Bearer Token (Super Admin)
**Query Params**: `name`, `wp_path`, `db_name` (optional), `node_id` (optional)

**Response:**
```json
{
  "success": true,
  "message": "Site 'example.com' imported successfully",
  "site": {
    "id": 1,
    "name": "example.com",
    "wp_path": "/var/www/example.com/htdocs",
    "node_id": 1
  }
}
```

---

## Backup History

### List Site Backups
**Endpoint**: `GET /sites/{site_id}/backups`
**Auth**: Bearer Token (Node Admin+)
**Query Params**: `skip`, `limit`

**Response:**
```json
{
  "backups": [
    {
      "id": 1,
      "site_id": 5,
      "site_name": "example.com",
      "filename": "backup_2025-12-26.tar.zst",
      "size_bytes": 52428800,
      "size_gb": 0.049,
      "s3_path": "s3://bucket/backups/site5/backup_2025-12-26.tar.zst",
      "created_at": "2025-12-26T10:00:00Z",
      "backup_type": "full",
      "status": "SUCCESS",
      "storage_provider": "S3 Prod"
    }
  ],
  "total": 1
}
```

### Get Backup Details
**Endpoint**: `GET /backups/{backup_id}`
**Auth**: Bearer Token (Node Admin+)

**Response:**
```json
{
  "id": 1,
  "site_id": 5,
  "site_name": "example.com",
  "filename": "backup_2025-12-26.tar.zst",
  "size_bytes": 52428800,
  "size_gb": 0.049,
  "s3_path": "s3://bucket/backups/site5/backup_2025-12-26.tar.zst",
  "created_at": "2025-12-26T10:00:00Z",
  "backup_type": "full",
  "status": "SUCCESS",
  "storage_provider": "S3 Prod",
  "storage_provider_detail": {
    "id": 1,
    "name": "S3 Prod",
    "type": "s3"
  }
}
```

### Delete Backup
**Endpoint**: `DELETE /backups/{backup_id}`
**Auth**: Bearer Token (Super Admin only)
**Query Params**: `delete_remote` (bool, default: false)

**Response:**
```json
{
  "success": true,
  "message": "Backup 'backup_2025-12-26.tar.zst' for site 'example.com' deleted",
  "remote_deleted": false
}
```

### Download Backup
**Endpoint**: `GET /backups/{backup_id}/download`
**Auth**: Bearer Token (Node Admin+)

Generates a presigned download URL for the backup file.

**Response:**
```json
{
  "backup_id": 1,
  "filename": "backup_2025-12-26.tar.zst",
  "s3_path": "s3://bucket/backups/site5/backup_2025-12-26.tar.zst",
  "provider": "S3 Prod",
  "download_url": "https://s3.../presigned...",
  "expires_in_seconds": 3600
}
```

---

## Backup Control

### Start Backup
**Endpoint**: `POST /sites/{site_id}/backup/start`
**Auth**: Bearer Token (Node Admin+)

Starts a **real backup** that runs through all stages:
1. Database dump (mysqldump)
2. File backup (wp-content)
3. Compression (tar + zstd)
4. Upload to storage provider
5. Cleanup

**Response:**
```json
{
  "success": true,
  "message": "Backup started for example.com",
  "status": "running",
  "site_id": 1
}
```

### Stop Backup
**Endpoint**: `POST /sites/{site_id}/backup/stop`
**Auth**: Bearer Token (Node Admin+)

**Response:**
```json
{
  "success": true,
  "message": "Backup stop requested",
  "status": "stopped"
}
```

### Get Backup Status
**Endpoint**: `GET /daemon/backup/status/{site_id}`
**Auth**: Bearer Token (Any authenticated)

Poll this endpoint to track backup progress.

**Response:**
```json
{
  "site_id": 1,
  "site_name": "example.com",
  "status": "running",
  "progress": 60,
  "message": "Running: backup_files",
  "error": null,
  "started_at": "2025-12-26T10:30:58.089482"
}
```

**Status Values:**
| Status | Description |
|--------|-------------|
| `idle` | No backup running |
| `running` | Backup in progress |
| `completed` | Backup finished successfully |
| `failed` | Backup failed (check `error`) |
| `stopped` | Backup stopped by user |

### Reset Stuck Backup
**Endpoint**: `POST /daemon/backup/reset/{site_id}`
**Auth**: Bearer Token (Node Admin+)

Resets a stuck backup status back to `idle`. Use this if a backup is stuck in `running` state.

**Response:**
```json
{
  "success": true,
  "message": "Backup status reset to idle for example.com"
}
```

### Daemon Health
**Endpoint**: `GET /daemon/health`
**Auth**: None (Public)

**Response:**
```json
{
  "status": "healthy",
  "running_backups": 0,
  "timestamp": "2025-12-26T10:30:00.000000"
}
```

---

## Logs Management Endpoints

All log endpoints require **Super Admin** role for security.

### List Log Entries
**Endpoint**: `GET /logs`
**Auth**: Bearer Token (Super Admin only)
**Query Params**:
- `limit` (int, default: 50, max: 500): Number of entries
- `level` (string, optional): Filter by level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- `search` (string, optional): Filter by message content

**Response:**
```json
{
  "entries": [
    {
      "timestamp": "2025-12-27T03:59:26.541554Z",
      "level": "INFO",
      "logger": "master.api.v1.endpoints.auth",
      "message": "[LOGIN] Token created successfully for: admin@example.com",
      "module": "auth",
      "function": "login_access_token",
      "line": 101
    }
  ],
  "total": 5,
  "filters": {
    "level": null,
    "search": null
  }
}
```

### List Log Files
**Endpoint**: `GET /logs/files`
**Auth**: Bearer Token (Super Admin only)

**Response:**
```json
{
  "log_directory": "/opt/wordpress-backup/logs",
  "files": [
    {
      "name": "app.json.log",
      "size_bytes": 954,
      "modified": "2025-12-27T03:59:07.572972"
    },
    {
      "name": "app.log",
      "size_bytes": 502,
      "modified": "2025-12-27T03:59:07.572972"
    },
    {
      "name": "error.log",
      "size_bytes": 0,
      "modified": "2025-12-27T03:56:38.059638"
    }
  ],
  "total": 3
}
```

### Download Log File
**Endpoint**: `GET /logs/download/{filename}`
**Auth**: Bearer Token (Super Admin only)

Returns the log file as a text/plain download.

**Security**: Only files in the log directory can be downloaded (path traversal protection).

### Search Logs
**Endpoint**: `GET /logs/search`
**Auth**: Bearer Token (Super Admin only)
**Query Params**:
- `query` (string, required): Search term
- `limit` (int, default: 100, max: 500)
- `level` (string, optional)

**Response:**
```json
{
  "query": "login",
  "entries": [...],
  "total": 3
}
```

### Stream Logs (Real-time)
**Endpoint**: `GET /logs/stream`
**Auth**: Query parameter `?token=<jwt>` (Required)

Server-Sent Events (SSE) stream of new log entries.

> **Note**: Browser EventSource API cannot send custom headers, so authentication is via query parameter only.

**Response Events:**
```json
{"event": "connected", "message": "Streaming logs...", "user": "admin@example.com"}
{"timestamp": "...", "level": "INFO", "message": "...", ...}
```

**Usage (JavaScript):**
```javascript
// Get token from login response
const token = 'your-jwt-token';

// Connect to SSE stream with token as query param
const source = new EventSource(`/api/v1/logs/stream?token=${token}`);

source.onmessage = (event) => {
  const entry = JSON.parse(event.data);
  console.log(`[${entry.level}] ${entry.message}`);
};

source.onerror = (e) => {
  console.error('SSE error:', e);
  source.close();
};
```

### Log Statistics
**Endpoint**: `GET /logs/stats`
**Auth**: Bearer Token (Super Admin only)

**Response:**
```json
{
  "file_count": 3,
  "total_size_bytes": 2220,
  "total_size_mb": 0.0,
  "recent_entries_by_level": {
    "INFO": 6
  },
  "log_directory": "/opt/wordpress-backup/logs"
}
```

### Log Levels
**Endpoint**: `GET /logs/levels`
**Auth**: Bearer Token (Super Admin only)

**Response:**
```json
{
  "current_level": "INFO",
  "available_levels": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
}
```

### Log Files

| File | Purpose |
|------|---------|
| `app.log` | Human-readable text logs (INFO+) |
| `app.json.log` | JSON-formatted logs for API parsing |
| `error.log` | ERROR and CRITICAL logs only |

