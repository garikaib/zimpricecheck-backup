# Users API

User management and role assignment.

## Endpoints Overview

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/users/` | List users | Node Admin+ |
| POST | `/users/` | Create user | Super Admin |
| GET | `/users/{id}` | Get user details | Node Admin+ |
| PUT | `/users/{id}` | Update user | Node Admin+ |
| DELETE | `/users/{id}` | Delete user | Super Admin |
| POST | `/users/{id}/nodes` | Assign nodes to user | Super Admin |
| POST | `/users/{id}/sites` | Assign sites to user | Super Admin |
| DELETE | `/users/{id}/nodes/{node_id}` | Remove node assignment | Super Admin |
| DELETE | `/users/{id}/sites/{site_id}` | Remove site assignment | Super Admin |

---

## GET /users/

List all users.

**Visibility:**
- Super Admin: All users
- Node Admin: Site Admins on their assigned nodes
- Site Admin: Own profile only

### Response

```json
{
  "users": [
    {
      "id": 1,
      "email": "admin@example.com",
      "full_name": "Admin User",
      "role": "super_admin",
      "is_active": true,
      "assigned_nodes": [],
      "assigned_sites": [],
      "created_at": "2025-01-01T00:00:00"
    }
  ],
  "total": 1
}
```

---

## POST /users/

Create a new user.

### Request

```bash
curl -X POST "https://api.example.com/api/v1/users/" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "full_name": "New User",
    "password": "SecurePass123!",
    "role": "node_admin"
  }'
```

### Response

```json
{
  "id": 2,
  "email": "newuser@example.com",
  "full_name": "New User",
  "role": "node_admin",
  "is_active": true,
  "assigned_nodes": [],
  "assigned_sites": []
}
```

---

## POST /users/{id}/nodes

Assign nodes to a user. **Super Admin only.**

### Request

```bash
curl -X POST "https://api.example.com/api/v1/users/2/nodes" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"node_ids": [1, 2, 3]}'
```

### Response

```json
{
  "message": "Assigned 3 nodes to user",
  "user_id": 2,
  "assigned_nodes": [1, 2, 3]
}
```

---

## POST /users/{id}/sites

Assign sites to a user. **Super Admin only.**

### Request

```bash
curl -X POST "https://api.example.com/api/v1/users/3/sites" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"site_ids": [5, 6]}'
```

### Response

```json
{
  "message": "Assigned 2 sites to user",
  "user_id": 3,
  "assigned_sites": [5, 6]
}
```

