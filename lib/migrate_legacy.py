#!/usr/bin/env python3
"""
Migrate Legacy Backups
Moves backup files from root to YYYY/MM/ folder structure.
"""

import sys
import re
import subprocess
import time
from backup_manager import MEGA_ACCOUNTS, mega_login, mega_logout, mega_list_files, mega_mkdir

def mega_move(filename, target_path):
    """Move a file to a new location."""
    # mega-mv filename target_path
    cmd = ["mega-mv", filename, target_path]
    result = subprocess.run(
        cmd,
        capture_output=True, text=True, timeout=60
    )
    return result.returncode == 0

def migrate_account(account):
    print(f"[*] Migrating account: {account['email']}")
    
    if not mega_login(account['email'], account['password']):
        print(f"[!] Failed to login to {account['email']}")
        return

    try:
        # List files in root
        files = mega_list_files()
        
        migrated_count = 0
        
        for file_info in files:
            name = file_info['name']
            
            # Check if it's a backup file in root (not a directory)
            # mega_list_files returns names. If it's a directory, our date parsing will likely fail or we can check.
            # Filename format: wp-backup-YYYYMMDD-HHMMSS.tar.zst
            
            if name.startswith('wp-backup-') and name.endswith('.tar.zst'):
                # Extract date
                try:
                    # wp-backup-20241224-000000.tar.zst
                    date_part = name.replace('wp-backup-', '').split('-')[0]
                    if len(date_part) == 8:
                        year = date_part[:4]
                        month = date_part[4:6]
                        
                        target_dir = f"{year}/{month}"
                        target_path = f"{target_dir}/{name}"
                        
                        print(f"    -> Moving {name} to {target_dir}...")
                        
                        # Create directory
                        if not mega_mkdir(target_dir):
                            print(f"       [!] Failed to create dir {target_dir}")
                            continue
                            
                        # Move file
                        if mega_move(name, target_path):
                            print("       [OK] Moved.")
                            migrated_count += 1
                        else:
                            print("       [!] Move failed.")
                            
                except Exception as e:
                    print(f"       [!] Error processing {name}: {e}")
                    
        print(f"[*] Finished account {account['email']}. Migrated {migrated_count} files.")
        
    finally:
        mega_logout()

def main():
    print("=== WordPress Backup Migration Tool ===")
    
    if not MEGA_ACCOUNTS:
        print("[!] No Mega accounts configured.")
        return
        
    for account in MEGA_ACCOUNTS:
        migrate_account(account)
        
    print("\n=== Migration Complete ===")

if __name__ == "__main__":
    main()
