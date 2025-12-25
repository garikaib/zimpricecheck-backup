# Configuration Reference

The system relies on two distinct configuration files for different purposes.

## 1. System Config: `.env`

The `.env` file handles **Deployment Targets**, **Credentials**, and **Global Settings**. It is NOT version controlled.

**Management**: Use `./configure.sh` (Main Menu) or edit manually.

| Category | Variable | Description |
|---|---|---|
| **Deployment** | `REMOTE_HOST` | Target VPS IP or Domain |
| | `REMOTE_USER` | SSH Username (default: `ubuntu`) |
| | `REMOTE_DIR` | Installation path |
| **Identity** | `SERVER_ID` | Unique ID for this server instance (e.g., hostname) |
| **Master** | `MASTER_URL` | URL of Master Server (Node Mode only) |
| | `NODE_API_KEY` | Auto-generated key (Node Mode only) |
| **Notifications** | `SMTP_SERVER` | SMTP Hostname |
| | `SMTP_USER` | SMTP Username |
| | `SMTP_PASSWORD` | SMTP Password |
| **Cloudflare** | `CLOUDFLARE_ACCOUNT_ID` | D1 Logging Account ID |
| | `CLOUDFLARE_API_TOKEN` | D1 API Token |

---

## 2. Backup Config: `config.json`

The `config.json` file handles **Site Definitions** and **S3 Storage Destinations**. It IS designed to be portable/shared if needed.

**Management**: Use `./configure.sh` (Sub-menus) or edit manually.

### A. Sites Array
Defines the WordPress installations to back up.
*See [Managing Sites](sites.md) for details.*

```json
{
  "sites": [
    {
      "name": "my-blog",
      "wp_config_path": "/var/www/html/wp-config.php",
      "wp_content_path": "/var/www/html/wp-content",
      "db_name": "wp_db" // Optional overrides
    }
  ]
}
```

### B. Storage Array
Defines S3-compatible destinations with failover priority.
*See [S3 Storage](s3-storage.md) for details.*

```json
{
  "storage": [
    {
      "name": "primary-storage",
      "type": "s3",
      "endpoint": "t5k4.ldn.idrivee2-61.com",
      "bucket": "backups-bucket",
      "weight": 100
    },
    {
      "name": "fallback-storage",
      "type": "s3",
      "endpoint": "s3.amazonaws.com",
      "bucket": "emergency-bucket",
      "weight": 50
    }
  ]
}
```

## 3. Setup Wizard

The `./configure.sh` script is the primary tool for managing both files interactively.

```bash
# Main Wizard (Manage .env, Email, D1)
./configure.sh

# Site Detection (Populates config.json)
./configure.sh --detect

# Admin Management (Master Server Only)
./configure.sh --add-admin

# Validation
./configure.sh --validate
```
