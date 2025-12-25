#!/usr/bin/env python3
"""
Migration Script: Reorganize Mega storage into server folders.

RUN THIS LOCALLY/MANUALLY.

This script:
1. Logs into each Mega account
2. Lists all existing backup files in Year/Month folders
3. Moves them to SERVER_ID/Year/Month folders

Usage:
    python3 migrate_mega_storage.py <SERVER_ID>
    
Example:
    python3 migrate_mega_storage.py zimpricecheck-server

DELETE THIS SCRIPT AFTER MIGRATION IS COMPLETE.
"""

import os
import sys
import subprocess
import re
from glob import glob
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_PATH)

def mega_login(email, password):
    subprocess.run(["mega-logout"], capture_output=True)
    res = subprocess.run(["mega-login", email, password], capture_output=True, text=True)
    return res.returncode == 0

def mega_logout():
    subprocess.run(["mega-logout"], capture_output=True)

def mega_ls(path=""):
    """List items at path."""
    cmd = ["mega-ls", "-l"]
    if path:
        cmd.append(path)
    res = subprocess.run(cmd, capture_output=True, text=True)
    items = []
    for line in res.stdout.split('\n'):
        if line.strip():
            parts = line.split()
            if len(parts) >= 1:
                items.append(parts[-1])  # Last part is filename
    return items

def mega_mkdir(path):
    subprocess.run(["mega-mkdir", "-p", path], capture_output=True)

def mega_mv(src, dst):
    """Move file/folder."""
    res = subprocess.run(["mega-mv", src, dst], capture_output=True, text=True)
    return res.returncode == 0

def migrate_account(email, password, server_id):
    """Migrate one Mega account."""
    print(f"\n[*] Processing account: {email}")
    
    if not mega_login(email, password):
        print(f"  [-] Failed to login")
        return
    
    # Look for Year folders (2023, 2024, 2025, etc.)
    root_items = mega_ls()
    years = [item for item in root_items if re.match(r'^\d{4}$', item)]
    
    # Also look for legacy root files
    root_files = [item for item in root_items if item.endswith('.tar.zst')]
    
    if not years and not root_files:
        print("  [=] No files to migrate")
        mega_logout()
        return
    
    # Migrate Year/Month folders to SERVER_ID/Year/Month
    for year in years:
        months = mega_ls(year)
        months = [m for m in months if re.match(r'^\d{2}$', m)]
        
        for month in months:
            old_path = f"{year}/{month}"
            new_path = f"{server_id}/{year}/{month}"
            
            # List files in this folder
            files = mega_ls(old_path)
            backup_files = [f for f in files if '.tar.zst' in f]
            
            if backup_files:
                print(f"  [*] Moving {len(backup_files)} files from {old_path} to {new_path}")
                mega_mkdir(new_path)
                
                for f in backup_files:
                    src = f"{old_path}/{f}"
                    if mega_mv(src, new_path + "/"):
                        print(f"    [+] Moved {f}")
                    else:
                        print(f"    [-] Failed to move {f}")
    
    # Migrate root-level legacy files
    for f in root_files:
        # Extract date from filename to determine destination
        # wp-backup-20241225-030000.tar.zst -> 2024/12
        match = re.search(r'(\d{4})(\d{2})\d{2}-\d{6}', f)
        if match:
            year, month = match.groups()
            new_path = f"{server_id}/{year}/{month}"
            mega_mkdir(new_path)
            
            print(f"  [*] Moving legacy file {f} to {new_path}")
            if mega_mv(f, new_path + "/"):
                print(f"    [+] Moved {f}")
            else:
                print(f"    [-] Failed to move {f}")
    
    mega_logout()
    print(f"  [+] Account migration complete")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 migrate_mega_storage.py <SERVER_ID>")
        print("Example: python3 migrate_mega_storage.py zimpricecheck-server")
        sys.exit(1)
    
    server_id = sys.argv[1]
    
    print("="*50)
    print(f"  Mega Storage Migration: server_id = '{server_id}'")
    print("="*50)
    print()
    print("This will reorganize existing Mega backups into:")
    print(f"  /{server_id}/YYYY/MM/")
    print()
    
    confirm = input("Continue? [y/N]: ")
    if confirm.lower() != 'y':
        print("Aborted.")
        sys.exit(0)
    
    # Load Mega accounts from .env
    accounts = []
    for i in range(1, 4):
        email = os.getenv(f"MEGA_EMAIL_{i}", "")
        password = os.getenv(f"MEGA_PASSWORD_{i}", "")
        if email and password:
            accounts.append((email, password))
    
    if not accounts:
        print("[-] No Mega accounts found in .env")
        sys.exit(1)
    
    for email, password in accounts:
        migrate_account(email, password, server_id)
    
    print()
    print("="*50)
    print("  Migration Complete!")
    print("  DELETE THIS SCRIPT after verifying.")
    print("="*50)


if __name__ == "__main__":
    main()
