# WordPress Backup Platform (SaaS Edition)

A scalable, **Master/Node** platform for automated WordPress backups.

- **Central Master Server**: Secure API for node management, stats aggregation, and RBAC implementation.
- **Node Agents**: Lightweight agents running on client servers (Nodes) that perform the actual backups.
- **Independence**: Nodes maintain local autonomy (local site definitions, local schedules) while streaming stats to the Master.

## Architecture

| Component | Role | Tech Stack |
|-----------|------|------------|
| **Master Server** | Central Orchestrator, RBAC, Stats API | FastAPI, SQLite/Postgres |
| **Node Agent** | Backup Executor, S3 Uploader, Stats Streamer | Python, Systemd |

## Quick Start

### 1. Deploy Master Server (The Control Plane)

The Master Server serves the API used by nodes to "Join" and report stats.

```bash
git clone <repo-url>
cd wordpress-backup

./configure.sh          # Select "Remote Host" for your Master VPS
./deploy.sh master      # Deploys FastAPI server to port 8000
```

### 2. Deploy Node Agent (The Client)

The Agent runs on your WordPress servers.

```bash
./configure.sh          # 1. Select "Remote Host" for Client VPS
                        # 2. Select "Managed Node" Mode
                        # 3. Enter Master URL (e.g., http://master-ip:8000)
                        
./deploy.sh node        # Deploys Agent + Systemd Timers
```

### 3. Approve Node

New nodes start in `PENDING` state. You must approve them via the Master API.

```bash
# Login as Super Admin (Default: admin@example.com / admin123)
curl -X POST http://master-ip:8000/api/v1/auth/login ...

# Approve Node ID 1
curl -X POST http://master-ip:8000/api/v1/nodes/approve/1 ...
```

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | Deep dive into Master/Node design & Data Flow |
| [Deployment](docs/deployment.md) | Detailed deployment guide for Master & Nodes |
| [Configuration](docs/configuration.md) | Environment variables, `config.json`, and Modes |
| [SaaS Master](docs/saas-master.md) | **NEW**: API Reference, RBAC, and Approval Workflow |
| [Managing Sites](docs/sites.md) | Adding WordPress sites to Nodes (Local config) |
| [S3 Storage](docs/s3-storage.md) | Configuring S3 destinations |
| [Troubleshooting](docs/troubleshooting.md) | Logs, Common Issues |

## Key Features

- **Decentralized Autonomy**: Nodes define sites locally (`config.json`), ensuring backups run even if Master is down.
- **Centralized Visibility**: Master Dashboard (future UI) / API receives live stats (CPU, Disk, Backup Status) from all nodes.
- **Approval Workflow**: Secure enrollment process. Nodes request access, Admins approve.
- **Weighted Storage**: Prioritized failover for S3 destinations (e.g., Try iDrive first, failover to AWS).
- **Concurrency Control**: Intelligent locking to prevent overlapping backups.

## License

MIT License
