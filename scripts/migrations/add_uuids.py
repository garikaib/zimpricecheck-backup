#!/usr/bin/env python3
"""
Migration: Add UUIDs and storage tracking to nodes and sites.

This script adds:
- uuid column to nodes table
- uuid column to sites table
- storage_used_bytes to nodes table
- storage_quota_gb to sites table

Run with: python scripts/migrations/add_uuids.py
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
import uuid
from master.db.session import engine, SessionLocal


def run_migration():
    print("=" * 50)
    print("Running UUID Migration")
    print("=" * 50)
    
    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'nodes' AND column_name = 'uuid'
        """))
        nodes_has_uuid = result.fetchone() is not None
        
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sites' AND column_name = 'uuid'
        """))
        sites_has_uuid = result.fetchone() is not None
        
        # Add uuid to nodes if needed
        if not nodes_has_uuid:
            print("[*] Adding 'uuid' column to nodes table...")
            conn.execute(text("ALTER TABLE nodes ADD COLUMN uuid VARCHAR(36)"))
            conn.commit()
            
            # Generate UUIDs for existing nodes
            result = conn.execute(text("SELECT id FROM nodes WHERE uuid IS NULL"))
            nodes = result.fetchall()
            for node in nodes:
                new_uuid = str(uuid.uuid4())
                conn.execute(text("UPDATE nodes SET uuid = :uuid WHERE id = :id"), {"uuid": new_uuid, "id": node[0]})
                print(f"    Node {node[0]} -> {new_uuid}")
            conn.commit()
            
            # Make column NOT NULL and add index
            conn.execute(text("ALTER TABLE nodes ALTER COLUMN uuid SET NOT NULL"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_nodes_uuid ON nodes(uuid)"))
            conn.commit()
            print("[+] Nodes UUID migration complete!")
        else:
            print("[=] Nodes already have 'uuid' column, skipping...")
        
        # Add uuid to sites if needed
        if not sites_has_uuid:
            print("[*] Adding 'uuid' column to sites table...")
            conn.execute(text("ALTER TABLE sites ADD COLUMN uuid VARCHAR(36)"))
            conn.commit()
            
            # Generate UUIDs for existing sites
            result = conn.execute(text("SELECT id FROM sites WHERE uuid IS NULL"))
            sites = result.fetchall()
            for site in sites:
                new_uuid = str(uuid.uuid4())
                conn.execute(text("UPDATE sites SET uuid = :uuid WHERE id = :id"), {"uuid": new_uuid, "id": site[0]})
                print(f"    Site {site[0]} -> {new_uuid}")
            conn.commit()
            
            # Make column NOT NULL and add index
            conn.execute(text("ALTER TABLE sites ALTER COLUMN uuid SET NOT NULL"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_sites_uuid ON sites(uuid)"))
            conn.commit()
            print("[+] Sites UUID migration complete!")
        else:
            print("[=] Sites already have 'uuid' column, skipping...")
        
        # Add storage_used_bytes to nodes if needed
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'nodes' AND column_name = 'storage_used_bytes'
        """))
        if result.fetchone() is None:
            print("[*] Adding 'storage_used_bytes' column to nodes table...")
            conn.execute(text("ALTER TABLE nodes ADD COLUMN storage_used_bytes INTEGER DEFAULT 0"))
            conn.commit()
            print("[+] Added storage_used_bytes to nodes!")
        else:
            print("[=] Nodes already have 'storage_used_bytes' column, skipping...")
        
        # Add storage_quota_gb to sites if needed
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sites' AND column_name = 'storage_quota_gb'
        """))
        if result.fetchone() is None:
            print("[*] Adding 'storage_quota_gb' column to sites table...")
            conn.execute(text("ALTER TABLE sites ADD COLUMN storage_quota_gb INTEGER DEFAULT 10"))
            conn.commit()
            print("[+] Added storage_quota_gb to sites!")
        else:
            print("[=] Sites already have 'storage_quota_gb' column, skipping...")
    
    print("=" * 50)
    print("Migration Complete!")
    print("=" * 50)


if __name__ == "__main__":
    run_migration()
