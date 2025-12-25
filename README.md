# WordPress Backup System

**Multi-Site SaaS Edition** — Automated backup for multiple WordPress sites with S3-compatible storage and Cloudflare D1 synchronization.

## Quick Start

```bash
git clone <repo-url>
cd wordpress-backup
./configure.sh          # Configure deployment target + credentials
./deploy.sh             # Deploy to remote server (auto-detects WordPress sites)
```

## Documentation

| Document | Description |
|----------|-------------|
| [Installation](docs/installation.md) | Requirements, setup, and first run |
| [Configuration](docs/configuration.md) | `.env` and `config.json` reference |
| [Managing Sites](docs/sites.md) | Multi-site setup in `config.json` |
| [S3 Storage](docs/s3-storage.md) | Unlimited S3 servers with priority weights |
| [Deployment](docs/deployment.md) | Remote server deployment with `deploy.sh` |
| [Backup Operations](docs/backup.md) | Running backups, `run.sh` options |
| [Cloudflare D1](docs/cloudflare-d1.md) | D1 sync, batching, schema |
| [Architecture](docs/architecture.md) | File structure, data flow |

## Key Features

- **Unified Configuration**: Single `config.json` for sites and storage priority
- **Weighted Failover**: Define multiple S3-compatible servers with priority weights
- **Multi-Site**: Back up unlimited WordPress sites from one installation
- **Remote-First**: Configure locally, sites detected on server during deploy
- **Server Isolation**: Each server uses unique `SERVER_ID` for storage/logs
- **Cloudflare D1**: Centralized logging across server fleet

## S3 Storage (config.json)

Configure unlimited S3-compatible servers with priority weights:

```json
"storage": [
  {
    "name": "primary-storage",
    "type": "s3",
    "endpoint": "t5k4.ldn.idrivee2-61.com",
    "bucket": "wordpress-backups",
    "weight": 100
  },
  {
    "name": "fallback-storage",
    "type": "s3",
    "endpoint": "s3.amazonaws.com",
    "bucket": "emergency-backups",
    "weight": 50
  }
]
```

## License

MIT License
