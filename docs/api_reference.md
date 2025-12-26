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

### 2. Node Authentication
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
