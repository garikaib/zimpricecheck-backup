# Users API

User management and role assignment.

## Endpoints Overview

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/users/` | List users | Super Admin |
| POST | `/users/` | Create user | Super Admin |
| GET | `/users/{id}` | Get user details | Super Admin |
| PUT | `/users/{id}` | Update user | Super Admin |
| DELETE | `/users/{id}` | Delete user | Super Admin |

---

## GET /users/

List all users.

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
    "password": "secure_password",
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
  "is_active": true
}
```
