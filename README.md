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
| [Configuration](docs/configuration.md) | All `configure.sh` options and flows |
| [Managing Sites](docs/sites.md) | Multi-site setup with `sites.json` |
| [Deployment](docs/deployment.md) | Remote server deployment with `deploy.sh` |
| [Backup Operations](docs/backup.md) | Running backups, `run.sh` options |
| [S3 Storage](docs/s3-storage.md) | Unlimited S3 servers, provider setup |
| [Cloudflare D1](docs/cloudflare-d1.md) | D1 sync, batching, schema |
| [Architecture](docs/architecture.md) | File structure, database schema |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |

## Key Features

- **Multi-Site**: Back up unlimited WordPress sites from one installation
- **Auto-Detection**: Automatically discovers WordPress sites in `/var/www/`
- **Remote-First**: Configure locally, sites detected on server during deploy
- **Server Isolation**: Each server uses unique `SERVER_ID` for storage/logs
- **Unlimited S3 Storage**: Support for unlimited S3-compatible servers (iDrive E2, AWS S3, Backblaze B2, etc.)
- **Cloudflare D1**: Free-tier optimized sync (batched, server-isolated)
- **Systemd Integration**: Automatic scheduling with timers
- **Email Notifications**: Daily reports and failure alerts

## Configuration Flow

### Local (Workstation)
1. Set deployment target (host, user, port)
2. Configure credentials (S3, SMTP, D1) — each optional with Y/N/S
3. Deploy to server

### Remote (Server)
1. Auto-detects WordPress sites
2. Validates requirements (warns if S3/SMTP missing)
3. Sets `SERVER_ID` from hostname
4. Generates systemd timers

## Server Isolation (Multi-Server)

When multiple servers share S3 storage or D1:

- **Storage**: Archives stored in `/{SERVER_ID}/Year/Month/Day/`
- **Logs**: Only syncs records where `server_id` matches
- **No conflicts**: Each server manages its own data

## S3 Storage

Configure unlimited S3-compatible servers in `.env`:

```env
S3_SERVER_1_ENDPOINT="t5k4.ldn.idrivee2-61.com"
S3_SERVER_1_REGION="eu-west-3"
S3_SERVER_1_ACCESS_KEY="your-key"
S3_SERVER_1_SECRET_KEY="your-secret"
S3_SERVER_1_BUCKET="wordpress-backups"

# Add more with S3_SERVER_2_*, S3_SERVER_3_*, etc.
```

See [S3 Storage docs](docs/s3-storage.md) for provider-specific setup.

## License

MIT License
