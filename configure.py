import os
import sys

def prompt(label, default=None):
    if default:
        val = input(f"{label} [{default}]: ").strip()
        return val if val else default
    else:
        while True:
            val = input(f"{label}: ").strip()
            if val:
                return val

def main():
    print("--- MongoDB Backup Configuration Wizard ---")
    
    # 0. Load existing .env if present for defaults
    defaults = {}
    if os.path.exists(".env"):
        try:
            with open(".env", "r") as f:
                for line in f:
                    if "=" in line:
                        key, val = line.strip().split("=", 1)
                        # Remove quotes if present
                        val = val.strip('"').strip("'")
                        defaults[key] = val
        except Exception as e:
            print(f"[-] Failed to load existing .env: {e}")

    # Helper to get default from loaded env or fallback
    def get_def(key, fallback=None):
        return defaults.get(key, fallback)
    
    # 1. Gather Variables
    mongo_source = prompt("Source MongoDB URI", get_def("MONGO_SOURCE_URI"))
    mongo_dest = prompt("Destination MongoDB URI", get_def("MONGO_DEST_URI"))
    
    print("\n-- Mega.nz Init --")
    mega_email = prompt("Mega.nz Email", get_def("MEGA_EMAIL"))
    mega_pass = prompt("Mega.nz Password", get_def("MEGA_PASSWORD"))
    
    print("\n-- SMTP Init --")
    smtp_server = prompt("SMTP Server", get_def("SMTP_SERVER", "smtp.gmail.com"))
    smtp_port = prompt("SMTP Port", get_def("SMTP_PORT", "587"))
    smtp_user = prompt("SMTP Username/Email", get_def("SMTP_USER"))
    smtp_pass = prompt("SMTP Password", get_def("SMTP_PASSWORD"))
    smtp_sender = prompt("SMTP Sender Email", get_def("SMTP_SENDER_EMAIL", "business@zimpricecheck.com"))
    
    print("\n-- Retention --")
    retention_local = prompt("Local Retention (Days)", get_def("RETENTION_LOCAL_DAYS", "2"))
    retention_mega = prompt("Mega Retention (Days)", get_def("RETENTION_MEGA_DAYS", "7"))
    
    backup_dir = prompt("Backup Directory", get_def("BACKUP_DIR", "/opt/mongo-sync-backup/backups"))
    
    # 2. Write .env
    env_content = f"""MONGO_SOURCE_URI="{mongo_source}"
MONGO_DEST_URI="{mongo_dest}"
MEGA_EMAIL="{mega_email}"
MEGA_PASSWORD="{mega_pass}"
SMTP_SERVER="{smtp_server}"
SMTP_PORT="{smtp_port}"
SMTP_USER="{smtp_user}"
SMTP_PASSWORD="{smtp_pass}"
SMTP_SENDER_EMAIL="{smtp_sender}"
BACKUP_DIR="{backup_dir}"
RETENTION_LOCAL_DAYS={retention_local}
RETENTION_MEGA_DAYS={retention_mega}
"""
    with open(".env", "w") as f:
        f.write(env_content)
    print("\n[+] Created .env file.")

    # 3. Systemd Generation
    print("\n--- Systemd Generation ---")
    # We are generating files LOCALLLY to be deployed REMOTELY.
    # The remote path is strict: /opt/mongo-sync-backup
    
    install_path = "/opt/mongo-sync-backup"
    
    service_content = f"""[Unit]
Description=MongoDB Backup and Sync Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory={install_path}
ExecStart={install_path}/venv/bin/python3 {install_path}/backup_manager.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""

    timer_content = """[Unit]
Description=Run MongoDB Backup every 2 hours

[Timer]
OnBootSec=15min
OnUnitActiveSec=2h
Unit=mongodb-backup.service

[Install]
WantedBy=timers.target
"""

    report_service = f"""[Unit]
Description=Daily MongoDB Backup Report
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory={install_path}
ExecStart={install_path}/venv/bin/python3 {install_path}/report_manager.py
Restart=on-failure
"""

    # Run daily at 08:00 AM
    report_timer = """[Unit]
Description=Send Daily MongoDB Backup Report

[Timer]
OnCalendar=*-*-* 08:00:00
Unit=mongodb-report.service

[Install]
WantedBy=timers.target
"""

    with open("mongodb-backup.service", "w") as f:
        f.write(service_content)
    
    with open("mongodb-backup.timer", "w") as f:
        f.write(timer_content)

    with open("mongodb-report.service", "w") as f:
        f.write(report_service)
        
    with open("mongodb-report.timer", "w") as f:
        f.write(report_timer)
        
    print("[+] Created systemd service files (backup & report).")
    
    # 4. Init DB
    print("[*] Initializing SQLite DB...")
    import sqlite3
    try:
        conn = sqlite3.connect("backups.db")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS backup_log
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
                      status TEXT, 
                      details TEXT)''')
        conn.commit()
        conn.close()
        print("[+] SQLite DB initialized.")
    except Exception as e:
        print(f"[-] Failed to init DB: {e}")

    print("\n--- Setup Complete ---")
    print("To install systemd services run:")
    print("sudo cp mongodb-backup.service /etc/systemd/system/")
    print("sudo cp mongodb-backup.timer /etc/systemd/system/")
    print("sudo systemctl daemon-reload")
    print("sudo systemctl enable --now mongodb-backup.timer")

if __name__ == "__main__":
    main()
