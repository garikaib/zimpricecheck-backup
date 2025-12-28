# API Reference

This directory contains detailed API documentation organized by feature area.

## Quick Links

| Document | Description |
|----------|-------------|
| [Authentication](./authentication.md) | Login, tokens, magic links |
| [Nodes](./nodes.md) | Node management and quota |
| [Sites](./sites.md) | Site management and backups |
| [Backups](./backups.md) | Backup CRUD and downloads |
| [Storage](./storage.md) | Providers, health, reconciliation |
| [Communications](./communications.md) | Channels, providers, SMTP/SendPulse |
| [Users](./users.md) | User management and roles |

## Base URL

```
https://wp.zimpricecheck.com:8081/api/v1
```

## Authentication

All endpoints (except login) require a Bearer token:

```bash
curl -H "Authorization: Bearer <token>" https://api.example.com/api/v1/...
```

## Common Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request - validation error |
| 401 | Unauthorized - invalid/missing token |
| 403 | Forbidden - insufficient permissions |
| 404 | Not Found |
| 409 | Conflict - resource in use |
| 500 | Internal Server Error |

## Roles

| Role | Description |
|------|-------------|
| `super_admin` | Full system access |
| `node_admin` | Manage assigned nodes/sites |
| `site_admin` | View assigned sites only |
