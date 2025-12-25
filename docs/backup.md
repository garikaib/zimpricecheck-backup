# Backup Operations

The `run.sh` script controls backup execution.

## Usage

```bash
./run.sh [OPTIONS]
```

## Command Line Options

| Flag | Description |
|------|-------------|
| (no flags) | Run backup in background |
| `-f`, `--foreground` | Run backup in foreground (see output) |
| `--db-sync` | Manually trigger Cloudflare D1 synchronization |
| `--dry-run` | Simulate backup without making changes |
| `--check` | Check status of running backup |

## Examples

### Standard Backup (Background)

```bash
./run.sh
```
Starts backup in background. Email notification sent on completion.

### Foreground Backup (Debug)

```bash
./run.sh -f
```
Runs backup with full output visible. Useful for troubleshooting.

### Manual D1 Sync

```bash
./run.sh --db-sync
```
Forces synchronization between local SQLite and Cloudflare D1.

### Dry Run

```bash
./run.sh --dry-run
```
Tests configuration without creating actual backups.

## Backup Process

For each site in `sites.json`:

1. **Database Backup** — `mysqldump` with `--add-drop-table`
2. **Config Backup** — Copies `wp-config.php`
3. **Content Archive** — Tars `wp-content` (excludes cache)
4. **Compression** — Creates `{site}-backup-{timestamp}.tar.zst`
5. **Upload** — Sends to Mega.nz
6. **Logging** — Records to local DB and D1

## Archive Contents

Each archive contains:

```
{site}-backup-20241225-053000.tar.zst
├── database.sql       # Full MySQL dump
├── wp-config.php      # WordPress configuration
└── wp-content.tar     # Themes, plugins, uploads
```

## Archive Naming

Format: `{site_name}-backup-{YYYYMMDD}-{HHMMSS}.tar.zst`

Example: `zimpricecheck-backup-20241225-053000.tar.zst`

## Excluded from wp-content

- `cache/`
- `w3tc-config/`
- `uploads/cache/`
- `node_modules/`
- `.git/`
- `debug.log`

## Automatic Scheduling

Backups run automatically via systemd timer based on `BACKUP_FREQUENCY`:

| Frequency | Schedule |
|-----------|----------|
| `daily` | Once at `BACKUP_TIME` |
| `twice` | Midnight and noon |
| `every-6h` | 00:00, 06:00, 12:00, 18:00 |
| `every-2h` | Every 2 hours |

Check timer status:
```bash
systemctl list-timers wordpress-backup.timer
```

## Restore Procedure

```bash
# 1. Download or locate archive
# 2. Extract
mkdir restore && cd restore
zstd -d {site}-backup-{timestamp}.tar.zst
tar -xf {site}-backup-{timestamp}.tar

# 3. Restore database
mysql -u user -p database < database.sql

# 4. Restore wp-config.php
cp wp-config.php /var/www/site.com/

# 5. Restore wp-content
tar -xf wp-content.tar -C /var/www/site.com/htdocs/
chown -R www-data:www-data /var/www/site.com/htdocs/wp-content
```
