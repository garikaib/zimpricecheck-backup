#!/usr/bin/env python3
"""
Cloudflare D1 Manager

Handles synchronization between local SQLite database and Cloudflare D1.
"""

import os
import requests
import sqlite3
import json
import datetime
import traceback
from dotenv import load_dotenv
import math

# Default env path is one level up from lib/
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(ENV_PATH)

def chunk_list(data, chunk_size):
    """Yield successive chunks from data."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]

class D1Manager:
    def __init__(self, db_file=None):
        # Allow overriding db_file, default to sibling of env
        if db_file is None:
             self.db_file = os.path.join(os.path.dirname(ENV_PATH), "backups.db")
        else:
             self.db_file = db_file
             
        self.account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        self.api_token = os.getenv("CLOUDFLARE_API_TOKEN")
        self.database_id = os.getenv("CLOUDFLARE_D1_DATABASE_ID")
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

        payload = {
            "sql": sql,
            "params": params or []
        }

        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("success"):
                error_msg = "; ".join([e.get("message", "Unknown error") for e in data.get("errors", [])])
                raise Exception(f"D1 API Error: {error_msg}")
            
            return data["result"][0] # D1 returns list of results, usually one per query
        except Exception as e:
            self.log(f"Query failed: {e}")
            # traceback.print_exc() # Optional debug
            return None

    def get_local_connection(self):
        return sqlite3.connect(self.db_file)

    def verify_remote_tables(self):
        """Ensure remote tables exist and have correct schema."""
        if not self.enabled:
            return

        # 1. Create tables if they don't exist
        schemas = [
            """CREATE TABLE IF NOT EXISTS backup_log
               (id INTEGER PRIMARY KEY, 
                timestamp DATETIME, 
                status TEXT, 
                details TEXT,
                site_name TEXT);""",
            
            """CREATE TABLE IF NOT EXISTS mega_archives
               (id INTEGER PRIMARY KEY,
                filename TEXT,
                mega_account TEXT,
                file_size INTEGER,
                upload_timestamp DATETIME,
                site_name TEXT);""",
            
            """CREATE TABLE IF NOT EXISTS daily_emails
               (id INTEGER PRIMARY KEY,
                date TEXT,
                email_sent INTEGER,
                backup_count INTEGER);"""
        ]
        
        for sql in schemas:
            self.execute_remote(sql)
            
        # 2. Migration: Add site_name column if missing (for existing tables)
        # We try to add it and ignore failure if it exists
        migration_sqls = [
            "ALTER TABLE backup_log ADD COLUMN site_name TEXT;",
            "ALTER TABLE mega_archives ADD COLUMN site_name TEXT;"
        ]
        
        for sql in migration_sqls:
            # We don't want to fail if column exists, but D1 API will return error.
            # We just log it as debug and proceed.
            try:
                self.execute_remote(sql)
            except:
                pass

    def sync_table(self, table_name, pk_field="id"):
        """Sync a specific table between local and remote using batched operations."""
        if not self.enabled:
            return

        self.log(f"Syncing table {table_name}...")

        # 1. Get all remote IDs
        remote_res = self.execute_remote(f"SELECT {pk_field} FROM {table_name}")
        remote_ids = set()
        if remote_res and "results" in remote_res:
            for row in remote_res["results"]:
                remote_ids.add(row[pk_field])

        # 2. Get all local records
        conn = self.get_local_connection()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Ensure local table has site_name (migration for local DB)
        if table_name in ["backup_log", "mega_archives"]:
            try:
                c.execute(f"ALTER TABLE {table_name} ADD COLUMN site_name TEXT")
                self.log(f"Added site_name column to local {table_name}")
            except sqlite3.OperationalError:
                pass # Already exists
        
        c.execute(f"SELECT * FROM {table_name}")
        local_rows = c.fetchall()
        
        local_ids = set()
        rows_to_push = []
        
        # Identify rows to push
        for row in local_rows:
            row_id = row[pk_field]
            local_ids.add(row_id)
            if row_id not in remote_ids:
                rows_to_push.append(row)
        
        # 3. Batch Push Missing to Remote
        if rows_to_push:
            if len(rows_to_push) > 0:
                cols_count = len(rows_to_push[0].keys())
                batch_size = math.floor(90 / cols_count)
                if batch_size < 1: batch_size = 1

                self.log(f"Pushing {len(rows_to_push)} records to remote in batches of {batch_size}...")
                
                for batch in chunk_list(rows_to_push, batch_size):
                    fields = batch[0].keys()
                    placeholders = "(" + ", ".join(["?"] * len(fields)) + ")"
                    all_placeholders = ", ".join([placeholders] * len(batch))
                    
                    sql = f"INSERT INTO {table_name} ({', '.join(fields)}) VALUES {all_placeholders}"
                    
                    params = []
                    for row in batch:
                        params.extend([row[f] for f in fields])
                    
                    self.execute_remote(sql, params)

        # 4. Batch Pull Missing from Remote
        missing_local = list(remote_ids - local_ids)
        
        if missing_local:
            pull_batch_size = 90
            self.log(f"Pulling {len(missing_local)} records from remote in batches of {pull_batch_size}...")
            
            for batch_ids in chunk_list(missing_local, pull_batch_size):
                placeholders = ", ".join(["?"] * len(batch_ids))
                sql = f"SELECT * FROM {table_name} WHERE {pk_field} IN ({placeholders})"
                
                res = self.execute_remote(sql, list(batch_ids))
                
                if res and "results" in res:
                    for row in res["results"]:
                        fields = list(row.keys())
                        values = [row[f] for f in fields]
                        sql_insert = f"INSERT INTO {table_name} ({', '.join(fields)}) VALUES ({', '.join(['?']*len(fields))})"
                        try:
                            c.execute(sql_insert, values)
                        except Exception as e:
                             self.log(f"Failed to insert local ID {row.get(pk_field)}: {e}")
        
        conn.commit()
        conn.close()

    def sync_all(self):
        """Sync all tracked tables."""
        if not self.enabled:
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
