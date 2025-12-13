import os
import sys
import subprocess
import datetime
import sqlite3
import smtplib
import glob
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mega import Mega
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
MONGO_SOURCE_URI = os.getenv("MONGO_SOURCE_URI")
MONGO_DEST_URI = os.getenv("MONGO_DEST_URI")
MEGA_EMAIL = os.getenv("MEGA_EMAIL")
MEGA_PASSWORD = os.getenv("MEGA_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SENDER_EMAIL = os.getenv("SMTP_SENDER_EMAIL", "business@zimpricecheck.com")
BACKUP_DIR = os.getenv("BACKUP_DIR", "./backups")
RETENTION_LOCAL_DAYS = int(os.getenv("RETENTION_LOCAL_DAYS", 2))
RETENTION_MEGA_DAYS = int(os.getenv("RETENTION_MEGA_DAYS", 7))
DB_FILE = "backups.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS backup_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
                  status TEXT, 
                  details TEXT)''')
    conn.commit()
    conn.close()

def log_job(status, details):
    print(f"[{status}] {details}")
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO backup_log (status, details) VALUES (?, ?)", (status, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to log to DB: {e}")

def send_email(subject, body):
    if not SMTP_SERVER or not SMTP_USER:
        print("SMTP not configured, skipping email.")
        return

    msg = MIMEMultipart()
    msg['From'] = SMTP_SENDER_EMAIL
    msg['To'] = SMTP_USER # Sending to self for now
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(SMTP_SENDER_EMAIL, SMTP_USER, text)
        server.quit()
        log_job("INFO", "Email sent successfully.")
    except Exception as e:
        log_job("ERROR", f"Failed to send email: {e}")

def run_backup():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"mongo-backup-{timestamp}.archive.bz2"
    filepath = os.path.join(BACKUP_DIR, filename)
    
    # Command: mongodump ... | bzip2 ...
    # Added -v for verbosity
    cmd = f'mongodump --uri="{MONGO_SOURCE_URI}" --archive -v | bzip2 -9 > {filepath}'
    
    log_job("INFO", f"Starting backup: {filename}")
    try:
        # Use shell=True for piping
        # Capture stderr to debug. Mongo tools write progress/stats to stderr.
        result = subprocess.run(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        
        # Log the output regardless of success so we can see what happened
        log_job("INFO", f"Backup Output:\n{result.stderr}")
        
        if result.returncode != 0:
            err_msg = f"Stderr: {result.stderr}\nStdout: {result.stdout}"
            raise Exception(f"Command failed with code {result.returncode}: {err_msg}")
            
        # Check file size
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            log_job("INFO", f"Backup file created. Size: {size} bytes")
            if size == 0:
                 raise Exception("Backup file is 0 bytes! Dump failed or DB is empty.")

        log_job("SUCCESS", f"Backup created: {filename}")
        return filepath
    except Exception as e:
        log_job("ERROR", f"Backup failed: {e}")
        raise

def run_restore(filepath):
    log_job("INFO", f"Starting restore to destination DB using {filepath}")
    # Command: bunzip2 -c ... | mongorestore ...
    # We add --drop to ensure we overwrite existing data (Sync behavior) preventing duplicate key errors
    # Added -v for verbosity
    cmd = f'bzip2 -dc {filepath} | mongorestore --uri="{MONGO_DEST_URI}" --archive --drop -v'
    
    try:
        result = subprocess.run(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        
        # Log the output regardless of success so we can see "x documents restored"
        log_job("INFO", f"Restore Output:\n{result.stderr}")

        if result.returncode != 0:
            err_msg = f"Stderr: {result.stderr}\nStdout: {result.stdout}"
            raise Exception(f"Restore command failed with code {result.returncode}: {err_msg}")

        log_job("SUCCESS", "Restore completed successfully.")
    except Exception as e:
        log_job("ERROR", f"Restore failed: {e}")
        raise

def upload_to_mega(filepath):
    if not MEGA_EMAIL or not MEGA_PASSWORD:
        log_job("WARNING", "Mega credentials missing, skipping upload.")
        return

    log_job("INFO", "Logging into Mega.nz...")
    try:
        mega = Mega()
        m = mega.login(MEGA_EMAIL, MEGA_PASSWORD)
        
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        log_job("INFO", f"Uploading {filepath} to Mega (Size: {file_size_mb:.2f} MB)...")
        
        m.upload(filepath)
        log_job("SUCCESS", "Upload to Mega completed.")
        
        # Cleanup Mega
        cleanup_mega(m)
        
    except Exception as e:
        log_job("ERROR", f"Mega operation failed: {e}")
        # Don't raise, we still want to finish local cleanup

def cleanup_mega(mega_instance):
    log_job("INFO", "Checking Mega retention...")
    files = mega_instance.get_files()
    
    # Simple check: assuming files are in root or we search for them.
    # Mega.py structure is a complex dictionary.
    # We will look for files starting with 'mongo-backup-' and check creation time.
    
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(days=RETENTION_MEGA_DAYS)
    
    count_deleted = 0
    
    for file_id, file_data in files.items():
        if file_data['t'] == 1: # Directory
            continue
        
        name = file_data['a']['n']
        if name.startswith('mongo-backup-') and name.endswith('.archive.bz2'):
             # Create time is in timestamp
             ts = file_data['ts']
             file_time = datetime.datetime.fromtimestamp(ts)
             
             if file_time < cutoff:
                 log_job("INFO", f"Deleting old Mega file: {name}")
                 mega_instance.destroy(file_id)
                 count_deleted += 1

    if count_deleted > 0:
        log_job("SUCCESS", f"Deleted {count_deleted} old files from Mega.")
    else:
        log_job("INFO", "No old Mega files to delete.")

def cleanup_local():
    log_job("INFO", "Cleaning up local files...")
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(days=RETENTION_LOCAL_DAYS)
    
    files = glob.glob(os.path.join(BACKUP_DIR, "mongo-backup-*.archive.bz2"))
    count_deleted = 0
    
    for f in files:
        if os.path.getmtime(f) < cutoff.timestamp():
            try:
                os.remove(f)
                log_job("INFO", f"Deleted local file: {f}")
                count_deleted += 1
            except Exception as e:
                log_job("ERROR", f"Failed to delete {f}: {e}")

    if count_deleted > 0:
        log_job("SUCCESS", f"Deleted {count_deleted} old local files.")

import argparse

def get_latest_backup():
    files = glob.glob(os.path.join(BACKUP_DIR, "mongo-backup-*.archive.bz2"))
    if not files:
        raise Exception("No local backups found to restore from.")
    return max(files, key=os.path.getmtime)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-backup", action="store_true", help="Skip creating a new backup and use the latest local one")
    args = parser.parse_args()

    init_db()
    log_job("START", "Backup job started.")
    
    try:
        backup_file = None
        
        if args.skip_backup:
            log_job("INFO", "Skipping new backup creation (--skip-backup). Finding latest local backup...")
            backup_file = get_latest_backup()
            log_job("INFO", f"Using latest backup: {backup_file}")
        else:
            # 1. Backup
            backup_file = run_backup()
        
        # 2. Restore
        run_restore(backup_file)
        
        if not args.skip_backup:
            # 3. Upload to Mega
            upload_to_mega(backup_file)
        else:
            log_job("INFO", "Skipping Mega upload (--skip-backup enabled).")
        
        # 4. Local Cleanup
        cleanup_local()
        
        # Success email removed as per request. Only failures are emailed.
        log_job("COMPLETE", "Backup job finished successfully.")
        
    except Exception as e:
        msg = f"Backup job failed: {str(e)}"
        log_job("FATAL", msg)
        send_email("Backup FAILED", msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
