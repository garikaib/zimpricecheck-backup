#!/usr/bin/env python3
"""
WordPress Backup Report Manager

Generates and sends daily backup summary reports including:
- Files stored
- File sizes (human-readable)
- S3 storage endpoint used for each backup
"""

import sqlite3
import datetime
import smtplib
import os
import pytz
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load config
load_dotenv()

DB_FILE = os.getenv("DB_FILE", "backups.db")
TIMEZONE = "Africa/Harare"
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SENDER_EMAIL = os.getenv("SMTP_SENDER_EMAIL", "business@zimpricecheck.com")


def human_readable_size(size_bytes):
    """Convert bytes to human-readable format."""
    if size_bytes is None:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def format_timestamp(ts_str):
    """Convert UTC timestamp to Africa/Harare timezone."""
    utc_zone = pytz.utc
    local_zone = pytz.timezone(TIMEZONE)
    
    try:
        utc_dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        utc_dt = utc_zone.localize(utc_dt)
        local_dt = utc_dt.astimezone(local_zone)
        return local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return ts_str


def get_recent_logs():
    """Get backup logs from last 24 hours."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        query = """
            SELECT timestamp, status, details 
            FROM backup_log 
            WHERE timestamp >= datetime('now', '-1 day') 
            ORDER BY timestamp DESC
        """
        c.execute(query)
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"DB Error: {e}")
        return []


def get_recent_archives():
    """Get archive uploads from last 24 hours."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        query = """
            SELECT filename, s3_endpoint, s3_bucket, file_size, upload_timestamp 
            FROM s3_archives 
            WHERE upload_timestamp >= datetime('now', '-1 day') 
            ORDER BY upload_timestamp DESC
        """
        c.execute(query)
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"DB Error: {e}")
        return []


def send_report(html_body):
    """Send the HTML report via email."""
    if not SMTP_SERVER or not SMTP_USER:
        print("SMTP not configured.")
        return

    msg = MIMEMultipart()
    msg['From'] = f"WordPress Backup <{SMTP_SENDER_EMAIL}>"
    msg['To'] = SMTP_USER
    msg['Subject'] = "WordPress Backup Daily Report"

    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_SENDER_EMAIL, SMTP_USER, msg.as_string())
        server.quit()
        print("Report sent successfully.")
    except Exception as e:
        print(f"Failed to send report: {e}")


def main():
    archives = get_recent_archives()
    logs = get_recent_logs()
    
    if not archives and not logs:
        print("No backup activity in last 24 hours.")
        return

    # Build HTML Report
    html = """
    <html>
    <head>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h2 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        h3 { color: #34495e; margin-top: 30px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background-color: #3498db; color: white; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .SUCCESS { color: #27ae60; font-weight: bold; }
        .ERROR { color: #e74c3c; font-weight: bold; }
        .FATAL { color: #c0392b; font-weight: bold; }
        .INFO { color: #7f8c8d; }
        .WARNING { color: #f39c12; font-weight: bold; }
        .size { font-weight: bold; color: #2980b9; }
        .s3-endpoint { font-family: monospace; background-color: #ecf0f1; padding: 2px 6px; border-radius: 3px; }
        .summary-box { background-color: #e8f6f3; border-left: 4px solid #1abc9c; padding: 15px; margin-bottom: 20px; }
    </style>
    </head>
    <body>
    <h2>🗂️ WordPress Backup Daily Report</h2>
    <p>Timezone: Africa/Harare (UTC+2)</p>
    """
    
    # Summary box
    if archives:
        total_size = sum(a[3] or 0 for a in archives)
        endpoints = set(f"{a[1]}/{a[2]}" for a in archives if a[1])
        html += f"""
        <div class="summary-box">
            <strong>Summary:</strong> {len(archives)} backup(s) created in the last 24 hours<br>
            <strong>Total Size:</strong> {human_readable_size(total_size)}<br>
            <strong>S3 Storage:</strong> {', '.join(endpoints) if endpoints else 'N/A'}
        </div>
        """
    
    # Archives Table
    if archives:
        html += """
        <h3>📦 Backup Archives</h3>
        <table>
            <tr>
                <th>Time</th>
                <th>Archive File</th>
                <th>Size</th>
                <th>S3 Endpoint</th>
            </tr>
        """
        
        for archive in archives:
            filename, s3_endpoint, s3_bucket, file_size, timestamp = archive
            local_ts = format_timestamp(timestamp)
            size_str = human_readable_size(file_size)
            storage_display = f"{s3_endpoint}/{s3_bucket}" if s3_endpoint else "N/A"
            html += f"""
            <tr>
                <td>{local_ts}</td>
                <td>{filename}</td>
                <td class="size">{size_str}</td>
                <td><span class="s3-endpoint">{storage_display}</span></td>
            </tr>
            """
        
        html += "</table>"
    
    # Activity Log Table
    if logs:
        html += """
        <h3>📋 Activity Log</h3>
        <table>
            <tr>
                <th>Time</th>
                <th>Status</th>
                <th>Details</th>
            </tr>
        """
        
        for log in logs:
            ts, status, details = log
            local_ts = format_timestamp(ts)
            # Truncate long details
            if len(details) > 200:
                details = details[:200] + "..."
            html += f"""
            <tr>
                <td>{local_ts}</td>
                <td class="{status}">{status}</td>
                <td>{details}</td>
            </tr>
            """
        
        html += "</table>"
    
    # Footer
    html += """
    <p style="color: #95a5a6; font-size: 12px; margin-top: 30px;">
        WordPress Backup System - zimpricecheck.com
    </p>
    </body>
    </html>
    """
    
    send_report(html)


if __name__ == "__main__":
    main()
