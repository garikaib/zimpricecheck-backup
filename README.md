# WordPress Backup System

**Multi-Site SaaS Edition** — Automated backup for multiple WordPress sites with Mega.nz storage and Cloudflare D1 synchronization.

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
| [Configuration](docs/configuration.md) | All `configure.sh` options and flows |
| [Managing Sites](docs/sites.md) | Multi-site setup with `sites.json` |
| [Deployment](docs/deployment.md) | Remote server deployment with `deploy.sh` |
| [Backup Operations](docs/backup.md) | Running backups, `run.sh` options |
| [Cloudflare D1](docs/cloudflare-d1.md) | D1 sync, batching, schema |
| [Architecture](docs/architecture.md) | File structure, database schema |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |

## Key Features

- **Multi-Site**: Back up unlimited WordPress sites from one installation
- **Auto-Detection**: Automatically discovers WordPress sites in `/var/www/`
- **Remote-First**: Configure locally, sites detected on server during deploy
- **Server Isolation**: Each server uses unique `SERVER_ID` for storage/logs
- **Mega.nz Storage**: Up to 3 accounts with smart rotation per server
- **Cloudflare D1**: Free-tier optimized sync (batched, server-isolated)
- **Systemd Integration**: Automatic scheduling with timers
- **Email Notifications**: Daily reports and failure alerts

## Configuration Flow

### Local (Workstation)
1. Set deployment target (host, user, port)
2. Configure credentials (Mega, SMTP, D1) — each optional with Y/N/S
3. Deploy to server

### Remote (Server)
1. Auto-detects WordPress sites
2. Validates requirements (warns if Mega/SMTP missing)
3. Sets `SERVER_ID` from hostname
4. Generates systemd timers

## Server Isolation (Multi-Server)

When multiple servers share Mega storage or D1:

- **Storage**: Archives stored in `/{SERVER_ID}/Year/Month/`
- **Logs**: Only syncs records where `server_id` matches
- **No conflicts**: Each server manages its own data

## Migration (Existing Data)

For existing installations, run before deploying:

```bash
./migrate.sh <SERVER_ID>
```

This adds `server_id` to all records and reorganizes Mega storage. Self-deletes on success.

## License

MIT License
