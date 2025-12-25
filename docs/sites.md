# Managing WordPress Sites

The backup system supports **unlimited WordPress sites** managed via `sites.json`.

## Adding Sites

### Interactive Method

```bash
./configure.sh --sites
```

Select **"A. Add New Site"** and provide:

| Field | Description | Example |
|-------|-------------|---------|
| Site Name | Unique identifier | `zimpricecheck` |
| wp-config.php path | Full path to config file | `/var/www/site.com/wp-config.php` |
| wp-content path | Full path to content dir | `/var/www/site.com/htdocs/wp-content` |
| DB Host | Database host (optional) | `localhost` |
| DB Name | Database name (optional) | Leave blank to auto-detect |
| DB User | Database user (optional) | Leave blank to auto-detect |
| DB Password | Database password (optional) | Leave blank to auto-detect |

> **Note**: If database credentials are left blank, they will be automatically extracted from `wp-config.php`.

### Manual Method

Edit `sites.json` directly:

```json
{
  "sites": [
    {
      "name": "zimpricecheck",
      "wp_config_path": "/var/www/zimpricecheck.com/wp-config.php",
      "wp_content_path": "/var/www/zimpricecheck.com/htdocs/wp-content",
      "db_host": "",
      "db_name": "",
      "db_user": "",
      "db_password": ""
    },
    {
      "name": "another-site",
      "wp_config_path": "/var/www/another.com/wp-config.php",
      "wp_content_path": "/var/www/another.com/htdocs/wp-content",
      "db_host": "localhost",
      "db_name": "another_db",
      "db_user": "dbuser",
      "db_password": "dbpass"
    }
  ]
}
```

## Removing Sites

```bash
./configure.sh --sites
```

Select **"R. Remove Site"** and enter the site number.

## Site Name Convention

The site name is used for:

1. **Archive naming**: `{site_name}-backup-{timestamp}.tar.zst`
2. **Database tracking**: `site_name` column in logs
3. **Log messages**: `[site_name] [STATUS] message`

Choose descriptive, URL-safe names (lowercase, hyphens allowed).

## Listing Sites

View currently configured sites:

```bash
./configure.sh --sites
```

Output:
```
--- Manage WordPress Sites (2 configured) ---
 1. zimpricecheck (/var/www/zimpricecheck.com/wp-config.php)
 2. another-site (/var/www/another.com/wp-config.php)
```

## Migration from Single-Site

If you have an existing `.env` with `WP_CONFIG_PATH` (legacy single-site format), running `./configure.sh` will automatically:

1. Create `sites.json`
2. Add a "default" site using the legacy paths
3. Display a migration notice

## File Location

- **Local development**: `./sites.json`
- **Remote server**: `/opt/wordpress-backup/sites.json`

> **Security**: `sites.json` is in `.gitignore` — credentials are never committed.
