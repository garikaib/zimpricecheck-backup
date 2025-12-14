#!/usr/bin/env python3
"""
WordPress Backup Configuration Wizard

Interactive setup for WordPress backup system including:
- WordPress paths
- MariaDB credentials (optional - can auto-extract from wp-config.php)
- Mega.nz accounts (up to 3)
- SMTP settings
- Systemd timer generation
"""

import os
import sys
import sqlite3


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


def load_existing_env():
    """Load existing .env file for defaults."""
    defaults = {}
    if os.path.exists(".env"):
        try:
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        key, val = line.split("=", 1)
                        # Remove quotes if present
                        val = val.strip('"').strip("'")
                        defaults[key] = val
        except Exception as e:
            print(f"[-] Failed to load existing .env: {e}")
    return defaults


def main():
    print("=" * 60)
    print("       WordPress Backup Configuration Wizard")
    print("=" * 60)
    print()
    
    # Load existing .env if present for defaults
    defaults = load_existing_env()
    
    def get_def(key, fallback=""):
        return defaults.get(key, fallback)
    
    # 1. WordPress Paths
    print("--- WordPress Paths ---")
    wp_config = prompt("wp-config.php path", get_def("WP_CONFIG_PATH", "/var/www/zimpricecheck.com/wp-config.php"))
    wp_content = prompt("wp-content directory", get_def("WP_CONTENT_PATH", "/var/www/zimpricecheck.com/htdocs/wp-content"))
    wp_temp = prompt("Temp directory (for work files)", get_def("WP_TEMP_DIR", "/var/tmp/wp-backup-work"))
    
    # 2. MariaDB Configuration
    print("\n--- MariaDB Configuration ---")
    print("Leave blank to auto-extract from wp-config.php")
    db_host = prompt("Database Host", get_def("DB_HOST", ""), required=False)
    db_name = prompt("Database Name", get_def("DB_NAME", ""), required=False)
    db_user = prompt("Database User", get_def("DB_USER", ""), required=False)
    db_pass = prompt("Database Password", get_def("DB_PASSWORD", ""), required=False)
    
    # 3. Mega.nz Accounts
    print("\n--- Mega.nz Cloud Storage ---")
    print("Primary account is required. Up to 3 accounts supported.")
    print("Storage limit: 19.5 GB per account (20GB - 500MB overhead)")
    
    mega_email_1 = prompt("Primary Mega Email", get_def("MEGA_EMAIL_1", "garikai@zimpricecheck.com"))
    mega_pass_1 = prompt("Primary Mega Password", get_def("MEGA_PASSWORD_1", ""))
    
    mega_email_2 = ""
    mega_pass_2 = ""
    mega_email_3 = ""
    mega_pass_3 = ""
    
    if prompt_yes_no("Add secondary Mega account?", False):
        mega_email_2 = prompt("Secondary Mega Email", get_def("MEGA_EMAIL_2", ""), required=False)
        mega_pass_2 = prompt("Secondary Mega Password", get_def("MEGA_PASSWORD_2", ""), required=False)
        
        if mega_email_2 and prompt_yes_no("Add tertiary Mega account?", False):
            mega_email_3 = prompt("Tertiary Mega Email", get_def("MEGA_EMAIL_3", ""), required=False)
            mega_pass_3 = prompt("Tertiary Mega Password", get_def("MEGA_PASSWORD_3", ""), required=False)
    
    mega_storage_limit = prompt("Mega Storage Limit (GB)", get_def("MEGA_STORAGE_LIMIT_GB", "19.5"))
    
    # 4. SMTP Configuration
    print("\n--- SMTP Email Configuration ---")
    smtp_server = prompt("SMTP Server", get_def("SMTP_SERVER", "smtp-pulse.com"))
    smtp_port = prompt("SMTP Port", get_def("SMTP_PORT", "587"))
    smtp_user = prompt("SMTP Username/Email", get_def("SMTP_USER", ""))
    smtp_pass = prompt("SMTP Password", get_def("SMTP_PASSWORD", ""))
    smtp_sender = prompt("Sender Email", get_def("SMTP_SENDER_EMAIL", "business@zimpricecheck.com"))
    
    # 5. Backup Settings
    print("\n--- Backup Settings ---")
    backup_dir = prompt("Backup Directory", get_def("BACKUP_DIR", "/opt/wordpress-backup/backups"))
    
    print("\nBackup Frequency Options:")
    print("  1. daily     - Once per day at midnight (Africa/Harare)")
    print("  2. twice     - Twice per day (midnight and noon)")
    print("  3. every-6h  - Every 6 hours")
    print("  4. every-2h  - Every 2 hours")
    
    freq_option = prompt("Backup Frequency (1-4)", "1")
    freq_map = {"1": "daily", "2": "twice", "3": "every-6h", "4": "every-2h"}
    backup_freq = freq_map.get(freq_option, "daily")
    
    backup_time = prompt("Backup Time (HH:MM, Africa/Harare)", get_def("BACKUP_TIME", "00:00"))
    
    # 6. Retention
    print("\n--- Retention Settings ---")
    retention_local = prompt("Local Retention (Days)", get_def("RETENTION_LOCAL_DAYS", "2"))
    retention_mega = prompt("Mega Retention (Days)", get_def("RETENTION_MEGA_DAYS", "7"))
    
    # Write .env file
    env_content = f"""# WordPress Paths
WP_CONFIG_PATH="{wp_config}"
WP_CONTENT_PATH="{wp_content}"
WP_TEMP_DIR="{wp_temp}"

# MariaDB - Leave empty to auto-extract from wp-config.php
DB_HOST="{db_host}"
DB_NAME="{db_name}"
DB_USER="{db_user}"
DB_PASSWORD="{db_pass}"

# Mega Accounts (Primary - required)
MEGA_EMAIL_1="{mega_email_1}"
MEGA_PASSWORD_1="{mega_pass_1}"

# Mega Account 2 (Optional)
MEGA_EMAIL_2="{mega_email_2}"
MEGA_PASSWORD_2="{mega_pass_2}"

# Mega Account 3 (Optional)
MEGA_EMAIL_3="{mega_email_3}"
MEGA_PASSWORD_3="{mega_pass_3}"

# Mega Storage Limit in GB (20GB - 500MB overhead = 19.5GB)
MEGA_STORAGE_LIMIT_GB={mega_storage_limit}

# SMTP Configuration
SMTP_SERVER="{smtp_server}"
SMTP_PORT="{smtp_port}"
SMTP_USER="{smtp_user}"
SMTP_PASSWORD="{smtp_pass}"
SMTP_SENDER_EMAIL="{smtp_sender}"

# Backup Settings
BACKUP_DIR="{backup_dir}"
BACKUP_FREQUENCY="{backup_freq}"
BACKUP_TIME="{backup_time}"

# Retention
RETENTION_LOCAL_DAYS={retention_local}
RETENTION_MEGA_DAYS={retention_mega}
"""

    with open(".env", "w") as f:
        f.write(env_content)
    print("\n[+] Created .env file.")
    
    # Generate systemd service files
    print("\n--- Generating Systemd Service Files ---")
    
    install_path = "/opt/wordpress-backup"
    
    # Backup service
    service_content = f"""[Unit]
Description=WordPress Backup Service
After=network.target

[Service]
Type=simple
User=ubuntu
Environment="TZ=Africa/Harare"
WorkingDirectory={install_path}
ExecStart={install_path}/venv/bin/python3 {install_path}/backup_manager.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""

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
ExecStart={install_path}/venv/bin/python3 {install_path}/report_manager.py
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

    with open("wordpress-backup.service", "w") as f:
        f.write(service_content)
    
    with open("wordpress-backup.timer", "w") as f:
        f.write(timer_content)
    
    with open("wordpress-report.service", "w") as f:
        f.write(report_service)
    
    with open("wordpress-report.timer", "w") as f:
        f.write(report_timer)
    
    print("[+] Created systemd service files.")
    
    # Initialize SQLite DB
    print("\n[*] Initializing SQLite database...")
    try:
        conn = sqlite3.connect("backups.db")
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
        print("[+] SQLite database initialized.")
    except Exception as e:
        print(f"[-] Failed to init database: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("                    SETUP COMPLETE")
    print("=" * 60)
    print()
    print("Mega Account(s) for backup storage:")
    print(f"  Primary: {mega_email_1}")
    if mega_email_2:
        print(f"  Secondary: {mega_email_2}")
    if mega_email_3:
        print(f"  Tertiary: {mega_email_3}")
    print()
    print(f"Backup Schedule: {backup_freq} at {backup_time} (Africa/Harare)")
    print(f"Timer Schedule: {timer_schedule}")
    print()
    print("To deploy to remote server, run:")
    print("  ./deploy.sh")
    print()
    print("To install systemd services manually:")
    print("  sudo cp wordpress-backup.service /etc/systemd/system/")
    print("  sudo cp wordpress-backup.timer /etc/systemd/system/")
    print("  sudo cp wordpress-report.service /etc/systemd/system/")
    print("  sudo cp wordpress-report.timer /etc/systemd/system/")
    print("  sudo systemctl daemon-reload")
    print("  sudo systemctl enable --now wordpress-backup.timer")
    print("  sudo systemctl enable --now wordpress-report.timer")


if __name__ == "__main__":
    main()
