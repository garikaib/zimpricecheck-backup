# Authentication API

User authentication and token management.

## Endpoints Overview

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/auth/login` | Login with credentials | Public |
| POST | `/auth/magic-link` | Request magic link | Public |
| GET | `/auth/verify-magic/{token}` | Verify magic link | Public |
| GET | `/auth/me` | Get current user | Authenticated |
| POST | `/auth/refresh` | Refresh token | Authenticated |

---

## POST /auth/login

Authenticate with username and password.

### Request

```bash
curl -X POST "https://api.example.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin@example.com",
    "password": "your_password"
  }'
```

### Response

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

---

## POST /auth/magic-link

Request a magic link login email.

### Request

```bash
curl -X POST "https://api.example.com/api/v1/auth/magic-link" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com"}'
```

### Response

```json
{
  "success": true,
  "message": "Magic link sent to admin@example.com"
}
```

---

## GET /auth/me

Get current authenticated user info.

### Response

```json
{
  "id": 1,
  "email": "admin@example.com",
  "full_name": "Admin User",
  "role": "super_admin",
  "is_active": true
}
```
