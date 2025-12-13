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

DB_FILE = "backups.db"
TIMEZONE = "Africa/Harare"
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SENDER_EMAIL = os.getenv("SMTP_SENDER_EMAIL", "business@zimpricecheck.com")

def get_recent_jobs():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Get jobs from last 24 hours
        # SQLite stores UTC by default as we used CURRENT_TIMESTAMP
        query = "SELECT timestamp, status, details FROM backup_log WHERE timestamp >= datetime('now', '-1 day') ORDER BY timestamp DESC"
        c.execute(query)
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"DB Error: {e}")
        return []

def format_timestamp(ts_str):
    # Setup timezones
    utc_zone = pytz.utc
    local_zone = pytz.timezone(TIMEZONE)
    
    # Parse UTC string from SQLite (YYYY-MM-DD HH:MM:SS)
    # Assume it is UTC because CURRENT_TIMESTAMP is UTC
    try:
        utc_dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        utc_dt = utc_zone.localize(utc_dt)
        local_dt = utc_dt.astimezone(local_zone)
        return local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return ts_str

def send_report(html_body):
    if not SMTP_SERVER or not SMTP_USER:
        print("SMTP not configured.")
        return

    msg = MIMEMultipart()
    msg['From'] = SMTP_SENDER_EMAIL
    msg['To'] = SMTP_USER
    msg['Subject'] = "Daily MongoDB Backup Report"

    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_SENDER_EMAIL, SMTP_USER, msg.as_string())
        server.quit()
        print("Report sent.")
    except Exception as e:
        print(f"Failed to send report: {e}")

def main():
    rows = get_recent_jobs()
    
    if not rows:
        print("No jobs found in last 24h.")
        return

    # Build HTML Table
    html = """
    <html>
    <head>
    <style>
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .SUCCESS { color: green; font-weight: bold; }
        .ERROR { color: red; font-weight: bold; }
        .FATAL { color: darkred; font-weight: bold; }
        .INFO { color: gray; }
    </style>
    </head>
    <body>
    <h2>Daily Backup Summary</h2>
    <p>Timezone: Africa/Harare</p>
    <table>
        <tr>
            <th>Time</th>
            <th>Status</th>
            <th>Details</th>
        </tr>
    """
    
    for row in rows:
        ts, status, details = row
        local_ts = format_timestamp(ts)
        html += f"""
        <tr>
            <td>{local_ts}</td>
            <td class="{status}">{status}</td>
            <td>{details}</td>
        </tr>
        """
        
    html += """
    </table>
    </body>
    </html>
    """
    
    send_report(html)

if __name__ == "__main__":
    main()
