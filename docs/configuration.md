# Configuration Reference

The `configure.sh` script provides an intelligent wizard that adapts to your environment.

## Environment Detection

The wizard automatically detects whether you're on a **local workstation** or a **remote server**:

- **Local**: Has no `/var/www/` directory with websites
- **Remote**: Has `/var/www/` with WordPress installations

## Local Workflow

When run locally (development machine):

```
./configure.sh
```

### Flow:
1. **Deployment Target** (Required on first run)
   - REMOTE_HOST, REMOTE_USER, REMOTE_PORT, REMOTE_DIR

2. **Optional Sections** (Y/N/S for each):
   - S3 Storage
   - SMTP Email
   - Cloudflare D1
   - Backup Settings
   
   > **S = Skip**: Immediately triggers deployment

3. **Deploy?** (Y/N)

## Remote Workflow

When run on a server (after deployment):

```
./configure.sh
```

### Flow:
1. **Auto-Detect WordPress Sites**
   - Scans `/var/www/` for installations
   - Displays found sites
   - Asks which to back up (Y/N for each)

2. **Validation**:
   | Check | Level | Result |
   |-------|-------|--------|
   | Sites ≥ 1 | CRITICAL | Exit if none |
   | S3 configured | WARNING | "Local backups only" |
   | SMTP configured | WARNING | "No email alerts" |
   | D1 configured | INFO | "Local logs only" |

3. **Generate Systemd Files**

## Command Line Options

| Flag | Description |
|------|-------------|
| `--detect` | Auto-detect and select WordPress sites |
| `--validate` | Run validation checks only |
| `--systemd` | Generate systemd files only |
| `--sites` | Manual site management |

## Detection Paths

WordPress sites are searched in:
- `/var/www/*/wp-config.php`
- `/var/www/*/htdocs/wp-config.php`
- `/var/www/*/public_html/wp-config.php`
- `/home/*/public_html/wp-config.php`

## Shared Storage (SERVER_ID)

When multiple servers share the same S3 storage:

```
SERVER_ID="server1"
```

Archives are stored at: `/{SERVER_ID}/{Year}/{Month}/{Day}/`

This prevents filename conflicts and allows proper retention per-server.

SERVER_ID is auto-generated from hostname on first remote run.

## Configuration Files

| File | Location | Purpose |
|------|----------|---------|
| `.env` | Project root | Global settings |
| `sites.json` | Project root | WordPress sites |

Both files are in `.gitignore` and should never be committed.
