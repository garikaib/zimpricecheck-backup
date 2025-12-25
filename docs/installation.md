# Installation Guide

## Requirements

- **Ubuntu Server** 22.04+ (other Linux distros may work)
- **Python 3.10+**
- **MariaDB/MySQL** client tools (`mysqldump`)
- **zstd** compression utility

## Local Setup

### 1. Clone Repository

```bash
git clone https://github.com/garikaib/zimpricecheck-backup.git
cd wordpress-backup
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run Configuration Wizard

```bash
./configure.sh
```

This launches an interactive menu to configure:
- WordPress sites
- S3 storage credentials
- SMTP email settings
- Cloudflare D1 sync
- Deployment target

### 4. Deploy to Remote Server

```bash
./deploy.sh
```

## Remote Server Requirements

The deploy script will automatically:
- Create `/opt/wordpress-backup` directory
- Set up Python virtual environment
- Install dependencies (including `boto3` for S3)
- Reset logs database for fresh start
- Configure systemd timers

## First Run

After deployment, verify the installation:

```bash
# Check timer status
systemctl status wordpress-backup.timer

# Run a test backup
cd /opt/wordpress-backup
./run.sh -f
```

## Updating

To update an existing installation:

```bash
# Locally
git pull
./deploy.sh
```

The deploy script preserves your `.env` and `sites.json` configurations.

> [!NOTE]
> Each deployment resets the `backups.db` log database. Historical data in Cloudflare D1 is preserved.
