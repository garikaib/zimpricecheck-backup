#!/usr/bin/env python3
"""
Migration Script: Add server_id to existing database records.

RUN THIS LOCALLY BEFORE DEPLOYING TO PRODUCTION.

This script:
1. Adds server_id column to local SQLite tables if missing
2. Updates all existing records to have a specified server_id
3. Does the same for remote D1 database

Usage:
    python3 migrate_db_server_id.py <SERVER_ID>
    
Example:
    python3 migrate_db_server_id.py zimpricecheck-server

DELETE THIS SCRIPT AFTER MIGRATION IS COMPLETE.
"""

import os
import sys
import sqlite3

# Add lib to path for d1_manager
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
DB_FILE = os.path.join(BASE_DIR, "backups.db")

load_dotenv(ENV_PATH)

def migrate_local(server_id):
    """Add server_id to local SQLite records."""
    print(f"[*] Migrating local database: {DB_FILE}")
    
    if not os.path.exists(DB_FILE):
        print("[-] Database file not found.")
        return
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    tables = ["backup_log", "mega_archives", "daily_emails"]
    
    for table in tables:
        # Add column if missing
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN server_id TEXT")
            print(f"  [+] Added server_id column to {table}")
        except sqlite3.OperationalError:
            print(f"  [=] Column server_id already exists in {table}")
        
        # Update records where server_id is NULL
        c.execute(f"UPDATE {table} SET server_id = ? WHERE server_id IS NULL", [server_id])
        updated = c.rowcount
        print(f"  [+] Updated {updated} records in {table}")
    
    conn.commit()
    conn.close()
    print("[+] Local migration complete.")


def migrate_remote(server_id):
    """Add server_id to remote D1 records."""
    print("\n[*] Migrating remote D1 database...")
    
    try:
        from lib.d1_manager import D1Manager
        
        manager = D1Manager()
        if not manager.enabled:
            print("[-] D1 not configured, skipping remote migration.")
            return
        
        tables = ["backup_log", "mega_archives", "daily_emails"]
        
        for table in tables:
            # Add column if missing
            try:
                manager.execute_remote(f"ALTER TABLE {table} ADD COLUMN server_id TEXT")
                print(f"  [+] Added server_id column to {table}")
            except:
                print(f"  [=] Column server_id may already exist in {table}")
            
            # Update NULL server_ids
            res = manager.execute_remote(
                f"UPDATE {table} SET server_id = ? WHERE server_id IS NULL",
                [server_id]
            )
            if res:
                print(f"  [+] Updated records in {table}")
        
        print("[+] Remote migration complete.")
        
    except ImportError as e:
        print(f"[-] Could not import D1Manager: {e}")
    except Exception as e:
        print(f"[-] Remote migration failed: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 migrate_db_server_id.py <SERVER_ID>")
        print("Example: python3 migrate_db_server_id.py zimpricecheck-server")
        sys.exit(1)
    
    server_id = sys.argv[1]
    
    print("="*50)
    print(f"  Database Migration: server_id = '{server_id}'")
    print("="*50)
    print()
    
    confirm = input(f"This will update ALL existing records to server_id='{server_id}'. Continue? [y/N]: ")
    if confirm.lower() != 'y':
        print("Aborted.")
        sys.exit(0)
    
    migrate_local(server_id)
    migrate_remote(server_id)
    
    print()
    print("="*50)
    print("  Migration Complete!")
    print("  DELETE THIS SCRIPT after verifying.")
    print("="*50)


if __name__ == "__main__":
    main()
