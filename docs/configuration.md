# Configuration Reference

The system uses two configuration files:
1. `.env` - Deployment target, SMTP, and system settings
2. `config.json` - Sites and S3 storage

## 1. Environment Config (.env)

Managed via `./configure.sh`.

| Variable | Description | Default |
|----------|-------------|---------|
| `REMOTE_HOST` | Target server IP/domain | - |
| `REMOTE_USER` | SSH Username | `ubuntu` |
| `SERVER_ID` | Unique ID for this server instance | (Hostname) |
| `SMTP_SERVER` | SMTP Hostname | - |
| `SMTP_PORT` | SMTP Port | `587` |
| `BACKUP_FREQUENCY` | `daily`, `twice`, `every-6h` | `daily` |
| `RETENTION_S3_DAYS` | Days to keep remote backups | `7` |

## 2. Unified Config (config.json)

Contains lists of sites and storage providers.

### Sites Array
See [Managing Sites](sites.md).

```json
"sites": [
  {
    "name": "mysite",
    "wp_config_path": "/path/to/wp-config.php",
    ...
  }
]
```

### Storage Array
See [S3 Storage](s3-storage.md).

```json
"storage": [
  {
    "name": "idrive",
    "type": "s3",
    "endpoint": "...",
    "weight": 100
  }
]
```

## Setup Wizard

The `./configure.sh` script is the primary interface for managing both files.

```bash
# Standard wizard (env + optional sections)
./configure.sh

# Detect sites (populates config.json)
./configure.sh --detect

# Validate configuration
./configure.sh --validate
```
