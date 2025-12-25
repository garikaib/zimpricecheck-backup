#!/usr/bin/env python3
"""
WordPress Backup Configuration Wizard (SaaS Remote-First Edition)

- Local: Configure deployment target, optional credentials, then deploy
- Remote: Auto-detect sites, validate requirements, generate systemd
- Unified Config: Manages sites and S3 storage in config.json
"""

import os
import sys
import argparse
import json
import uuid
from dotenv import dotenv_values

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# Import site detector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from site_detector import detect_wordpress_sites, prompt_select_sites, is_remote_environment
except ImportError:
    def detect_wordpress_sites(): return []
    def prompt_select_sites(sites): return sites
    def is_remote_environment(): return os.path.isdir("/var/www")


def prompt(label, default=None, required=True):
    """Prompt user for input."""
    if default:
        val = input(f"{label} [{default}]: ").strip()
        return val if val else default
    else:
        while True:
            val = input(f"{label}: ").strip()
            if val or not required:
                return val
            print("  This field is required.")


def prompt_section(section_name):
    """Ask if user wants to configure a section. Returns: 'y', 'n', or 's' (skip to end)."""
    while True:
        choice = input(f"\nConfigure {section_name}? [Y/n/S=skip to end]: ").strip().lower()
        if choice in ('', 'y', 'yes'):
            return 'y'
        elif choice in ('n', 'no'):
            return 'n'
        elif choice == 's':
            return 's'
        print("  Please enter Y, N, or S")


# --- Config Management ---

def load_env():
    if os.path.exists(ENV_PATH):
        return dict(dotenv_values(ENV_PATH))
    return {}


def save_env(config):
    lines = []
    for key, val in config.items():
        if val is None:
            val = ""
        lines.append(f'{key}="{val}"')
    
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[+] Env configuration saved to {ENV_PATH}")


def load_config():
    """Load unified config.json."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except:
            pass
    return {"sites": [], "storage": []}


def save_config(config):
    """Save unified config.json."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    print(f"[+] Configuration saved to {CONFIG_PATH}")


def get_def(config, key, fallback=""):
    return config.get(key, fallback)


# --- Configuration Sections ---

def configure_deployment(env_config):
    print("\n--- Deployment Target ---")
    env_config["REMOTE_HOST"] = prompt("Remote Host (IP or domain)", get_def(env_config, "REMOTE_HOST", ""))
    env_config["REMOTE_USER"] = prompt("SSH User", get_def(env_config, "REMOTE_USER", "ubuntu"))
    env_config["REMOTE_PORT"] = prompt("SSH Port", get_def(env_config, "REMOTE_PORT", "22"))
    env_config["REMOTE_DIR"] = prompt("Install Directory", get_def(env_config, "REMOTE_DIR", "/opt/wordpress-backup"))
    return env_config


def configure_s3(json_config):
    """Configure S3-compatible storage servers in config.json."""
    print("\n--- S3 Storage ---")
    print("Configure S3-compatible storage (AWS S3, iDrive E2, Backblaze B2, etc.)")
    print("Supports multiple servers with weighted priority (higher weight = tried first).")
    
    storage_list = json_config.get("storage", [])
    
    # Display existing
    if storage_list:
        print("\nExisting Storage:")
        for idx, s in enumerate(storage_list):
            print(f"  {idx+1}. {s.get('name')} ({s.get('endpoint')}/{s.get('bucket')}) [Weight: {s.get('weight')}]")
        
        modify = input("\nAdd more servers? [y/N]: ").strip().lower()
        if modify != 'y':
            return json_config
    
    while True:
        print(f"\n--- Add New S3 Server ---")
        
        name = prompt("Friendly Name (e.g. idrive-primary)", f"s3-server-{len(storage_list)+1}")
        endpoint = prompt("S3 Endpoint (e.g. s3.amazonaws.com)", "", required=False)
        if not endpoint:
            break
            
        server = {
            "name": name,
            "type": "s3",
            "endpoint": endpoint,
            "region": prompt("Region Code", "us-east-1"),
            "access_key": prompt("Access Key ID", ""),
            "secret_key": prompt("Secret Access Key", ""),
            "bucket": prompt("Bucket Name", "wordpress-backups"),
            "weight": int(prompt("Priority Weight (1-100)", "100")),
            "storage_limit_gb": float(prompt("Storage Limit (GB)", "100"))
        }
        
        storage_list.append(server)
        json_config["storage"] = storage_list
        save_config(json_config)  # Save incrementally
        
        add_more = input("\nAdd another S3 server? [y/N]: ").strip().lower()
        if add_more != 'y':
            break
    
    return json_config


def configure_email(config):
    print("\n--- SMTP Email ---")
    config["SMTP_SERVER"] = prompt("SMTP Server", get_def(config, "SMTP_SERVER", ""), required=False)
    config["SMTP_PORT"] = prompt("SMTP Port", get_def(config, "SMTP_PORT", "587"))
    config["SMTP_USER"] = prompt("SMTP User", get_def(config, "SMTP_USER", ""), required=False)
    config["SMTP_PASSWORD"] = prompt("SMTP Password", get_def(config, "SMTP_PASSWORD", ""), required=False)
    config["SMTP_SENDER_EMAIL"] = prompt("Sender Email", get_def(config, "SMTP_SENDER_EMAIL", ""), required=False)
    return config


def configure_cloudflare(config):
    print("\n--- Cloudflare D1 ---")
    config["CLOUDFLARE_ACCOUNT_ID"] = prompt("Account ID", get_def(config, "CLOUDFLARE_ACCOUNT_ID", ""), required=False)
    config["CLOUDFLARE_API_TOKEN"] = prompt("API Token", get_def(config, "CLOUDFLARE_API_TOKEN", ""), required=False)
    config["CLOUDFLARE_D1_DATABASE_ID"] = prompt("Database ID", get_def(config, "CLOUDFLARE_D1_DATABASE_ID", ""), required=False)
    return config


def configure_backup(config):
    print("\n--- Backup Settings ---")
    config["BACKUP_DIR"] = prompt("Backup Directory", get_def(config, "BACKUP_DIR", "/opt/wordpress-backup/backups"))
    config["BACKUP_FREQUENCY"] = prompt("Frequency (daily/twice/every-6h/every-2h)", get_def(config, "BACKUP_FREQUENCY", "daily"))
    config["BACKUP_TIME"] = prompt("Time (HH:MM)", get_def(config, "BACKUP_TIME", "00:00"))
    config["RETENTION_LOCAL_DAYS"] = prompt("Local Retention (days)", get_def(config, "RETENTION_LOCAL_DAYS", "2"))
    config["RETENTION_S3_DAYS"] = prompt("S3 Retention (days)", get_def(config, "RETENTION_S3_DAYS", "7"))
    return config


def ensure_server_id(config):
    """Ensure SERVER_ID exists for shared storage."""
    if not config.get("SERVER_ID"):
        # Use hostname or generate UUID
        try:
            hostname = os.uname().nodename.split('.')[0]
            config["SERVER_ID"] = hostname[:20]  # Limit length
        except:
            config["SERVER_ID"] = str(uuid.uuid4())[:8]
    return config


# --- Validation ---

def validate_remote_config():
    """Validate configuration on remote server. Returns (ok, warnings, errors)."""
    warnings = []
    errors = []
    
    env_config = load_env()
    json_config = load_config()
    
    sites = json_config.get("sites", [])
    storage = json_config.get("storage", [])
    
    # CRITICAL: Must have at least one site
    if not sites:
        errors.append("No WordPress sites configured in config.json. Run site detection first.")
    
    # WARNING: No S3 storage
    if not storage:
        warnings.append("No S3 storage configured. Backups will be LOCAL ONLY.")
    else:
        # Check if at least one looks valid
        valid_storage = False
        for s in storage:
            if s.get("endpoint") and s.get("bucket"):
                valid_storage = True
                break
        if not valid_storage:
             warnings.append("S3 storage configured but missing endpoint/bucket.")
    
    # WARNING: No email
    if not env_config.get("SMTP_SERVER"):
        warnings.append("No SMTP configured. No email notifications.")
    
    # INFO: No D1
    if not env_config.get("CLOUDFLARE_ACCOUNT_ID"):
        warnings.append("No Cloudflare D1 configured. Logs stored locally only.")
    
    return len(errors) == 0, warnings, errors


def run_validation():
    """Display validation results."""
    ok, warnings, errors = validate_remote_config()
    
    print("\n" + "="*50)
    print("  Configuration Validation")
    print("="*50)
    
    if errors:
        print("\n[CRITICAL ERRORS]")
        for e in errors:
            print(f"  ✗ {e}")
    
    if warnings:
        print("\n[WARNINGS]")
        for w in warnings:
            print(f"  ⚠ {w}")
    
    if ok and not warnings:
        print("\n  ✓ All checks passed!")
    
    print()
    return ok


# --- Systemd ---

def generate_systemd(config):
    print("\n--- Generating Systemd Files ---")
    install_path = os.getcwd()
    systemd_dir = os.path.join(BASE_DIR, "systemd")
    os.makedirs(systemd_dir, exist_ok=True)
    
    service = f"""[Unit]
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
    
    freq = config.get("BACKUP_FREQUENCY", "daily")
    time = config.get("BACKUP_TIME", "00:00")
    
    if freq == "daily":
        schedule = f"*-*-* {time}:00"
    elif freq == "twice":
        schedule = "*-*-* 00,12:00:00"
    elif freq == "every-6h":
        schedule = "*-*-* 00,06,12,18:00:00"
    else:
        schedule = "*-*-* 00,02,04,06,08,10,12,14,16,18,20,22:00:00"
    
    timer = f"""[Unit]
Description=WordPress Backup Timer

[Timer]
OnCalendar={schedule}
Persistent=true
Unit=wordpress-backup.service

[Install]
WantedBy=timers.target
"""
    
    with open(os.path.join(systemd_dir, "wordpress-backup.service"), "w") as f:
        f.write(service)
    with open(os.path.join(systemd_dir, "wordpress-backup.timer"), "w") as f:
        f.write(timer)
    
    # Report service
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
    
    with open(os.path.join(systemd_dir, "wordpress-report.service"), "w") as f:
        f.write(report_service)
    with open(os.path.join(systemd_dir, "wordpress-report.timer"), "w") as f:
        f.write(report_timer)
    
    print(f"[+] Systemd files created in {systemd_dir}")


# --- Main Flows ---

def run_local_wizard():
    """Local environment wizard - configure for deployment."""
    print("\n" + "="*50)
    print("  WordPress Backup - Local Setup")
    print("="*50)
    
    env_config = load_env()
    json_config = load_config()
    first_run = not os.path.exists(ENV_PATH)
    
    # Deployment is REQUIRED on first run
    if first_run or not env_config.get("REMOTE_HOST"):
        env_config = configure_deployment(env_config)
        save_env(env_config)
    
    # Config Sections
    if prompt_section("S3 Storage") == 'y':
        json_config = configure_s3(json_config)
        save_config(json_config)

    sections = [
        ("SMTP Email", configure_email),
        ("Cloudflare D1", configure_cloudflare),
        ("Backup Settings", configure_backup),
    ]
    
    for name, func in sections:
        choice = prompt_section(name)
        if choice == 's':
            break  # Skip to deploy
        elif choice == 'y':
            env_config = func(env_config)
            save_env(env_config)
    
    # Deploy?
    deploy = input("\nDeploy now? [Y/n]: ").strip().lower()
    if deploy in ('', 'y', 'yes'):
        print("\n[*] Running deploy.sh...")
        os.chdir(BASE_DIR)
        os.execvp("./deploy.sh", ["./deploy.sh"])


def run_remote_wizard():
    """Remote environment wizard - detect sites, validate, generate systemd."""
    print("\n" + "="*50)
    print("  WordPress Backup - Server Setup")
    print("="*50)
    
    env_config = load_env()
    env_config = ensure_server_id(env_config)
    save_env(env_config)
    
    json_config = load_config()
    existing_sites = json_config.get("sites", [])
    
    # Auto-detect WordPress sites
    print("\n[*] Scanning for WordPress sites...")
    detected = detect_wordpress_sites()
    
    if detected:
        selected = prompt_select_sites(detected)
        if selected:
            # Merge with existing, avoid duplicates by name
            existing_names = {s['name'] for s in existing_sites}
            for s in selected:
                if s['name'] not in existing_names:
                    existing_sites.append(s)
            json_config["sites"] = existing_sites
            save_config(json_config)
    else:
        print("[!] No WordPress sites detected automatically.")
    
    # Offer to add sites manually
    while True:
        add_more = input("\nAdd a site manually? [y/N]: ").strip().lower()
        if add_more != 'y':
            break
        
        new_site = manual_add_site()
        if new_site:
            existing_sites.append(new_site)
            json_config["sites"] = existing_sites
            save_config(json_config)
    
    # Validate
    if not run_validation():
        print("\n[!] Critical errors found. Please fix before running backups.")
        sys.exit(1)
    
    # Generate systemd
    generate_systemd(env_config)
    
    print("\n[+] Server setup complete!")
    print("    Install systemd services with:")
    print("      sudo cp systemd/* /etc/systemd/system/")
    print("      sudo systemctl daemon-reload")
    print("      sudo systemctl enable --now wordpress-backup.timer")


def manual_add_site():
    """Manually add a WordPress site with validation."""
    print("\n--- Add WordPress Site Manually ---")
    
    # Get site name
    name = input("Site name (unique identifier): ").strip()
    if not name:
        print("  [!] Site name is required.")
        return None
    
    # Clean up name
    name = name.lower().replace(" ", "-").replace(".", "-")
    
    # Get wp-config path
    wp_config_path = input("Path to wp-config.php: ").strip()
    if not wp_config_path:
        print("  [!] wp-config.php path is required.")
        return None
    
    # Validate wp-config.php exists
    if not os.path.isfile(wp_config_path):
        print(f"  [!] File not found: {wp_config_path}")
        return None
    
    # Validate it's a real wp-config
    try:
        with open(wp_config_path, 'r') as f:
            content = f.read(1000)
            if 'DB_NAME' not in content:
                print("  [!] File does not appear to be a valid wp-config.php (no DB_NAME found)")
                return None
    except Exception as e:
        print(f"  [!] Cannot read file: {e}")
        return None
    
    # Get wp-content path
    wp_content_path = input("Path to wp-content directory: ").strip()
    if not wp_content_path:
        print("  [!] wp-content path is required.")
        return None
    
    # Validate wp-content exists
    if not os.path.isdir(wp_content_path):
        print(f"  [!] Directory not found: {wp_content_path}")
        return None
    
    # Check for themes or plugins subdirectory as validation
    has_themes = os.path.isdir(os.path.join(wp_content_path, "themes"))
    has_plugins = os.path.isdir(os.path.join(wp_content_path, "plugins"))
    if not has_themes and not has_plugins:
        print("  [!] Directory does not appear to be a valid wp-content (no themes/ or plugins/ found)")
        return None
    
    print(f"  [+] Site '{name}' validated successfully!")
    
    return {
        "name": name,
        "wp_config_path": wp_config_path,
        "wp_content_path": wp_content_path,
        "db_host": "",
        "db_name": "",
        "db_user": "",
        "db_password": ""
    }


def main():
    parser = argparse.ArgumentParser(description="WordPress Backup Configuration")
    parser.add_argument("--systemd", action="store_true", help="Generate systemd files only")
    parser.add_argument("--detect", action="store_true", help="Auto-detect WordPress sites")
    parser.add_argument("--validate", action="store_true", help="Validate configuration")
    
    args = parser.parse_args()
    
    # Special modes
    if args.systemd:
        env_config = load_env()
        generate_systemd(env_config)
        return
    
    if args.detect:
        json_config = load_config()
        existing_sites = json_config.get("sites", [])
        detected = detect_wordpress_sites()
        if detected:
            selected = prompt_select_sites(detected)
            if selected:
                json_config["sites"] = existing_sites + selected
                save_config(json_config)
        return
    
    if args.validate:
        ok = run_validation()
        sys.exit(0 if ok else 1)
    
    # Auto-detect environment
    if is_remote_environment():
        run_remote_wizard()
    else:
        run_local_wizard()


if __name__ == "__main__":
    main()
