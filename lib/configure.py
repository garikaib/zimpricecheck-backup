#!/usr/bin/env python3
"""
WordPress Backup Configuration Wizard

Interactive setup for WordPress backup system including:
- WordPress paths
- MariaDB credentials (optional - can auto-extract from wp-config.php)
- Mega.nz accounts (up to 3)
- SMTP settings
- Systemd timer generation
- Cloudflare D1
"""

import os
import sys
import sqlite3
import argparse
from dotenv import dotenv_values

# Default env path is one level up from lib/
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

def prompt(label, default=None, required=True):
    """Prompt user for input with optional default value."""
    if default:
        val = input(f"{label} [{default}]: ").strip()
        return val if val else default
    else:
        while True:
            val = input(f"{label}: ").strip()
            if val or not required:
                return val
            print("  This field is required.")


def prompt_yes_no(label, default=True):
    """Prompt for yes/no response."""
    default_str = "Y/n" if default else "y/N"
    val = input(f"{label} [{default_str}]: ").strip().lower()
    if not val:
        return default
    return val in ('y', 'yes')


def load_config():
    """Load existing .env file."""
    if os.path.exists(ENV_PATH):
        return dotenv_values(ENV_PATH)
    return {}


def get_def(config, key, fallback=""):
    return config.get(key, fallback)


def configure_paths(config):
    print("\n--- WordPress Paths ---")
    config["WP_CONFIG_PATH"] = prompt("wp-config.php path", get_def(config, "WP_CONFIG_PATH", "/var/www/zimpricecheck.com/wp-config.php"))
    config["WP_CONTENT_PATH"] = prompt("wp-content directory", get_def(config, "WP_CONTENT_PATH", "/var/www/zimpricecheck.com/htdocs/wp-content"))
    config["WP_TEMP_DIR"] = prompt("Temp directory (for work files)", get_def(config, "WP_TEMP_DIR", "/var/tmp/wp-backup-work"))
    return config


def configure_db(config):
    print("\n--- MariaDB Configuration ---")
    print("Leave blank to auto-extract from wp-config.php")
    config["DB_HOST"] = prompt("Database Host", get_def(config, "DB_HOST", ""), required=False)
    config["DB_NAME"] = prompt("Database Name", get_def(config, "DB_NAME", ""), required=False)
    config["DB_USER"] = prompt("Database User", get_def(config, "DB_USER", ""), required=False)
    config["DB_PASSWORD"] = prompt("Database Password", get_def(config, "DB_PASSWORD", ""), required=False)
    return config


def configure_mega(config):
    print("\n--- Mega.nz Cloud Storage ---")
    print("Primary account is required. Up to 3 accounts supported.")
    
    config["MEGA_EMAIL_1"] = prompt("Primary Mega Email", get_def(config, "MEGA_EMAIL_1", "garikai@zimpricecheck.com"))
    config["MEGA_PASSWORD_1"] = prompt("Primary Mega Password", get_def(config, "MEGA_PASSWORD_1", ""))
    
    # Check for existing secondary credentials to offer as defaults
    has_sec = bool(get_def(config, "MEGA_EMAIL_2", ""))
    
    if prompt_yes_no("Add secondary Mega account?", has_sec):
        config["MEGA_EMAIL_2"] = prompt("Secondary Mega Email", get_def(config, "MEGA_EMAIL_2", ""), required=False)
        config["MEGA_PASSWORD_2"] = prompt("Secondary Mega Password", get_def(config, "MEGA_PASSWORD_2", ""), required=False)
        
        has_ter = bool(get_def(config, "MEGA_EMAIL_3", ""))
        if (config.get("MEGA_EMAIL_2") and prompt_yes_no("Add tertiary Mega account?", has_ter)):
            config["MEGA_EMAIL_3"] = prompt("Tertiary Mega Email", get_def(config, "MEGA_EMAIL_3", ""), required=False)
            config["MEGA_PASSWORD_3"] = prompt("Tertiary Mega Password", get_def(config, "MEGA_PASSWORD_3", ""), required=False)
    
    config["MEGA_STORAGE_LIMIT_GB"] = prompt("Mega Storage Limit (GB)", get_def(config, "MEGA_STORAGE_LIMIT_GB", "19.5"))
    return config


def configure_email(config):
    print("\n--- SMTP Email Configuration ---")
    config["SMTP_SERVER"] = prompt("SMTP Server", get_def(config, "SMTP_SERVER", "smtp-pulse.com"))
    config["SMTP_PORT"] = prompt("SMTP Port", get_def(config, "SMTP_PORT", "587"))
    config["SMTP_USER"] = prompt("SMTP Username/Email", get_def(config, "SMTP_USER", ""))
    config["SMTP_PASSWORD"] = prompt("SMTP Password", get_def(config, "SMTP_PASSWORD", ""))
    config["SMTP_SENDER_EMAIL"] = prompt("Sender Email", get_def(config, "SMTP_SENDER_EMAIL", "business@zimpricecheck.com"))
    return config


def configure_backup(config):
    print("\n--- Backup Settings ---")
    config["BACKUP_DIR"] = prompt("Backup Directory", get_def(config, "BACKUP_DIR", "/opt/wordpress-backup/backups"))
    
    print("\nBackup Frequency Options:")
    print("  1. daily     - Once per day at midnight (Africa/Harare)")
    print("  2. twice     - Twice per day (midnight and noon)")
    print("  3. every-6h  - Every 6 hours")
    print("  4. every-2h  - Every 2 hours")
    
    current = get_def(config, "BACKUP_FREQUENCY", "daily")
    # map back to option?
    inv_map = {"daily": "1", "twice": "2", "every-6h": "3", "every-2h": "4"}
    def_opt = inv_map.get(current, "1")
    
    freq_option = prompt("Backup Frequency (1-4)", def_opt)
    freq_map = {"1": "daily", "2": "twice", "3": "every-6h", "4": "every-2h"}
    config["BACKUP_FREQUENCY"] = freq_map.get(freq_option, "daily")
    
    config["BACKUP_TIME"] = prompt("Backup Time (HH:MM, Africa/Harare)", get_def(config, "BACKUP_TIME", "00:00"))
    
    print("\n--- Retention Settings ---")
    config["RETENTION_LOCAL_DAYS"] = prompt("Local Retention (Days)", get_def(config, "RETENTION_LOCAL_DAYS", "2"))
    config["RETENTION_MEGA_DAYS"] = prompt("Mega Retention (Days)", get_def(config, "RETENTION_MEGA_DAYS", "7"))
    return config


def configure_cloudflare(config):
    print("\n--- Cloudflare D1 Configuration ---")
    print("Sync backup logs with Cloudflare D1.")
    config["CLOUDFLARE_ACCOUNT_ID"] = prompt("Cloudflare Account ID", get_def(config, "CLOUDFLARE_ACCOUNT_ID", ""), required=False)
    config["CLOUDFLARE_API_TOKEN"] = prompt("Cloudflare API Token", get_def(config, "CLOUDFLARE_API_TOKEN", ""), required=False)
    config["CLOUDFLARE_D1_DATABASE_ID"] = prompt("D1 Database ID", get_def(config, "CLOUDFLARE_D1_DATABASE_ID", ""), required=False)
    return config


def save_config(config):
    # Sort keys for consistent output or group them? 
    # For now, just dumping them.
    # We can try to format it nicely.
    
    output = []
    
    output.append("# WordPress Paths")
    output.append(f'WP_CONFIG_PATH="{config.get("WP_CONFIG_PATH", "")}"')
    output.append(f'WP_CONTENT_PATH="{config.get("WP_CONTENT_PATH", "")}"')
    output.append(f'WP_TEMP_DIR="{config.get("WP_TEMP_DIR", "")}"')
    output.append("")
    
    output.append("# MariaDB")
    output.append(f'DB_HOST="{config.get("DB_HOST", "")}"')
    output.append(f'DB_NAME="{config.get("DB_NAME", "")}"')
    output.append(f'DB_USER="{config.get("DB_USER", "")}"')
    output.append(f'DB_PASSWORD="{config.get("DB_PASSWORD", "")}"')
    output.append("")
    
    output.append("# Mega Accounts")
    output.append(f'MEGA_EMAIL_1="{config.get("MEGA_EMAIL_1", "")}"')
    output.append(f'MEGA_PASSWORD_1="{config.get("MEGA_PASSWORD_1", "")}"')
    output.append(f'MEGA_EMAIL_2="{config.get("MEGA_EMAIL_2", "")}"')
    output.append(f'MEGA_PASSWORD_2="{config.get("MEGA_PASSWORD_2", "")}"')
    output.append(f'MEGA_EMAIL_3="{config.get("MEGA_EMAIL_3", "")}"')
    output.append(f'MEGA_PASSWORD_3="{config.get("MEGA_PASSWORD_3", "")}"')
    output.append(f'MEGA_STORAGE_LIMIT_GB={config.get("MEGA_STORAGE_LIMIT_GB", "19.5")}')
    output.append("")
    
    output.append("# SMTP")
    output.append(f'SMTP_SERVER="{config.get("SMTP_SERVER", "")}"')
    output.append(f'SMTP_PORT="{config.get("SMTP_PORT", "")}"')
    output.append(f'SMTP_USER="{config.get("SMTP_USER", "")}"')
    output.append(f'SMTP_PASSWORD="{config.get("SMTP_PASSWORD", "")}"')
    output.append(f'SMTP_SENDER_EMAIL="{config.get("SMTP_SENDER_EMAIL", "")}"')
    output.append("")
    
    output.append("# Backup Settings")
    output.append(f'BACKUP_DIR="{config.get("BACKUP_DIR", "")}"')
    output.append(f'BACKUP_FREQUENCY="{config.get("BACKUP_FREQUENCY", "daily")}"')
    output.append(f'BACKUP_TIME="{config.get("BACKUP_TIME", "00:00")}"')
    output.append(f'RETENTION_LOCAL_DAYS={config.get("RETENTION_LOCAL_DAYS", "2")}')
    output.append(f'RETENTION_MEGA_DAYS={config.get("RETENTION_MEGA_DAYS", "7")}')
    output.append("")
    
    output.append("# Cloudflare D1")
    output.append(f'CLOUDFLARE_ACCOUNT_ID="{config.get("CLOUDFLARE_ACCOUNT_ID", "")}"')
    output.append(f'CLOUDFLARE_API_TOKEN="{config.get("CLOUDFLARE_API_TOKEN", "")}"')
    output.append(f'CLOUDFLARE_D1_DATABASE_ID="{config.get("CLOUDFLARE_D1_DATABASE_ID", "")}"')
    
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(output))
    print(f"\n[+] Configuration saved to {ENV_PATH}")


def generate_systemd(config):
    print("\n--- Generating Systemd Service Files ---")
    
    
    install_path = os.getcwd()
    
    # Write to systemd/ directory relative to here
    systemd_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "systemd")
    os.makedirs(systemd_dir, exist_ok=True)
    
    # Backup service
    service_content = f"""[Unit]
Description=WordPress Backup Service
After=network.target

[Service]
Type=simple
User=ubuntu
Environment="TZ=Africa/Harare"
WorkingDirectory={install_path}
ExecStart={install_path}/venv/bin/python3 {install_path}/lib/backup_manager.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""

    backup_freq = config.get("BACKUP_FREQUENCY", "daily")
    backup_time = config.get("BACKUP_TIME", "00:00")
    
    # Timer based on frequency
    if backup_freq == "daily":
        timer_schedule = f"*-*-* {backup_time}:00"
    elif backup_freq == "twice":
        timer_schedule = "*-*-* 00,12:00:00"
    elif backup_freq == "every-6h":
        timer_schedule = "*-*-* 00,06,12,18:00:00"
    else:  # every-2h
        timer_schedule = "*-*-* 00,02,04,06,08,10,12,14,16,18,20,22:00:00"
    
    timer_content = f"""[Unit]
Description=WordPress Backup Timer

[Timer]
OnCalendar={timer_schedule}
Persistent=true
Unit=wordpress-backup.service

[Install]
WantedBy=timers.target
"""

    # Report service
    report_service = f"""[Unit]
Description=WordPress Backup Daily Report
After=network.target

[Service]
Type=simple
User=ubuntu
Environment="TZ=Africa/Harare"
WorkingDirectory={install_path}
ExecStart={install_path}/venv/bin/python3 {install_path}/lib/report_manager.py
Restart=on-failure
"""

    # Report timer - 08:00 AM daily
    report_timer = """[Unit]
Description=WordPress Backup Daily Report Timer

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true
Unit=wordpress-report.service

[Install]
WantedBy=timers.target
"""

    with open(os.path.join(systemd_dir, "wordpress-backup.service"), "w") as f:
        f.write(service_content)
    
    with open(os.path.join(systemd_dir, "wordpress-backup.timer"), "w") as f:
        f.write(timer_content)
    
    with open(os.path.join(systemd_dir, "wordpress-report.service"), "w") as f:
        f.write(report_service)
    
    with open(os.path.join(systemd_dir, "wordpress-report.timer"), "w") as f:
        f.write(report_timer)
    
    print(f"[+] Created systemd service files in {systemd_dir}")


def init_db():
    print("\n[*] Initializing SQLite database...")
    db_file = os.path.join(os.path.dirname(ENV_PATH), "backups.db")
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS backup_log
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
                      status TEXT, 
                      details TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS mega_archives
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      filename TEXT NOT NULL,
                      mega_account TEXT NOT NULL,
                      file_size INTEGER,
                      upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS daily_emails
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT NOT NULL UNIQUE,
                      email_sent INTEGER DEFAULT 0,
                      backup_count INTEGER DEFAULT 0)''')
        
        conn.commit()
        conn.close()
        print(f"[+] SQLite database initialized at {db_file}")
    except Exception as e:
        print(f"[-] Failed to init database: {e}")


def main():
    print("=" * 60)
    print("       WordPress Backup Configuration Wizard")
    print("=" * 60)

    parser = argparse.ArgumentParser(description="Configure WordPress Backup")
    parser.add_argument("--paths", action="store_true", help="Configure WordPress paths")
    parser.add_argument("--db", action="store_true", help="Configure Database settings")
    parser.add_argument("--mega", action="store_true", help="Configure Mega.nz accounts")
    parser.add_argument("--email", action="store_true", help="Configure SMTP email")
    parser.add_argument("--backup", action="store_true", help="Configure Backup scheduling/retention")
    parser.add_argument("--cloudflare", action="store_true", help="Configure Cloudflare D1")
    parser.add_argument("--all", action="store_true", help="Configure all settings (default)")
    parser.add_argument("--systemd", action="store_true", help="Generate systemd service files (use on remote server)")
    
    args = parser.parse_args()
    
    # If no specific flags (other than systemd), default to all
    if not any([args.paths, args.db, args.mega, args.email, args.backup, args.cloudflare]) and not args.systemd:
        args.all = True

    config = load_config()

    if args.all or args.paths:
        config = configure_paths(config)
    
    if args.all or args.db:
        config = configure_db(config)
    
    if args.all or args.mega:
        config = configure_mega(config)
    
    if args.all or args.email:
        config = configure_email(config)
    
    if args.all or args.backup:
        config = configure_backup(config)
        
    if args.all or args.cloudflare:
        config = configure_cloudflare(config)

    save_config(config)
    
    # Only regenerate systemd files if requested
    if args.systemd:
        generate_systemd(config)
    
    # Always init db to be safe
    init_db()

    print("\nConfiguration Complete.")
    if args.systemd:
        print("To install systemd services:")
        print("  sudo cp systemd/* /etc/systemd/system/")
        print("  sudo systemctl daemon-reload")
        print("  sudo systemctl enable --now wordpress-backup.timer")

if __name__ == "__main__":
    main()
