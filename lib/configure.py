#!/usr/bin/env python3
"""
WordPress Backup Configuration Wizard (Multi-Site SaaS Edition)

Interactive setup for:
- Multiple WordPress Sites (sites.json)
- Remote Deployment Settings (SSH)
- Global Credentials (Mega, Cloudflare, SMTP) - stored in .env
"""

import os
import sys
import sqlite3
import argparse
import json
from dotenv import dotenv_values

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
SITES_PATH = os.path.join(BASE_DIR, "sites.json")

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

# --- Config Management ---

def load_env():
    """Load existing .env file."""
    if os.path.exists(ENV_PATH):
        return dotenv_values(ENV_PATH)
    return {}

def save_env(config):
    """Save dictionary to .env file."""
    lines = []
    for key, val in config.items():
        if val is None: val = ""
        lines.append(f'{key}="{val}"')
    
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[+] Global configuration saved to {ENV_PATH}")

def load_sites():
    """Load sites from sites.json."""
    if os.path.exists(SITES_PATH):
        try:
            with open(SITES_PATH, "r") as f:
                data = json.load(f)
                return data.get("sites", [])
        except json.JSONDecodeError:
            print("[-] Error decoding sites.json. Starting fresh.")
    return []

def save_sites(sites):
    """Save sites list to sites.json."""
    with open(SITES_PATH, "w") as f:
        json.dump({"sites": sites}, f, indent=2)
    print(f"[+] Sites saved to {SITES_PATH}")

def get_def(config, key, fallback=""):
    return config.get(key, fallback)

# --- Configuration Sections ---

def configure_global_backup(config):
    print("\n--- Global Backup Settings ---")
    config["BACKUP_DIR"] = prompt("Backup Directory", get_def(config, "BACKUP_DIR", "/opt/wordpress-backup/backups"))
    
    print("\nBackup Frequency Options:")
    print("  1. daily     - Once per day at midnight")
    print("  2. twice     - Twice per day (noon/midnight)")
    print("  3. every-6h  - Every 6 hours")
    print("  4. every-2h  - Every 2 hours")
    
    current = get_def(config, "BACKUP_FREQUENCY", "daily")
    inv_map = {"daily": "1", "twice": "2", "every-6h": "3", "every-2h": "4"}
    def_opt = inv_map.get(current, "1")
    
    freq_opt = prompt("Backup Frequency (1-4)", def_opt)
    freq_map = {"1": "daily", "2": "twice", "3": "every-6h", "4": "every-2h"}
    config["BACKUP_FREQUENCY"] = freq_map.get(freq_opt, "daily")
    config["BACKUP_TIME"] = prompt("Backup Time (HH:MM)", get_def(config, "BACKUP_TIME", "00:00"))
    
    config["RETENTION_LOCAL_DAYS"] = prompt("Local Retention (Days)", get_def(config, "RETENTION_LOCAL_DAYS", "2"))
    config["RETENTION_MEGA_DAYS"] = prompt("Mega Retention (Days)", get_def(config, "RETENTION_MEGA_DAYS", "7"))
    return config

def configure_mega(config):
    print("\n--- Mega.nz Cloud Storage ---")
    config["MEGA_EMAIL_1"] = prompt("Primary Email", get_def(config, "MEGA_EMAIL_1", ""))
    config["MEGA_PASSWORD_1"] = prompt("Primary Password", get_def(config, "MEGA_PASSWORD_1", ""))
    config["MEGA_STORAGE_LIMIT_GB"] = prompt("Storage Limit (GB)", get_def(config, "MEGA_STORAGE_LIMIT_GB", "19.5"))
    return config

def configure_email(config):
    print("\n--- SMTP Email ---")
    config["SMTP_SERVER"] = prompt("SMTP Server", get_def(config, "SMTP_SERVER", "smtp-pulse.com"))
    config["SMTP_PORT"] = prompt("SMTP Port", get_def(config, "SMTP_PORT", "587"))
    config["SMTP_USER"] = prompt("SMTP User", get_def(config, "SMTP_USER", ""))
    config["SMTP_PASSWORD"] = prompt("SMTP Password", get_def(config, "SMTP_PASSWORD", ""))
    config["SMTP_SENDER_EMAIL"] = prompt("Sender Email", get_def(config, "SMTP_SENDER_EMAIL", "backup@example.com"))
    return config

def configure_cloudflare(config):
    print("\n--- Cloudflare D1 ---")
    config["CLOUDFLARE_ACCOUNT_ID"] = prompt("Account ID", get_def(config, "CLOUDFLARE_ACCOUNT_ID", ""), required=False)
    config["CLOUDFLARE_API_TOKEN"] = prompt("API Token", get_def(config, "CLOUDFLARE_API_TOKEN", ""), required=False)
    config["CLOUDFLARE_D1_DATABASE_ID"] = prompt("Database ID", get_def(config, "CLOUDFLARE_D1_DATABASE_ID", ""), required=False)
    return config

def configure_deployment(config):
    print("\n--- Remote Deployment Settings ---")
    print("These settings are used by deploy.sh")
    config["REMOTE_HOST"] = prompt("Remote Host (IP or domain)", get_def(config, "REMOTE_HOST", "wp.zimpricecheck.com"))
    config["REMOTE_USER"] = prompt("Remote SSH User", get_def(config, "REMOTE_USER", "ubuntu"))
    config["REMOTE_PORT"] = prompt("Remote SSH Port", get_def(config, "REMOTE_PORT", "22"))
    config["REMOTE_DIR"] = prompt("Remote Install Dir", get_def(config, "REMOTE_DIR", "/opt/wordpress-backup"))
    return config

# --- Site Management ---

def configure_site_wizard(existing_site=None):
    """Wizard to add or edit a site."""
    site = existing_site or {}
    print("\n--- Configure Site ---")
    
    # If editing, name is fixed (or separate logic), here we assume name is unique ID
    name = prompt("Site Name (unique ID)", site.get("name"), required=True)
    
    # WP Config
    wp_config = prompt("wp-config.php path", site.get("wp_config_path", "/var/www/html/wp-config.php"))
    wp_content = prompt("wp-content directory", site.get("wp_content_path", "/var/www/html/wp-content"))
    
    # DB (Optional)
    print("Database Settings (Leave blank to auto-detect from wp-config.php)")
    db_host = prompt("DB Host", site.get("db_host", ""), required=False)
    db_name = prompt("DB Name", site.get("db_name", ""), required=False)
    db_user = prompt("DB User", site.get("db_user", ""), required=False)
    db_password = prompt("DB Password", site.get("db_password", ""), required=False)
    
    return {
        "name": name,
        "wp_config_path": wp_config,
        "wp_content_path": wp_content,
        "db_host": db_host,
        "db_name": db_name,
        "db_user": db_user,
        "db_password": db_password
    }

def manage_sites():
    sites = load_sites()
    while True:
        print(f"\n--- Manage WordPress Sites ({len(sites)} configured) ---")
        for idx, site in enumerate(sites):
            print(f" {idx+1}. {site['name']} ({site['wp_config_path']})")
        print(" A. Add New Site")
        print(" R. Remove Site")
        print(" B. Back to Main Menu")
        
        choice = input("Choice: ").strip().lower()
        
        if choice == 'a':
            new_site = configure_site_wizard()
            # Remove existing if same name
            sites = [s for s in sites if s['name'] != new_site['name']]
            sites.append(new_site)
            save_sites(sites)
        elif choice == 'r':
            if not sites:
                print("No sites to remove.")
                continue
            idx = input("Enter number to remove: ")
            try:
                idx = int(idx) - 1
                if 0 <= idx < len(sites):
                    rem = sites.pop(idx)
                    print(f"Removed {rem['name']}")
                    save_sites(sites)
                else:
                    print("Invalid index.")
            except ValueError:
                print("Invalid input.")
        elif choice == 'b':
            break

# --- Migration ---

def migrate_legacy_env():
    """Migrate legacy single-site .env config to sites.json."""
    config = load_env()
    sites = load_sites()
    
    # Check if we have legacy WP_CONFIG_PATH in .env
    if "WP_CONFIG_PATH" in config and not sites:
        print("[!] Detected legacy single-site configuration. Migrating to sites.json...")
        site = {
            "name": "default",
            "wp_config_path": config.get("WP_CONFIG_PATH"),
            "wp_content_path": config.get("WP_CONTENT_PATH"),
            "db_host": config.get("DB_HOST", ""),
            "db_name": config.get("DB_NAME", ""),
            "db_user": config.get("DB_USER", ""),
            "db_password": config.get("DB_PASSWORD", "")
        }
        sites.append(site)
        save_sites(sites)
        
        # Cleanup legacy keys from env config dict (not strictly necessary to delete from file, but cleaner)
        # We won't delete them from file automatically to be safe, but we won't use them anymore.
        print("[+] Migration complete. 'default' site added.")

# --- Systemd ---

def generate_systemd(config):
    print("\n--- Generating Systemd Service Files ---")
    install_path = os.getcwd()
    systemd_dir = os.path.join(BASE_DIR, "systemd")
    os.makedirs(systemd_dir, exist_ok=True)
    
    # Same service content, backup_manager handles looping internally
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
    # ... (Timer logic same as before) ...
    backup_freq = config.get("BACKUP_FREQUENCY", "daily")
    backup_time = config.get("BACKUP_TIME", "00:00")
    
    if backup_freq == "daily": schedule = f"*-*-* {backup_time}:00"
    elif backup_freq == "twice": schedule = "*-*-* 00,12:00:00"
    elif backup_freq == "every-6h": schedule = "*-*-* 00,06,12,18:00:00"
    else: schedule = "*-*-* 00,02,04,06,08,10,12,14,16,18,20,22:00:00"

    timer_content = f"""[Unit]
Description=WordPress Backup Timer

[Timer]
OnCalendar={schedule}
Persistent=true
Unit=wordpress-backup.service

[Install]
WantedBy=timers.target
"""
    # Write files...
    with open(os.path.join(systemd_dir, "wordpress-backup.service"), "w") as f: f.write(service_content)
    with open(os.path.join(systemd_dir, "wordpress-backup.timer"), "w") as f: f.write(timer_content)
    
    # Report service (No changes needed usually)
    report_service = f"""[Unit]
Description=WordPress Backup Report
After=network.target

[Service]
Type=simple
User=ubuntu
Environment="TZ=Africa/Harare"
WorkingDirectory={install_path}
ExecStart={install_path}/venv/bin/python3 {install_path}/lib/report_manager.py
Restart=on-failure
"""
    report_timer = """[Unit]
Description=WordPress Backup Report Timer
[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true
Unit=wordpress-report.service
[Install]
WantedBy=timers.target
"""
    with open(os.path.join(systemd_dir, "wordpress-report.service"), "w") as f: f.write(report_service)
    with open(os.path.join(systemd_dir, "wordpress-report.timer"), "w") as f: f.write(report_timer)
    
    print(f"[+] Files created in {systemd_dir}")

def init_db():
    print("\n[*] Initializing SQLite database...")
    db_file = os.path.join(BASE_DIR, "backups.db")
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        
        # Add site_name if missing (Migration handled by simple CREATE logic + Alter check)
        c.execute('''CREATE TABLE IF NOT EXISTS backup_log
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
                      status TEXT, 
                      details TEXT,
                      site_name TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS mega_archives
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      filename TEXT NOT NULL,
                      mega_account TEXT NOT NULL,
                      file_size INTEGER,
                      upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                      site_name TEXT)''')
                      
        c.execute('''CREATE TABLE IF NOT EXISTS daily_emails
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT NOT NULL UNIQUE,
                      email_sent INTEGER DEFAULT 0,
                      backup_count INTEGER DEFAULT 0)''')
        
        # Migration for existing tables without site_name
        for table in ['backup_log', 'mega_archives']:
            try:
                c.execute(f"ALTER TABLE {table} ADD COLUMN site_name TEXT")
                print(f"[+] Added site_name column to {table}")
            except sqlite3.OperationalError:
                pass
                
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[-] DB Init Error: {e}")

# --- Main Menu ---

def main():
    parser = argparse.ArgumentParser(description="Multi-Site Backup Config")
    parser.add_argument("--systemd", action="store_true", help="Generate systemd files")
    parser.add_argument("--sites", action="store_true", help="Manage sites")
    parser.add_argument("--deploy", action="store_true", help="Configure deployment")
    parser.add_argument("--env", action="store_true", help="Configure global .env")
    
    args = parser.parse_args()
    
    # 1. Migration Check
    migrate_legacy_env()
    
    # 2. Automation Mode (Systemd generation)
    if args.systemd:
        config = load_env()
        generate_systemd(config)
        init_db()
        return

    # 3. Interactive Menu
    while True:
        print("\n" + "="*50)
        print("   Backup Configuration Wizard (SaaS Ready)")
        print("="*50)
        print(" 1. Manage WordPress Sites")
        print(" 2. Configure Global Credentials (Mega, Email, D1)")
        print(" 3. Configure Deployment Settings (SSH)")
        print(" 4. Configure Backup Schedule & Retention")
        print(" 5. Generate Systemd Files")
        print(" 0. Exit")
        
        if args.sites: choice = '1'
        elif args.env: choice = '2'
        elif args.deploy: choice = '3'
        else: choice = input("\nChoice: ").strip()
        
        config = load_env()
        
        if choice == '1':
            manage_sites()
            if args.sites: break
            
        elif choice == '2':
            config = configure_mega(config)
            config = configure_email(config)
            config = configure_cloudflare(config)
            save_env(config)
            if args.env: break
            
        elif choice == '3':
            config = configure_deployment(config)
            save_env(config)
            if args.deploy: break
            
        elif choice == '4':
            config = configure_global_backup(config)
            save_env(config)
            
        elif choice == '5':
            generate_systemd(config)
            init_db()
            
        elif choice == '0':
            break
        else:
            print("Invalid choice.")
            
    print("\n[+] Verification: Run ./run.sh --dry-run")

if __name__ == "__main__":
    main()
