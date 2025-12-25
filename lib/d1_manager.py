#!/usr/bin/env python3
"""
Cloudflare D1 Manager (Multi-Server Isolated)

Handles synchronization between local SQLite and Cloudflare D1.
Each server only syncs its OWN records (filtered by server_id).
"""

import os
import requests
import sqlite3
import json
import datetime
import traceback
from dotenv import load_dotenv
import math

# Paths
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(ENV_PATH)

def chunk_list(data, chunk_size):
    """Yield successive chunks from data."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]


class D1Manager:
    def __init__(self, db_file=None):
        if db_file is None:
            self.db_file = os.path.join(os.path.dirname(ENV_PATH), "backups.db")
        else:
            self.db_file = db_file
        
        self.account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        self.api_token = os.getenv("CLOUDFLARE_API_TOKEN")
        self.database_id = os.getenv("CLOUDFLARE_D1_DATABASE_ID")
        self.server_id = os.getenv("SERVER_ID", "default")
        
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/d1/database/{self.database_id}/query"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        self.enabled = all([self.account_id, self.api_token, self.database_id])

    def log(self, message):
        print(f"[D1] {message}")

    def execute_remote(self, sql, params=None):
        """Execute SQL query on D1."""
        if not self.enabled:
            return None

        payload = {"sql": sql, "params": params or []}

        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload, timeout=30)
            data = response.json()
            
            if not response.ok:
                # Try to get detailed error from response
                errors = data.get("errors", [])
                if errors:
                    error_msg = errors[0].get("message", str(response.status_code))
                else:
                    error_msg = f"HTTP {response.status_code}"
                self.log(f"API Error: {error_msg}")
                return None
            
            if not data.get("success"):
                error_msg = "; ".join([e.get("message", "") for e in data.get("errors", [])])
                self.log(f"D1 Error: {error_msg}")
                return None
            
            return data["result"][0]
        except requests.exceptions.RequestException as e:
            self.log(f"Network error: {e}")
            return None
        except Exception as e:
            self.log(f"Query failed: {e}")
            return None

    def get_local_connection(self):
        return sqlite3.connect(self.db_file)

    def verify_remote_tables(self):
        """Ensure remote tables exist with server_id column."""
        if not self.enabled:
            return

        schemas = [
            """CREATE TABLE IF NOT EXISTS backup_log
               (id INTEGER PRIMARY KEY, 
                timestamp DATETIME, 
                status TEXT, 
                details TEXT,
                site_name TEXT,
                server_id TEXT);""",
            
            """CREATE TABLE IF NOT EXISTS mega_archives
               (id INTEGER PRIMARY KEY,
                filename TEXT,
                mega_account TEXT,
                file_size INTEGER,
                upload_timestamp DATETIME,
                site_name TEXT,
                server_id TEXT);""",
            
            """CREATE TABLE IF NOT EXISTS daily_emails
               (id INTEGER PRIMARY KEY,
                date TEXT,
                email_sent INTEGER,
                backup_count INTEGER,
                server_id TEXT);"""
        ]
        
        for sql in schemas:
            self.execute_remote(sql)
        
        # Migration: Add server_id column if missing
        migrations = [
            "ALTER TABLE backup_log ADD COLUMN server_id TEXT;",
            "ALTER TABLE mega_archives ADD COLUMN server_id TEXT;",
            "ALTER TABLE daily_emails ADD COLUMN server_id TEXT;"
        ]
        
        for sql in migrations:
            try:
                self.execute_remote(sql)
            except:
                pass

    def sync_table(self, table_name, pk_field="id"):
        """Sync table filtered by server_id - each server only syncs its own records."""
        if not self.enabled:
            return

        self.log(f"Syncing {table_name} for server '{self.server_id}'...")

        # 1. Get remote IDs FOR THIS SERVER ONLY
        remote_res = self.execute_remote(
            f"SELECT {pk_field} FROM {table_name} WHERE server_id = ?",
            [self.server_id]
        )
        remote_ids = set()
        if remote_res and "results" in remote_res:
            for row in remote_res["results"]:
                remote_ids.add(row[pk_field])

        # 2. Get local records FOR THIS SERVER
        conn = self.get_local_connection()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Ensure local table has server_id
        try:
            c.execute(f"ALTER TABLE {table_name} ADD COLUMN server_id TEXT")
            self.log(f"Added server_id column to local {table_name}")
        except sqlite3.OperationalError:
            pass
        
        # Select only this server's records
        c.execute(f"SELECT * FROM {table_name} WHERE server_id = ? OR server_id IS NULL", [self.server_id])
        local_rows = c.fetchall()
        
        local_ids = set()
        rows_to_push = []
        
        for row in local_rows:
            row_id = row[pk_field]
            local_ids.add(row_id)
            if row_id not in remote_ids:
                rows_to_push.append(row)
        
        # 3. Push missing to remote (with server_id)
        if rows_to_push:
            cols_count = len(rows_to_push[0].keys())
            batch_size = max(1, math.floor(90 / cols_count))
            
            self.log(f"Pushing {len(rows_to_push)} records...")
            
            for batch in chunk_list(rows_to_push, batch_size):
                fields = list(batch[0].keys())
                
                # Ensure server_id is set
                if 'server_id' not in fields:
                    fields.append('server_id')
                
                placeholders = "(" + ", ".join(["?"] * len(fields)) + ")"
                all_placeholders = ", ".join([placeholders] * len(batch))
                
                sql = f"INSERT INTO {table_name} ({', '.join(fields)}) VALUES {all_placeholders}"
                
                params = []
                for row in batch:
                    for f in fields:
                        if f == 'server_id':
                            params.append(self.server_id)
                        else:
                            params.append(row[f] if f in row.keys() else None)
                
                self.execute_remote(sql, params)

        # 4. Pull missing from remote (for THIS SERVER only)
        missing_local = list(remote_ids - local_ids)
        
        if missing_local:
            self.log(f"Pulling {len(missing_local)} records...")
            
            for batch_ids in chunk_list(missing_local, 90):
                placeholders = ", ".join(["?"] * len(batch_ids))
                sql = f"SELECT * FROM {table_name} WHERE {pk_field} IN ({placeholders}) AND server_id = ?"
                
                res = self.execute_remote(sql, list(batch_ids) + [self.server_id])
                
                if res and "results" in res:
                    for row in res["results"]:
                        fields = list(row.keys())
                        values = [row[f] for f in fields]
                        sql_insert = f"INSERT OR REPLACE INTO {table_name} ({', '.join(fields)}) VALUES ({', '.join(['?']*len(fields))})"
                        try:
                            c.execute(sql_insert, values)
                        except Exception as e:
                            self.log(f"Insert failed: {e}")
        
        conn.commit()
        conn.close()

    def sync_all(self):
        """Sync all tables for this server."""
        if not self.enabled:
            self.log("D1 not configured, skipping sync.")
            return
        
        try:
            self.verify_remote_tables()
            self.sync_table("backup_log")
            self.sync_table("mega_archives")
            self.sync_table("daily_emails")
            self.log("Sync complete.")
        except Exception as e:
            self.log(f"Sync failed: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    manager = D1Manager()
    if manager.enabled:
        manager.sync_all()
    else:
        print("D1 not configured.")
