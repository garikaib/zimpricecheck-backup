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
