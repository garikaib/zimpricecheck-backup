# Frontend RBAC Implementation Brief

This document details the frontend implementation requirements for the new Role-Based Access Control (RBAC) system.

## Core Concepts

### Permission Model
Permissions are now based on **Many-to-Many (M:N) resource assignments**, not legacy 1:1 `admin_id` fields:
- **Node Admins** access nodes via `user.assigned_nodes`
- **Site Admins** access sites via `user.assigned_sites`
- Backend endpoints are automatically filtered based on these assignments

### Role Definitions

| Role | Nodes | Sites | Users | Backups |
|------|-------|-------|-------|---------|
| **Super Admin** | All (Full CRUD) | All (Full CRUD) | All (Full CRUD) | All (Full CRUD) |
| **Node Admin** | Assigned only (Read) | Sites on assigned nodes (Read/Backup) | Site Admins on their nodes (Read) | Sites on assigned nodes |
| **Site Admin** | None | Assigned only (Read/Backup) | Self only | Assigned sites only |

---

## UI Components Required

### 1. User Assignment Manager (Super Admin Only)

Create a modal/drawer for managing user assignments:

```
┌─────────────────────────────────────────────┐
│  Manage Assignments: john@example.com       │
│  Role: Node Admin                           │
├─────────────────────────────────────────────┤
│  Assigned Nodes:                            │
│  ☑ node-1.example.com                       │
│  ☑ node-2.example.com                       │
│  ☐ node-3.example.com                       │
│                                             │
│  [Save Changes]                             │
└─────────────────────────────────────────────┘
```

**API Endpoints:**
- `GET /api/v1/users/{id}` - Get user with assignments
- `POST /api/v1/users/{id}/nodes` - Assign nodes (body: `{node_ids: [1,2,3]}`)
- `POST /api/v1/users/{id}/sites` - Assign sites (body: `{site_ids: [1,2,3]}`)

**Logic:**
- Show nodes selector for `node_admin` role
- Show sites selector for `site_admin` role
- Clear assignments when role changes

### 2. Navigation Filtering

Filter navigation items based on user role:

```vue
<!-- Example: Hide "Add Node" for non-Super Admins -->
<UButton v-if="authStore.isSuperAdmin" @click="openAddNodeModal">
  Add Node
</UButton>
```

**Role Checks:**
```typescript
const authStore = useAuthStore()

// Check functions
authStore.isSuperAdmin   // role === 'super_admin'
authStore.isNodeAdmin    // role === 'node_admin' 
authStore.isSiteAdmin    // role === 'site_admin'
authStore.isNodeAdminOrHigher // super_admin OR node_admin
```

### 3. List Filtering

The backend now automatically filters lists. No frontend filtering needed, but handle empty states:

```vue
<template>
  <div v-if="nodes.length === 0">
    <p v-if="authStore.isSiteAdmin">
      You don't have access to any nodes.
    </p>
    <p v-else>
      No nodes found. <UButton v-if="authStore.isSuperAdmin">Add Node</UButton>
    </p>
  </div>
</template>
```

### 4. Backup Controls for Site Admins

**NEW**: Site Admins can now manage backups for their assigned sites.

Enable backup buttons for all authenticated users (backend enforces access):

```vue
<!-- Previously: v-if="authStore.isNodeAdminOrHigher" -->
<!-- Now: Always show, backend will 403 if unauthorized -->
<UButton @click="startBackup(site.id)">Start Backup</UButton>
<UButton @click="stopBackup(site.id)">Stop Backup</UButton>
```

---

## API Response Changes

### User Response (Updated)

```typescript
interface UserResponse {
  id: number
  email: string
  full_name: string | null
  role: 'super_admin' | 'node_admin' | 'site_admin'
  is_active: boolean
  assigned_nodes: number[]  // NEW: List of assigned node IDs
  assigned_sites: number[]  // NEW: List of assigned site IDs
}
```

### Filtered Lists

The following endpoints now return filtered results:

| Endpoint | Super Admin | Node Admin | Site Admin |
|----------|-------------|------------|------------|
| `GET /nodes/` | All nodes | Assigned nodes only | Empty |
| `GET /sites/` | All sites | Sites on assigned nodes | Assigned sites only |
| `GET /users/` | All users | Site Admins on their nodes | Only self |

---

## Error Handling

Handle `403 Forbidden` responses gracefully:

```typescript
try {
  await api.delete(`/sites/${siteId}`)
} catch (error) {
  if (error.response?.status === 403) {
    toast.error('You do not have permission to delete this site.')
  }
}
```

---

## Implementation Checklist

- [ ] Create `UserAssignmentsModal.vue` component
- [ ] Add role-based navigation visibility
- [ ] Update node/site list empty states
- [ ] Enable backup buttons for all roles
- [ ] Update user table to show assignments
- [ ] Add 403 error handling globally
- [ ] Update `authStore` with role helper methods
