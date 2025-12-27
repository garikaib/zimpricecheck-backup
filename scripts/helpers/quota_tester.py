#!/usr/bin/env python3
"""
Quota Tester Helper

Python helper for testing quota warning flow and cleanup scheduling.
"""
import sys
import os
import argparse
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, timedelta


def check_quota_status(site_id: int):
    """Check quota status for a site."""
    from master.db.session import SessionLocal
    from master.db import models
    from master.core.quota_manager import check_quota_status
    
    db = SessionLocal()
    try:
        site = db.query(models.Site).filter(models.Site.id == site_id).first()
        if not site:
            print(f"Site {site_id} not found")
            return
        
        status = check_quota_status(site)
        print(json.dumps(status, indent=2, default=str))
        
    finally:
        db.close()


def simulate_over_quota(site_id: int, used_gb: float):
    """Simulate a site being over quota by setting usage."""
    from master.db.session import SessionLocal
    from master.db import models
    
    db = SessionLocal()
    try:
        site = db.query(models.Site).filter(models.Site.id == site_id).first()
        if not site:
            print(f"Site {site_id} not found")
            return
        
        old_used = site.storage_used_bytes or 0
        site.storage_used_bytes = int(used_gb * (1024 ** 3))
        db.commit()
        
        print(f"Site {site.name} storage set to {used_gb} GB")
        print(f"Old: {round(old_used / (1024**3), 2)} GB")
        print(f"New: {used_gb} GB")
        print(f"Quota: {site.storage_quota_gb} GB")
        
    finally:
        db.close()


def list_scheduled_deletions():
    """List all backups scheduled for deletion."""
    from master.db.session import SessionLocal
    from master.db import models
    
    db = SessionLocal()
    try:
        scheduled = db.query(models.Backup).filter(
            models.Backup.scheduled_deletion != None
        ).all()
        
        if not scheduled:
            print("No backups scheduled for deletion")
            return
        
        print(f"Found {len(scheduled)} backups scheduled for deletion:")
        for b in scheduled:
            site_name = b.site.name if b.site else "Unknown"
            print(f"  - {b.filename} (Site: {site_name})")
            print(f"    Scheduled: {b.scheduled_deletion}")
            print(f"    Size: {round((b.size_bytes or 0) / (1024**3), 2)} GB")
        
    finally:
        db.close()


def run_cleanup():
    """Run the scheduled cleanup manually."""
    from master.db.session import SessionLocal
    from master.core.cleanup_scheduler import run_scheduled_cleanup
    
    db = SessionLocal()
    try:
        result = run_scheduled_cleanup(db)
        print(json.dumps(result, indent=2, default=str))
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Quota System Tester")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Check quota status
    check_parser = subparsers.add_parser("check", help="Check quota status for a site")
    check_parser.add_argument("site_id", type=int, help="Site ID")
    
    # Simulate over quota
    simulate_parser = subparsers.add_parser("simulate", help="Simulate storage usage")
    simulate_parser.add_argument("site_id", type=int, help="Site ID")
    simulate_parser.add_argument("used_gb", type=float, help="Used storage in GB")
    
    # List scheduled deletions
    subparsers.add_parser("list-scheduled", help="List scheduled deletions")
    
    # Run cleanup
    subparsers.add_parser("cleanup", help="Run scheduled cleanup")
    
    args = parser.parse_args()
    
    if args.command == "check":
        check_quota_status(args.site_id)
    elif args.command == "simulate":
        simulate_over_quota(args.site_id, args.used_gb)
    elif args.command == "list-scheduled":
        list_scheduled_deletions()
    elif args.command == "cleanup":
        run_cleanup()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
