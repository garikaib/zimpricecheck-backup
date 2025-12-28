# Authentication API

User authentication and token management.

## Endpoints Overview

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/auth/login` | Login with credentials | Public |
| POST | `/auth/magic-link` | Request magic link | Public |
| GET | `/auth/verify-magic/{token}` | Verify magic link | Public |
| GET | `/auth/me` | Get current user | Authenticated |
| POST | `/auth/mfa/enable` | Enable MFA for user | Authenticated |
| POST | `/auth/mfa/verify` | Verify MFA & get token | Public (with mfa_token) |

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

### Response (Success)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### Response (MFA Required)

If the user has MFA enabled, the response will prompt for a second factor.

```json
{
  "access_token": "", 
  "token_type": "bearer",
  "mfa_required": true,
  "mfa_token": "eyJhbGciOiJIUzI1NiIs..." 
}
```

The `mfa_token` is a temporary token with `scope="mfa_pending"` used to call `/auth/mfa/verify`.

---

## POST /auth/mfa/verify

Verify the One-Time Password (OTP) sent to the user's communication channel.

### Request

```bash
curl -X POST "https://api.example.com/api/v1/auth/mfa/verify" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "123456",
    "mfa_token": "eyJhbGciOiJIUzI1NiIs..."
  }'
```

### Response

Returns a standard access token upon successful verification.

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

---

## POST /auth/mfa/enable

Enable MFA for the current user. Requires selecting a communication channel.

### Request

```bash
curl -X POST "https://api.example.com/api/v1/auth/mfa/enable" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": 1
  }'
```

### Response

Returns a fresh access token (optional) or success.

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
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
  "is_active": true,
  "mfa_enabled": true
}
```
