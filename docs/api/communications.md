# Communication Channels API

Manage notification channels (Email, SMS, etc.) and providers.

## List Providers

Get a list of available communication providers and their configuration schemas. This is useful for building dynamic configuration forms.

**Endpoint**: `GET /communications/providers`
**Auth**: `super_admin` only

**Response**:

```json
{
  "providers": [
    {
      "channel_type": "email",
      "provider_name": "smtp",
      "config_schema": {
        "host": {"type": "string", "required": true},
        "port": {"type": "integer", "required": true},
        "encryption": {"type": "string", "required": false},
        "username": {"type": "string", "required": true},
        "password": {"type": "string", "required": true, "secret": true},
        "from_email": {"type": "string", "required": true},
        "from_name": {"type": "string", "required": false}
      }
    },
    {
      "channel_type": "email",
      "provider_name": "sendpulse_api",
      "config_schema": {
        "api_id": {"type": "string", "required": true},
        "api_secret": {"type": "string", "required": true, "secret": true},
        "from_email": {"type": "string", "required": true},
        "from_name": {"type": "string", "required": false}
      }
    }
  ]
}
```

## List Channels

List all configured communication channels.

**Endpoint**: `GET /communications/channels`
**Auth**: `super_admin` only

**Response**:

```json
{
  "channels": [
    {
      "id": 1,
      "name": "Primary SMTP",
      "channel_type": "email",
      "provider": "smtp",
      "is_default": true,
      "is_active": true,
      "priority": 10,
      "created_at": "2023-10-27T10:00:00Z"
    }
  ],
  "total": 1
}
```

## Create Channel

Create a new communication channel. The `config` object is strictly validated against the provider's schema.

**Endpoint**: `POST /communications/channels`
**Auth**: `super_admin` only

**Body**:

```json
{
  "name": "SendPulse Transactional",
  "channel_type": "email",
  "provider": "sendpulse_api",
  "config": {
    "api_id": "...",
    "api_secret": "...",
    "from_email": "noreply@example.com"
  },
  "is_default": false,
  "priority": 20
}
```

**Errors**:
- `400 Bad Request`: Invalid provider or configuration validation failure (e.g. missing fields, wrong types).
    - **Note**: `from_email` is strictly validated for format.
    - **SendPulse**: The `from_email` MUST be a verified sender in your SendPulse account.

## Update Channel

Update an existing channel. Configuration updates are validated.

**Endpoint**: `PUT /communications/channels/{id}`
**Auth**: `super_admin` only

**Body**:

```json
{
  "config": {
    "host": "new.smtp.host"
  },
  "is_active": true
}
```

## Delete Channel

**Endpoint**: `DELETE /communications/channels/{id}`
**Auth**: `super_admin` only

## Test Channel

Send a test message through a specific channel to verify configuration.

**Endpoint**: `POST /communications/channels/{id}/test`
**Auth**: `super_admin` only

**Body**:
```json
{
  "to": "admin@example.com"
}
```

**Success Response** (200):
```json
{
  "success": true,
  "message": "Test message sent successfully"
}
```

**Error Response** (500):
```json
{
  "detail": "Test failed: <error message>"
}
```

## Troubleshooting

### "Failed to decrypt channel config"

**Cause**: The channel's encrypted configuration is corrupted, empty, or was encrypted with a different `SECRET_KEY`.

**Fix**:
1. Re-save the channel configuration via `PUT /communications/channels/{id}` with complete `config` object.
2. Ensure `SECRET_KEY` in `.env` hasn't changed since the channel was created.

### "Empty config for channel" / "Invalid config for channel"

**Cause**: The channel configuration is missing required fields (e.g., `from_email`, `host`, `password`).

**Fix**:
1. Check provider schema via `GET /communications/providers`.
2. Update the channel with all required fields.

### "KeyError: 'from_email'" or similar

**Cause**: A required configuration field is missing. The system now validates configs before use, so this error should show as "Invalid config" instead.

**Fix**: Update the channel with the missing field.
