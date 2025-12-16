#!/usr/bin/env python3
"""
WordPress Backup Manager

Backs up WordPress sites including:
- wp-config.php
- wp-content directory
- MariaDB database (with --add-drop-table)

Uploads to Mega.nz using MEGAcmd CLI (supports up to 3 accounts with smart rotation).
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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
WP_CONFIG_PATH = os.getenv("WP_CONFIG_PATH", "/var/www/zimpricecheck.com/wp-config.php")
WP_CONTENT_PATH = os.getenv("WP_CONTENT_PATH", "/var/www/zimpricecheck.com/htdocs/wp-content")
WP_TEMP_DIR = os.getenv("WP_TEMP_DIR", "/var/tmp/wp-backup-work")

# MariaDB Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Mega Accounts (up to 3)
MEGA_ACCOUNTS = []
for i in range(1, 4):
    email = os.getenv(f"MEGA_EMAIL_{i}", "")
    password = os.getenv(f"MEGA_PASSWORD_{i}", "")
    if email and password:
        MEGA_ACCOUNTS.append({"email": email, "password": password})

# Fallback to single MEGA_EMAIL/MEGA_PASSWORD if no numbered accounts
if not MEGA_ACCOUNTS:
    email = os.getenv("MEGA_EMAIL", "")
    password = os.getenv("MEGA_PASSWORD", "")
    if email and password:
        MEGA_ACCOUNTS.append({"email": email, "password": password})

# Mega storage limit (19.5 GB = 20GB - 500MB overhead)
MEGA_STORAGE_LIMIT_BYTES = int(float(os.getenv("MEGA_STORAGE_LIMIT_GB", "19.5")) * 1024 * 1024 * 1024)

# SMTP Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SENDER_EMAIL = os.getenv("SMTP_SENDER_EMAIL", "business@zimpricecheck.com")

# Retention
BACKUP_DIR = os.getenv("BACKUP_DIR", "/opt/wordpress-backup/backups")
RETENTION_LOCAL_DAYS = int(os.getenv("RETENTION_LOCAL_DAYS", 2))
RETENTION_MEGA_DAYS = int(os.getenv("RETENTION_MEGA_DAYS", 7))

# Database
DB_FILE = os.getenv("DB_FILE", "backups.db")

# Timezone
TIMEZONE = "Africa/Harare"


def init_db():
    """Initialize SQLite database with required tables."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Backup log table
    c.execute('''CREATE TABLE IF NOT EXISTS backup_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
                  status TEXT, 
                  details TEXT)''')
    
    # Mega archives tracking table
    c.execute('''CREATE TABLE IF NOT EXISTS mega_archives
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT NOT NULL,
                  mega_account TEXT NOT NULL,
                  file_size INTEGER,
                  upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Daily email tracking
    c.execute('''CREATE TABLE IF NOT EXISTS daily_emails
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT NOT NULL UNIQUE,
                  email_sent INTEGER DEFAULT 0,
                  backup_count INTEGER DEFAULT 0)''')
    
    conn.commit()
    conn.close()


def log_job(status, details):
    """Log a job status to console and database."""
    print(f"[{status}] {details}")
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO backup_log (status, details) VALUES (?, ?)", (status, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to log to DB: {e}")


def human_readable_size(size_bytes):
    """Convert bytes to human-readable format."""
    if size_bytes is None:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def send_email(subject, body, is_html=False):
    """Send an email notification."""
    if not SMTP_SERVER or not SMTP_USER:
        print("SMTP not configured, skipping email.")
        return

    msg = MIMEMultipart()
    msg['From'] = SMTP_SENDER_EMAIL
    msg['To'] = SMTP_USER
    msg['Subject'] = subject

    content_type = 'html' if is_html else 'plain'
    msg.attach(MIMEText(body, content_type))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_SENDER_EMAIL, SMTP_USER, msg.as_string())
        server.quit()
        log_job("INFO", "Email sent successfully.")
    except Exception as e:
        log_job("ERROR", f"Failed to send email: {e}")


def extract_db_credentials_from_wpconfig():
    """Extract database credentials from wp-config.php if not set in env."""
    global DB_NAME, DB_USER, DB_PASSWORD, DB_HOST
    
    if DB_NAME and DB_USER and DB_PASSWORD:
        return True
    
    if not os.path.exists(WP_CONFIG_PATH):
        log_job("ERROR", f"wp-config.php not found at {WP_CONFIG_PATH}")
        return False
    
    try:
        with open(WP_CONFIG_PATH, 'r') as f:
            content = f.read()
        
        # Extract DB_NAME
        match = re.search(r"define\s*\(\s*['\"]DB_NAME['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", content)
        if match:
            DB_NAME = match.group(1)
        
        # Extract DB_USER
        match = re.search(r"define\s*\(\s*['\"]DB_USER['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", content)
        if match:
            DB_USER = match.group(1)
        
        # Extract DB_PASSWORD
        match = re.search(r"define\s*\(\s*['\"]DB_PASSWORD['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", content)
        if match:
            DB_PASSWORD = match.group(1)
        
        # Extract DB_HOST
        match = re.search(r"define\s*\(\s*['\"]DB_HOST['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", content)
        if match:
            DB_HOST = match.group(1)
        
        if DB_NAME and DB_USER and DB_PASSWORD:
            log_job("INFO", f"Extracted DB credentials from wp-config.php (DB: {DB_NAME})")
            return True
        else:
            log_job("ERROR", "Could not extract all DB credentials from wp-config.php")
            return False
            
    except Exception as e:
        log_job("ERROR", f"Failed to read wp-config.php: {e}")
        return False


def create_database_backup(work_dir):
    """Create MariaDB database backup with --add-drop-table."""
    if not extract_db_credentials_from_wpconfig():
        raise Exception("Database credentials not available")
    
    db_backup_file = os.path.join(work_dir, "database.sql")
    
    log_job("INFO", f"Backing up MariaDB database: {DB_NAME}")
    
    # Use mysqldump with --add-drop-table for clean restores
    cmd = [
        "mysqldump",
        f"--host={DB_HOST}",
        f"--user={DB_USER}",
        f"--password={DB_PASSWORD}",
        "--add-drop-table",
        "--single-transaction",
        "--routines",
        "--triggers",
        DB_NAME
    ]
    
    try:
        with open(db_backup_file, 'w') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
        
        if result.returncode != 0:
            raise Exception(f"mysqldump failed: {result.stderr}")
        
        size = os.path.getsize(db_backup_file)
        log_job("SUCCESS", f"Database backup created: {human_readable_size(size)}")
        return db_backup_file
        
    except Exception as e:
        log_job("ERROR", f"Database backup failed: {e}")
        raise


def create_wp_config_backup(work_dir):
    """Copy wp-config.php to work directory."""
    if not os.path.exists(WP_CONFIG_PATH):
        raise Exception(f"wp-config.php not found at {WP_CONFIG_PATH}")
    
    dest = os.path.join(work_dir, "wp-config.php")
    shutil.copy2(WP_CONFIG_PATH, dest)
    log_job("SUCCESS", "wp-config.php backed up")
    return dest


def create_wp_content_backup(work_dir):
    """Create tarball of wp-content directory."""
    if not os.path.exists(WP_CONTENT_PATH):
        raise Exception(f"wp-content not found at {WP_CONTENT_PATH}")
    
    archive_file = os.path.join(work_dir, "wp-content.tar")
    
    log_job("INFO", f"Archiving wp-content from {WP_CONTENT_PATH}...")
    
    # Create tar archive of wp-content
    # Exclude known cache directories
    cmd = [
        "tar", 
        "--exclude=wp-content/cache", 
        "--exclude=wp-content/w3tc-config", 
        "--exclude=wp-content/uploads/cache",
        "--exclude=wp-content/plugins/w3-total-cache/pub",
        "--exclude=wp-content/node_modules",
        "--exclude=wp-content/.git",
        "--exclude=wp-content/debug.log",
        "-cf", archive_file, 
        "-C", os.path.dirname(WP_CONTENT_PATH), 
        "wp-content"
    ]
    
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise Exception(f"tar failed: {result.stderr}")
    
    size = os.path.getsize(archive_file)
    log_job("SUCCESS", f"wp-content archived: {human_readable_size(size)}")
    return archive_file


def create_final_archive(work_dir, backup_dir):
    """Combine all backups into a single zstd-compressed archive."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"wp-backup-{timestamp}.tar.zst"
    filepath = os.path.join(backup_dir, filename)
    
    log_job("INFO", "Creating final compressed archive...")
    
    # Create final archive with zstd compression
    cmd = f"tar -cf - -C {work_dir} . | zstd -T0 -19 > {filepath}"
    
    result = subprocess.run(cmd, shell=True, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise Exception(f"Final archive creation failed: {result.stderr}")
    
    size = os.path.getsize(filepath)
    log_job("SUCCESS", f"Final archive created: {filename} ({human_readable_size(size)})")
    
    return filepath, filename, size


# ============================================================================
# MEGAcmd CLI Functions
# ============================================================================

def mega_cmd(args, timeout=300):
    """Execute a MEGAcmd command and return output."""
    cmd = ["mega-cmd"] + args if shutil.which("mega-cmd") else ["mega-" + args[0]] + args[1:]
    
    # Try mega-cmd first, then individual commands like mega-login, mega-put, etc.
    if not shutil.which("mega-cmd"):
        cmd = ["mega-" + args[0]] + args[1:]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -1, "", "MEGAcmd not installed"


def mega_logout():
    """Logout from current Mega session."""
    subprocess.run(["mega-logout"], capture_output=True, timeout=30)


def mega_login(email, password):
    """Login to Mega account."""
    mega_logout()
    result = subprocess.run(
        ["mega-login", email, password],
        capture_output=True, text=True, timeout=60
    )
    return result.returncode == 0


def mega_get_usage():
    """Get current storage usage in bytes."""
    result = subprocess.run(
        ["mega-df"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return 0, 0
    
    # Parse mega-df output
    # Example: "Total: 20971520000 bytes / Used: 5000000000 bytes / Free: 15971520000 bytes"
    output = result.stdout + result.stderr
    
    used = 0
    total = 0
    
    # Try to find used space
    for line in output.split('\n'):
        if 'Used' in line or 'used' in line:
            # Extract numbers
            numbers = re.findall(r'(\d+)', line)
            if numbers:
                used = int(numbers[0])
        if 'Total' in line or 'total' in line:
            numbers = re.findall(r'(\d+)', line)
            if numbers:
                total = int(numbers[0])
    
    return used, total


def mega_upload(filepath, remote_path="/"):
    """Upload file to Mega."""
    result = subprocess.run(
        ["mega-put", filepath, remote_path],
        capture_output=True, text=True, timeout=3600  # 1 hour timeout for large files
    )
    return result.returncode == 0, result.stderr


def mega_delete(filename):
    """Delete a file from Mega."""
    result = subprocess.run(
        ["mega-rm", filename],
        capture_output=True, text=True, timeout=60
    )
    return result.returncode == 0


def mega_list_files():
    """List files in Mega root."""
    result = subprocess.run(
        ["mega-ls", "-l"],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        return []
    
    files = []
    for line in result.stdout.split('\n'):
        if line.strip() and 'wp-backup-' in line:
            parts = line.split()
            if len(parts) >= 5:
                # Format: -rw- USER SIZE DATE FILENAME
                try:
                    filename = parts[-1]
                    size = int(parts[2]) if parts[2].isdigit() else 0
                    files.append({"name": filename, "size": size})
                except (ValueError, IndexError):
                    continue
    
    return files


def check_megacmd_installed():
    """Check if MEGAcmd is installed."""
    return shutil.which("mega-login") is not None or shutil.which("mega-cmd") is not None


def get_oldest_archive_across_accounts():
    """Find the oldest archive across all Mega accounts from our database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT id, filename, mega_account, file_size 
        FROM mega_archives 
        ORDER BY upload_timestamp ASC 
        LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    
    if row:
        return {"id": row[0], "filename": row[1], "account": row[2], "size": row[3]}
    return None


def remove_archive_record(archive_id):
    """Remove archive record from database."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM mega_archives WHERE id = ?", (archive_id,))
    conn.commit()
    conn.close()


def upload_to_mega(filepath, filename, file_size):
    """Upload backup to an available Mega account with space."""
    if not MEGA_ACCOUNTS:
        log_job("WARNING", "No Mega accounts configured, skipping upload.")
        return None
    
    if not check_megacmd_installed():
        log_job("ERROR", "MEGAcmd is not installed. Please install it: https://mega.io/cmd")
        log_job("INFO", "Backup saved locally only.")
        return None
    
    # Try each account
    for account in MEGA_ACCOUNTS:
        try:
            log_job("INFO", f"Trying Mega account: {account['email']}")
            
            if not mega_login(account['email'], account['password']):
                log_job("WARNING", f"Failed to login to {account['email']}")
                continue
            
            # Check available space
            used, total = mega_get_usage()
            available = MEGA_STORAGE_LIMIT_BYTES - used
            
            log_job("INFO", f"Account usage: {human_readable_size(used)}, Available: {human_readable_size(available)}")
            
            if available >= file_size:
                # Enough space, upload here
                log_job("INFO", f"Uploading to {account['email']}...")
                success, error = mega_upload(filepath)
                
                if success:
                    # Record in database
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO mega_archives (filename, mega_account, file_size) VALUES (?, ?, ?)",
                        (filename, account['email'], file_size)
                    )
                    conn.commit()
                    conn.close()
                    
                    log_job("SUCCESS", f"Uploaded to Mega: {account['email']}")
                    mega_logout()
                    return account['email']
                else:
                    log_job("WARNING", f"Upload failed: {error}")
            
            mega_logout()
            
        except Exception as e:
            log_job("WARNING", f"Failed with account {account['email']}: {e}")
            mega_logout()
            continue
    
    # All accounts full - delete oldest and retry
    log_job("INFO", "All Mega accounts full. Deleting oldest archive...")
    oldest = get_oldest_archive_across_accounts()
    
    if oldest:
        # Find the account and delete
        for account in MEGA_ACCOUNTS:
            if account['email'] == oldest['account']:
                try:
                    if mega_login(account['email'], account['password']):
                        if mega_delete(oldest['filename']):
                            log_job("INFO", f"Deleted old archive: {oldest['filename']}")
                            remove_archive_record(oldest['id'])
                            mega_logout()
                            # Retry upload
                            return upload_to_mega(filepath, filename, file_size)
                        mega_logout()
                except Exception as e:
                    log_job("ERROR", f"Failed to cleanup oldest archive: {e}")
    
    log_job("ERROR", "Could not upload to any Mega account")
    return None


def cleanup_mega_retention():
    """Delete old archives from Mega based on retention policy."""
    if not MEGA_ACCOUNTS or not check_megacmd_installed():
        return
    
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(days=RETENTION_MEGA_DAYS)
    
    for account in MEGA_ACCOUNTS:
        try:
            if not mega_login(account['email'], account['password']):
                continue
            
            files = mega_list_files()
            
            for file_info in files:
                name = file_info['name']
                if name.startswith('wp-backup-') and name.endswith('.tar.zst'):
                    # Extract date from filename: wp-backup-YYYYMMDD-HHMMSS.tar.zst
                    try:
                        date_str = name.replace('wp-backup-', '').replace('.tar.zst', '')
                        file_date = datetime.datetime.strptime(date_str, "%Y%m%d-%H%M%S")
                        
                        if file_date < cutoff:
                            log_job("INFO", f"Deleting old Mega file: {name}")
                            mega_delete(name)
                            
                            # Also remove from our tracking DB
                            conn = sqlite3.connect(DB_FILE)
                            c = conn.cursor()
                            c.execute("DELETE FROM mega_archives WHERE filename = ?", (name,))
                            conn.commit()
                            conn.close()
                    except ValueError:
                        continue
            
            mega_logout()
            
        except Exception as e:
            log_job("WARNING", f"Mega cleanup failed for {account['email']}: {e}")
            mega_logout()


def cleanup_local():
    """Clean up old local backup files."""
    log_job("INFO", "Cleaning up local files...")
    
    if not os.path.exists(BACKUP_DIR):
        return
    
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(days=RETENTION_LOCAL_DAYS)
    
    count_deleted = 0
    for f in os.listdir(BACKUP_DIR):
        if f.startswith("wp-backup-") and f.endswith(".tar.zst"):
            filepath = os.path.join(BACKUP_DIR, f)
            if os.path.getmtime(filepath) < cutoff.timestamp():
                try:
                    os.remove(filepath)
                    log_job("INFO", f"Deleted local file: {f}")
                    count_deleted += 1
                except Exception as e:
                    log_job("ERROR", f"Failed to delete {f}: {e}")
    
    if count_deleted > 0:
        log_job("SUCCESS", f"Deleted {count_deleted} old local files.")


def should_send_daily_email():
    """Check if we should send a daily email (only once per day if >2 backups)."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get or create today's record
    c.execute("SELECT email_sent, backup_count FROM daily_emails WHERE date = ?", (today,))
    row = c.fetchone()
    
    if row:
        email_sent, backup_count = row
        backup_count += 1
        c.execute("UPDATE daily_emails SET backup_count = ? WHERE date = ?", (backup_count, today))
    else:
        backup_count = 1
        c.execute("INSERT INTO daily_emails (date, backup_count) VALUES (?, ?)", (today, 1))
    
    conn.commit()
    conn.close()
    
    # If this is the first or second backup, no daily email yet
    # If third or more, and email not sent, we should send
    return backup_count >= 2 and (not row or row[0] == 0)


def mark_daily_email_sent():
    """Mark that the daily summary email has been sent."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE daily_emails SET email_sent = 1 WHERE date = ?", (today,))
    conn.commit()
    conn.close()


def get_todays_backups():
    """Get all backups from today for the summary email."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT filename, mega_account, file_size, upload_timestamp 
        FROM mega_archives 
        WHERE date(upload_timestamp) = ?
        ORDER BY upload_timestamp DESC
    """, (today,))
    rows = c.fetchall()
    conn.close()
    
    return rows


def send_daily_summary():
    """Send daily summary email with all backups."""
    backups = get_todays_backups()
    
    if not backups:
        return
    
    html = """
    <html>
    <head>
    <style>
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        .size { font-weight: bold; }
    </style>
    </head>
    <body>
    <h2>WordPress Backup Daily Summary</h2>
    <p>Timezone: Africa/Harare</p>
    <table>
        <tr>
            <th>Time</th>
            <th>Archive</th>
            <th>Size</th>
            <th>Mega Account</th>
        </tr>
    """
    
    for backup in backups:
        filename, mega_account, file_size, timestamp = backup
        size_str = human_readable_size(file_size) if file_size else "Unknown"
        html += f"""
        <tr>
            <td>{timestamp}</td>
            <td>{filename}</td>
            <td class="size">{size_str}</td>
            <td>{mega_account}</td>
        </tr>
        """
    
    html += """
    </table>
    </body>
    </html>
    """
    
    send_email("WordPress Backup Daily Summary", html, is_html=True)
    mark_daily_email_sent()


def run_backup():
    """Main backup process."""
    # Ensure backup directory exists
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    # Create temporary work directory (away from WordPress path)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    work_dir = os.path.join(WP_TEMP_DIR, f"backup-{timestamp}")
    os.makedirs(work_dir, exist_ok=True)
    
    log_job("INFO", f"Working directory: {work_dir}")
    
    filepath = None
    try:
        # 1. Backup database
        create_database_backup(work_dir)
        
        # 2. Backup wp-config.php
        create_wp_config_backup(work_dir)
        
        # 3. Backup wp-content
        create_wp_content_backup(work_dir)
        
        # 4. Create final archive
        filepath, filename, file_size = create_final_archive(work_dir, BACKUP_DIR)
        
        # 5. Upload to Mega
        mega_account = upload_to_mega(filepath, filename, file_size)
        
        # 6. Cleanup
        cleanup_mega_retention()
        cleanup_local()
        
        # 7. Check if we need to send daily summary
        if should_send_daily_email():
            send_daily_summary()
        
        log_job("COMPLETE", f"Backup completed: {filename} ({human_readable_size(file_size)}) -> {mega_account or 'local only'}")
        
        return filepath, filename, file_size, mega_account
        
    except Exception:
        # If any step fails, clean up the final archive if it was created
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                log_job("WARNING", f"Deleted failed backup artifact: {filepath}")
            except Exception as cleanup_error:
                log_job("ERROR", f"Failed to delete failed artifact: {cleanup_error}")
        raise
        
    finally:
        # Always cleanup work directory
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
            log_job("INFO", "Cleaned up work directory")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="WordPress Backup Manager")
    parser.add_argument("--dry-run", action="store_true", help="Simulate backup without making changes")
    args = parser.parse_args()
    
    init_db()
    log_job("START", "WordPress backup job started.")
    
    if args.dry_run:
        log_job("INFO", "DRY RUN MODE - No actual backup will be created")
        log_job("INFO", f"Would backup: {WP_CONFIG_PATH}")
        log_job("INFO", f"Would backup: {WP_CONTENT_PATH}")
        log_job("INFO", f"Would backup database: {DB_NAME or 'from wp-config.php'}")
        log_job("INFO", f"Temp directory: {WP_TEMP_DIR}")
        log_job("INFO", f"Mega accounts configured: {len(MEGA_ACCOUNTS)}")
        for acc in MEGA_ACCOUNTS:
            log_job("INFO", f"  - {acc['email']}")
        if check_megacmd_installed():
            log_job("INFO", "MEGAcmd: Installed")
        else:
            log_job("WARNING", "MEGAcmd: NOT INSTALLED - uploads will be skipped")
        return
    
    try:
        filepath, filename, file_size, mega_account = run_backup()
        log_job("SUCCESS", "Backup job completed successfully.")
        
    except Exception as e:
        msg = f"Backup job failed: {str(e)}"
        log_job("FATAL", msg)
        send_email("WordPress Backup FAILED", msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
