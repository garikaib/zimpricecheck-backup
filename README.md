# WordPress Backup System

**Multi-Site SaaS Edition** — Automated backup for multiple WordPress sites with Mega.nz storage and Cloudflare D1 synchronization.

## Quick Start

```bash
git clone <repo-url>
cd wordpress-backup
./configure.sh          # Interactive setup wizard
./deploy.sh             # Deploy to remote server
```

## Documentation

| Document | Description |
|----------|-------------|
| [Installation](docs/installation.md) | Requirements, setup, and first run |
| [Configuration](docs/configuration.md) | All `configure.sh` options and flags |
| [Managing Sites](docs/sites.md) | Multi-site setup with `sites.json` |
| [Deployment](docs/deployment.md) | Remote server deployment with `deploy.sh` |
| [Backup Operations](docs/backup.md) | Running backups, `run.sh` options |
| [Cloudflare D1](docs/cloudflare-d1.md) | D1 sync, batching, schema |
| [Architecture](docs/architecture.md) | File structure, database schema |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |

## Key Features

- **Multi-Site**: Back up unlimited WordPress sites from one installation
- **Mega.nz Storage**: Up to 3 accounts with smart rotation
- **Cloudflare D1**: Free-tier optimized sync with batching
- **Configurable Deployment**: Deploy to any server via `.env`
- **Systemd Integration**: Automatic scheduling with timers

## License

MIT License
