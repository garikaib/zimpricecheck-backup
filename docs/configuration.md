# Configuration Reference

The SaaS Platform divides configuration between **Deployment/Infrastructure** (local) and **Business Logic** (remote/centralized).

## 1. Local Infrastructure: `.env`

The `.env` file handles **Deployment Targets**, **Server Identity**, and **Connection Strings**. It is machine-specific and NOT version controlled.

**Management**: Use `./configure.sh` or edit manually.

| Category | Variable | Description |
|---|---|---|
| **Deployment** | `REMOTE_HOST` | Target VPS IP or Domain |
| | `REMOTE_USER` | SSH Username (default: `ubuntu`) |
| | `REMOTE_PORT` | SSH Port (default: `22`) |
| | `REMOTE_DIR` | Installation path (default: `/opt/wordpress-backup`) |
| **Mode** | `MODE` | `master` or `node` |
| **Master (Node Mode)** | `MASTER_URL` | URL of Master Server API |
| | `NODE_API_KEY` | Auto-generated key for auth |
| **Master (Master Mode)** | `SECRET_KEY` | JWT Signing Key |
| | `POSTGRES_USER` | DB User |
| | `POSTGRES_PASSWORD` | DB Password |
| **Notifications** | `SENDPULSE_ID` | SendPulse API ID |
| | `SENDPULSE_SECRET` | SendPulse Secret |
| **Cloudflare** | `CLOUDFLARE_D1_TOKEN` | (Optional) Legacy logging |

---

## 2. Site Configuration

In **Node Mode**, the agent automatically detects WordPress sites in `/var/www/`.

- **Auto-Detection**: Scans for `wp-config.php`.
- **Registration**: Registers sites with the Master API.
- **Filtering**: Can be constrained by `config.json` (optional).

### `config.json` (Optional/Advanced)

Used primarily to *exclude* sites or override specific paths if auto-detection fails.

```json
{
  "sites": [
    {
      "name": "special-site",
      "wp_path": "/custom/path/to/site",
      "skip": false
    }
  ]
}
```

---

## 3. Storage Configuration

**Managed centrally via the Master API.**

See [S3 Storage](s3-storage.md) for details on how to configure providers.

The local `config.json` `storage` section is **deprecated** and ignored in Node Mode.

---

## 4. Setup Scripts

### `deploy.sh`

The primary tool for deploying code to remote servers.

```bash
./deploy.sh [node|master] [--test]
```

### `configure.sh`

Helper to generate `.env` files.

```bash
./configure.sh
```
