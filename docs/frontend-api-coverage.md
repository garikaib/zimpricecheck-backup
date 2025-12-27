# Backend API Coverage for Frontend

Base URL: `https://wp.zimpricecheck.com:8081/api/v1`

## Authentication

| Endpoint | Method | Auth | Request | Response |
|----------|--------|------|---------|----------|
| `/auth/login` | POST | None | `{username, password}` | `{access_token, token_type}` |

---

## Users

| Endpoint | Method | Auth | Request | Response |
|----------|--------|------|---------|----------|
| `/users/me` | GET | Bearer | - | `UserResponse` |
| `/users/` | GET | Bearer (Node Admin+) | `?skip=0&limit=100` | `{users: [], total: int}` |
| `/users/` | POST | Bearer (Super Admin) | `UserCreate` | `UserResponse` |
| `/users/{id}` | GET | Bearer (Node Admin+) | - | `UserResponse` |
| `/users/{id}` | PUT | Bearer (Node Admin+) | `UserUpdate` | `UserResponse` |
| `/users/{id}` | DELETE | Bearer (Super Admin) | - | `UserResponse` |

### Types

```typescript
interface UserCreate {
  email: string;
  password: string;
  full_name?: string;
  is_active?: boolean;
  role?: 'super_admin' | 'node_admin' | 'site_admin';
}

interface UserUpdate {
  email?: string;
  password?: string;
  full_name?: string;
  is_active?: boolean;
  role?: 'super_admin' | 'node_admin' | 'site_admin';
}

interface UserResponse {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  role: 'super_admin' | 'node_admin' | 'site_admin';
}
```

---

## Nodes

| Endpoint | Method | Auth | Request | Response |
|----------|--------|------|---------|----------|
| `/nodes/` | GET | Bearer | `?skip=0&limit=100` | `NodeResponse[]` |
| `/nodes/simple` | GET | Bearer | - | `NodeSimple[]` (for dropdowns) |
| `/nodes/{id}` | GET | Bearer (Node Admin+) | - | `NodeDetailResponse` |
| `/nodes/{id}/quota` | PUT | Bearer (Super Admin) | `{storage_quota_gb: int}` | `NodeResponse` |
| `/nodes/{id}/sites` | GET | Bearer (Node Admin+) | `?skip=0&limit=100` | `SiteListResponse` |
| `/nodes/{id}/backups` | GET | Bearer (Node Admin+) | `?site_id=&skip=0&limit=50` | `BackupListResponse` |
| `/nodes/{id}/backups/{backup_id}` | DELETE | Bearer (Super Admin) | - | `{status, backup_id}` |
| `/nodes/join-request` | POST | None | `{hostname, ip_address, system_info?}` | `{request_id, message}` |
| `/nodes/status/{request_id}` | GET | None | - | `{status, api_key?}` |
| `/nodes/approve/{node_id}` | POST | Bearer (Super Admin) | - | `NodeResponse` |

### Types

```typescript
interface NodeSimple {
  id: number;
  hostname: string;
}

interface NodeDetailResponse {
  id: number;
  hostname: string;
  ip_address: string | null;
  status: 'pending' | 'active' | 'blocked';
  storage_quota_gb: number;
  total_available_gb: number;
  storage_used_gb: number;
  sites_count: number;
  backups_count: number;
}

interface NodeResponse {
  id: number;
  hostname: string;
  ip_address: string | null;
  status: 'pending' | 'active' | 'blocked';
  storage_quota_gb: number;
}
```

---

## Sites

| Endpoint | Method | Auth | Request | Response |
|----------|--------|------|---------|----------|
| `/sites/` | GET | Bearer | `?skip=0&limit=100` | `SiteListResponse` |
| `/sites/simple` | GET | Bearer | `?node_id=` | `SiteSimple[]` (for dropdowns) |
| `/sites/{id}` | GET | Bearer | - | `SiteResponse` |

### Types

```typescript
interface SiteSimple {
  id: number;
  name: string;
  node_id: number;
}

interface SiteResponse {
  id: number;
  name: string;
  wp_path: string;
  db_name: string | null;
  node_id: number;
  status: string;
  storage_used_gb: number;
  last_backup: string | null;
}

interface SiteListResponse {
  sites: SiteResponse[];
  total: number;
}

interface BackupResponse {
  id: number;
  site_id: number;
  site_name: string;
  filename: string;
  size_bytes: number;
  size_gb: number;
  s3_path?: string;
  created_at: string;
  backup_type: 'full' | 'incremental';
  status: string;
  storage_provider?: string;
}

interface BackupListResponse {
  backups: BackupResponse[];
  total: number;
}
```

---

## Stats

| Endpoint | Method | Auth | Request | Response |
|----------|--------|------|---------|----------|
| `/stats/` | POST | X-API-KEY | `{cpu_usage, disk_usage, active_backups}` | `{status: "ok"}` |

---

## Error Responses

```typescript
interface HTTPError {
  detail: string;
}
```

| Status | Meaning |
|--------|---------|
| 400 | Bad Request / Validation Error |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient privileges) |
| 404 | Not Found |

---

## Example: Composables

```typescript
// composables/useUsers.ts
export const useUsers = () => {
  const { $api } = useNuxtApp()
  
  const getMe = () => $api('/users/me')
  const listUsers = (skip = 0, limit = 100) => 
    $api(`/users/?skip=${skip}&limit=${limit}`)
  const createUser = (data: UserCreate) => 
    $api('/users/', { method: 'POST', body: data })
  const updateUser = (id: number, data: UserUpdate) => 
    $api(`/users/${id}`, { method: 'PUT', body: data })
  const deleteUser = (id: number) => 
    $api(`/users/${id}`, { method: 'DELETE' })
  
  return { getMe, listUsers, createUser, updateUser, deleteUser }
}
```
