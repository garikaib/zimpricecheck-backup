# Users API

User management endpoints with role-based access control.

## Roles

| Role | Scope |
|------|-------|
| `super_admin` | Full system access, manage all users/nodes/sites |
| `node_admin` | Manage nodes and Site Admins assigned to them |
| `site_admin` | Manage own sites, view own profile |

---

## Endpoints

### Get Current User
```
GET /api/v1/users/me
Auth: Any authenticated
```
Returns the authenticated user's profile.

### List Users
```
GET /api/v1/users/
Auth: Node Admin+
Query: skip (int), limit (int)
```
- **Super Admin**: All users
- **Node Admin**: Site Admins on their nodes

### Create User
```
POST /api/v1/users/
Auth: Super Admin
Content-Type: application/json
```
```json
{
  "email": "user@example.com",
  "password": "securepass",
  "full_name": "John Doe",
  "role": "site_admin"
}
```

### Get User by ID
```
GET /api/v1/users/{user_id}
Auth: Node Admin+
```
Access restricted by role hierarchy.

### Update User
```
PUT /api/v1/users/{user_id}
Auth: Node Admin+
Content-Type: application/json
```
```json
{
  "full_name": "Updated Name",
  "is_active": true
}
```
> **Note**: Only Super Admins can change user roles.

### Delete User
```
DELETE /api/v1/users/{user_id}
Auth: Super Admin
```
Cannot delete yourself.

---

## Response Schema

```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "role": "site_admin"
}
```

List response:
```json
{
  "users": [...],
  "total": 10
}
```
