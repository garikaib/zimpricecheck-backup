#!/usr/bin/env python3
"""
WordPress Backup Manager (Multi-Site Edition)

Backs up multiple WordPress sites configuration in sites.json.
- Iterates through defined sites.
- Backs up DB, wp-config, wp-content.
- Uploads to Mega (shared accounts).
- Syncs logs to D1 with site context.
"""

import os
import sys
import subprocess
import datetime
import sqlite3
import smtplib
import shutil
import re
import json
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv, dotenv_values
from d1_manager import D1Manager

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
SITES_PATH = os.path.join(BASE_DIR, "sites.json")
DB_FILE = os.path.join(BASE_DIR, "backups.db")

load_dotenv(ENV_PATH)

# Global Configuration
BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.join(BASE_DIR, "backups"))
RETENTION_LOCAL_DAYS = int(os.getenv("RETENTION_LOCAL_DAYS", 2))
RETENTION_MEGA_DAYS = int(os.getenv("RETENTION_MEGA_DAYS", 7))
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SENDER_EMAIL = os.getenv("SMTP_SENDER_EMAIL", "backup@example.com")
WP_TEMP_DIR = os.getenv("WP_TEMP_DIR", "/var/tmp/wp-backup-work")

# Mega Accounts
MEGA_ACCOUNTS = []
for i in range(1, 4):
    email = os.getenv(f"MEGA_EMAIL_{i}", "")
    password = os.getenv(f"MEGA_PASSWORD_{i}", "")
    if email and password:
        MEGA_ACCOUNTS.append({"email": email, "password": password})

MEGA_STORAGE_LIMIT_BYTES = int(float(os.getenv("MEGA_STORAGE_LIMIT_GB", "19.5")) * 1024 * 1024 * 1024)

# Server ID for shared storage (avoids conflicts between servers)
SERVER_ID = os.getenv("SERVER_ID", "default")

# Status Tracking
LOCK_FILE = "/var/tmp/wp-backup.pid"
STATUS_FILE = "/var/tmp/wp-backup.status"

class BackupTracker:
    def __init__(self):
        self.pid = os.getpid()
    
    def check_running(self):
        """Check if another instance is running."""
        if os.path.exists(LOCK_FILE):
            try:
                with open(LOCK_FILE, 'r') as f:
                    old_pid = int(f.read().strip())
                if os.path.exists(f"/proc/{old_pid}"):
                    return True
            except ValueError:
                os.remove(LOCK_FILE)
        return False

    def start(self):
        with open(LOCK_FILE, 'w') as f:
            f.write(str(self.pid))
    
    def finish(self):
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

# --- Database & Logging ---

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS backup_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
                  status TEXT, 
                  details TEXT,
                  site_name TEXT,
                  server_id TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS mega_archives
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT NOT NULL,
                  mega_account TEXT NOT NULL,
                  file_size INTEGER,
                  upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  site_name TEXT,
                  server_id TEXT)''')
    
    # Migration: add server_id if missing
    for table in ['backup_log', 'mega_archives']:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN server_id TEXT")
        except sqlite3.OperationalError:
            pass
    
    conn.commit()
    conn.close()

def log_job(status, details, site_name="system"):
    print(f"[{SERVER_ID}:{site_name}] [{status}] {details}")
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO backup_log (status, details, site_name, server_id) VALUES (?, ?, ?, ?)", 
                  (status, details, site_name, SERVER_ID))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to log to DB: {e}")

def human_readable_size(size_bytes):
    if size_bytes is None: return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0: return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

# --- Mega Functions ---

def mega_cmd(args, timeout=300):
    cmd = ["mega-cmd"] + args if shutil.which("mega-cmd") else ["mega-" + args[0]] + args[1:]
    if not shutil.which("mega-cmd") and not shutil.which(cmd[0]):
         # Try mega-exec if installed
         if shutil.which("mega-exec"):
             cmd = ["mega-exec"] + args
         else:
             return -1, "", "MEGAcmd not installed"

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)

def mega_login(email, password):
    subprocess.run(["mega-logout"], capture_output=True)
    res = subprocess.run(["mega-login", email, password], capture_output=True, text=True, timeout=60)
    return res.returncode == 0

def mega_logout():
    subprocess.run(["mega-logout"], capture_output=True)

def mega_get_usage():
    res = subprocess.run(["mega-df"], capture_output=True, text=True)
    used = 0
    # Parse output "Used: X bytes" or similar
    # Simple regex
    m = re.search(r"Used[:\s]+(\d+)", res.stdout + res.stderr)
    if m: used = int(m.group(1))
    return used, 0

def mega_upload(filepath, remote_path):
    res = subprocess.run(["mega-put", filepath, remote_path], capture_output=True, text=True, timeout=3600)
    return res.returncode == 0, res.stderr

def mega_delete(filename):
    subprocess.run(["mega-rm", filename], capture_output=True)

def mega_list_files(path):
    res = subprocess.run(["mega-ls", "-l", path], capture_output=True, text=True)
    files = []
    # Parse ls output
    return files # simplified for this step

def upload_to_mega(filepath, filename, file_size, site_name):
    if not MEGA_ACCOUNTS:
        log_job("WARNING", "No Mega accounts configured", site_name)
        return None
    
    for account in MEGA_ACCOUNTS:
        try:
            log_job("INFO", f"Trying Mega account: {account['email']}", site_name)
            if not mega_login(account['email'], account['password']):
                continue
            
            used, _ = mega_get_usage()
            if (MEGA_STORAGE_LIMIT_BYTES - used) < file_size:
                log_job("WARNING", "Not enough space", site_name)
                mega_logout()
                continue
            
            # Determine dir: SERVER_ID/Year/Month (for shared storage)
            date_part = datetime.datetime.now().strftime("%Y%m%d")
            year, month = date_part[:4], date_part[4:6]
            remote_dir = f"{SERVER_ID}/{year}/{month}"
            
            subprocess.run(["mega-mkdir", "-p", remote_dir], capture_output=True)
            
            success, err = mega_upload(filepath, remote_dir)
            if success:
                full_remote = f"{remote_dir}/{filename}"
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("INSERT INTO mega_archives (filename, mega_account, file_size, site_name, server_id) VALUES (?, ?, ?, ?, ?)",
                          (full_remote, account['email'], file_size, site_name, SERVER_ID))
                conn.commit()
                conn.close()
                log_job("SUCCESS", f"Uploaded to {account['email']}", site_name)
                mega_logout()
                return account['email']
            else:
                log_job("WARNING", f"Upload failed: {err}", site_name)
            
            mega_logout()
        except Exception as e:
            log_job("ERROR", f"Mega error: {e}", site_name)
            mega_logout()
    
    log_job("ERROR", "All uploads failed", site_name)
    return None

# --- Backup Logic ---

def backup_site(site):
    site_name = site['name']
    log_job("START", f"Starting backup for {site_name}", site_name)
    
    work_dir = os.path.join(WP_TEMP_DIR, site_name)
    if os.path.exists(work_dir): shutil.rmtree(work_dir)
    os.makedirs(work_dir)
    
    try:
        # 1. DB Backup
        # If credentials provided, use them. Else try extract (not implemented fully here for simplicity, reusing env vars logic generally)
        # Assuming credentials in site dict or env
        db_host = site.get("db_host") or os.getenv("DB_HOST", "localhost")
        db_name = site.get("db_name")
        db_user = site.get("db_user")
        db_pass = site.get("db_password")
        
        # If DB details missing, try extract from wp-config
        if not (db_name and db_user and db_pass):
            # Parse wp-config
            with open(site['wp_config_path'], 'r') as f:
                content = f.read()
                if not db_name: db_name = re.search(r"define\s*\(\s*['\"]DB_NAME['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", content).group(1)
                if not db_user: db_user = re.search(r"define\s*\(\s*['\"]DB_USER['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", content).group(1)
                if not db_pass: db_pass = re.search(r"define\s*\(\s*['\"]DB_PASSWORD['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", content).group(1)
        
        db_file = os.path.join(work_dir, "database.sql")
        cmd = ["mysqldump", f"--host={db_host}", f"--user={db_user}", f"--password={db_pass}", 
               "--single-transaction", "--add-drop-table", db_name]
        with open(db_file, 'w') as f:
            subprocess.run(cmd, stdout=f, check=True)
        log_job("INFO", "Database backed up", site_name)
        
        # 2. WP Config
        shutil.copy2(site['wp_config_path'], os.path.join(work_dir, "wp-config.php"))
        
        # 3. WP Content
        content_tar = os.path.join(work_dir, "wp-content.tar")
        cmd = ["tar", "--exclude=cache", "-cf", content_tar, "-C", os.path.dirname(site['wp_content_path']), "wp-content"]
        subprocess.run(cmd, check=True, stderr=subprocess.DEVNULL)
        log_job("INFO", "wp-content archived", site_name)
        
        # 4. Final Archive
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        final_filename = f"{site_name}-backup-{timestamp}.tar.zst"
        final_path = os.path.join(BACKUP_DIR, final_filename)
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # Compress
        subprocess.run(f"tar -cf - -C {work_dir} . | zstd -T0 -19 > {final_path}", shell=True, check=True)
        size = os.path.getsize(final_path)
        log_job("SUCCESS", f"Archive created: {final_filename} ({human_readable_size(size)})", site_name)
        
        # 5. Upload
        upload_to_mega(final_path, final_filename, size, site_name)
        
    except Exception as e:
        log_job("ERROR", f"Backup failed: {e}", site_name)
    finally:
        shutil.rmtree(work_dir)

def main():
    tracker = BackupTracker()
    if tracker.check_running():
        print("Backup already running.")
        sys.exit(1)
    
    tracker.start()
    init_db()
    
    # Sync Schema (D1) first
    d1 = D1Manager()
    if d1.enabled: d1.verify_remote_tables()

    # Load Sites
    if not os.path.exists(SITES_PATH):
        print("No sites.json found.")
        tracker.finish()
        return

    with open(SITES_PATH, 'r') as f:
        data = json.load(f)
        sites = data.get("sites", [])
    
    for site in sites:
        backup_site(site)
    
    # Sync Logs
    if d1.enabled: d1.sync_all()

    tracker.finish()

if __name__ == "__main__":
    main()
