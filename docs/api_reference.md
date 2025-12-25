# SaaS Master API Reference

This document provides extensive documentation for the Master Server API, intended for building Admin Panels or integrating third-party tools.

## Base URL
*   Production: `http://<master-ip>:8000/api/v1`
*   Test Tunnel: `http://localhost:8001/api/v1` (via `./deploy.sh master --test`)

## Authentication

The API uses **OAuth2 Password Bearer** flow for Admins and **API Keys** for Nodes.

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
*   `super_admin`: Full access.
*   `node_admin`: Can manage own nodes (Future).
*   `site_admin`: Can manage own sites (Future).
