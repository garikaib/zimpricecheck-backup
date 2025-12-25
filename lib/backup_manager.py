#!/usr/bin/env python3
"""
WordPress Backup Manager (Multi-Site Edition)

Backs up multiple WordPress sites configuration in sites.json.
- Iterates through defined sites.
- Backs up DB, wp-config, wp-content.
- Uploads to S3-compatible storage.
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
from s3_manager import S3Manager, upload_to_s3

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
SITES_PATH = os.path.join(BASE_DIR, "sites.json")
DB_FILE = os.path.join(BASE_DIR, "backups.db")

load_dotenv(ENV_PATH)

# Global Configuration
BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.join(BASE_DIR, "backups"))
RETENTION_LOCAL_DAYS = int(os.getenv("RETENTION_LOCAL_DAYS", 2))
RETENTION_S3_DAYS = int(os.getenv("RETENTION_S3_DAYS", 7))
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SENDER_EMAIL = os.getenv("SMTP_SENDER_EMAIL", "backup@example.com")
WP_TEMP_DIR = os.getenv("WP_TEMP_DIR", "/var/tmp/wp-backup-work")

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
    
    c.execute('''CREATE TABLE IF NOT EXISTS s3_archives
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT NOT NULL,
                  s3_endpoint TEXT NOT NULL,
                  s3_bucket TEXT NOT NULL,
                  file_size INTEGER,
                  upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  site_name TEXT,
                  server_id TEXT)''')
    
    # Migration: add server_id if missing
    for table in ['backup_log', 's3_archives']:
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

# --- Backup Logic ---

def backup_site(site):
    site_name = site['name']
    log_job("START", f"Starting backup for {site_name}", site_name)
    
    work_dir = os.path.join(WP_TEMP_DIR, site_name)
    if os.path.exists(work_dir): shutil.rmtree(work_dir)
    os.makedirs(work_dir)
    
    try:
        # 1. DB Backup
        db_host = site.get("db_host") or os.getenv("DB_HOST", "localhost")
        db_name = site.get("db_name")
        db_user = site.get("db_user")
        db_pass = site.get("db_password")
        
        # If DB details missing, try extract from wp-config
        if not (db_name and db_user and db_pass):
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
        
        # 5. Upload to S3
        upload_to_s3(final_path, final_filename, size, site_name, log_job)
        
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
