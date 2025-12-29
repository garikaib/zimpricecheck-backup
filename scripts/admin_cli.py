#!/usr/bin/env python3
"""
WordPress Backup Admin CLI
Direct database access - bypasses FastAPI

Usage:
    ./admin.sh              # Interactive menu
    ./admin.sh reset-password user@example.com
    ./admin.sh disable-mfa user@example.com
    ./admin.sh list-users
"""
import sys
import os
import secrets
import json

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from master.db.session import SessionLocal, engine
from master.db import models
from master.core.security import get_password_hash
from master.core.encryption import encrypt_credential


def get_db():
    return SessionLocal()


def print_menu():
    print("""
╔═══════════════════════════════════════════════════╗
║         WordPress Backup Admin CLI                ║
╚═══════════════════════════════════════════════════╝

1. User Management
2. Storage Management
3. Node Management
4. System
0. Exit
""")


def print_user_menu():
    print("""
--- User Management ---
1. List users
2. Reset user password
3. Disable MFA for user
4. Create new admin
5. Verify user email
0. Back
""")


def print_storage_menu():
    print("""
--- Storage Management ---
1. List storage providers
2. Add S3-compatible storage
3. Set provider storage limit
4. Remove storage provider
0. Back
""")


def print_node_menu():
    print("""
--- Node Management ---
1. List nodes
2. Approve pending node
3. Block node
4. Set node quota
5. Remove node
0. Back
""")


def print_system_menu():
    print("""
--- System ---
1. View system status
2. Run database integrity check
3. Reset all quotas to 0
4. Clear stale stats (>1 hour)
5. DANGER: Reset database
0. Back
""")


# ==================== USER MANAGEMENT ====================

def list_users():
    db = get_db()
    users = db.query(models.User).all()
    print(f"\n{'ID':<5} {'Email':<35} {'Role':<15} {'Verified':<10} {'MFA':<5}")
    print("-" * 75)
    for u in users:
        print(f"{u.id:<5} {u.email:<35} {u.role.value:<15} {str(u.is_verified):<10} {str(u.mfa_enabled):<5}")
    db.close()


def reset_password(email=None):
    if not email:
        email = input("Enter user email: ").strip()
    
    db = get_db()
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user:
        print(f"❌ User not found: {email}")
        db.close()
        return
    
    new_password = secrets.token_urlsafe(12)
    user.hashed_password = get_password_hash(new_password)
    db.commit()
    
    print(f"\n✅ Password reset for {email}")
    print(f"   New password: {new_password}")
    print("   (User should change this after login)")
    db.close()


def disable_mfa(email=None):
    if not email:
        email = input("Enter user email: ").strip()
    
    db = get_db()
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user:
        print(f"❌ User not found: {email}")
        db.close()
        return
    
    user.mfa_enabled = False
    user.mfa_channel_id = None
    user.login_otp = None
    user.login_otp_expires = None
    db.commit()
    
    print(f"✅ MFA disabled for {email}")
    db.close()


def create_admin():
    email = input("Admin email: ").strip()
    full_name = input("Full name: ").strip()
    
    db = get_db()
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        print(f"❌ User already exists: {email}")
        db.close()
        return
    
    password = secrets.token_urlsafe(12)
    user = models.User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name,
        role=models.UserRole.SUPER_ADMIN,
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    
    print(f"\n✅ Admin created: {email}")
    print(f"   Password: {password}")
    db.close()


def verify_user_email(email=None):
    if not email:
        email = input("Enter user email: ").strip()
    
    db = get_db()
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user:
        print(f"❌ User not found: {email}")
        db.close()
        return
    
    user.is_verified = True
    user.email_verification_code = None
    user.email_verification_expires = None
    db.commit()
    
    print(f"✅ Email verified for {email}")
    db.close()


# ==================== STORAGE MANAGEMENT ====================

def list_storage_providers():
    db = get_db()
    providers = db.query(models.StorageProvider).all()
    
    if not providers:
        print("\n⚠️  No storage providers configured.")
        print("   Use 'Add S3-compatible storage' to add one.")
        db.close()
        return
    
    print(f"\n{'ID':<5} {'Name':<25} {'Type':<10} {'Limit (GB)':<12} {'Active':<8}")
    print("-" * 65)
    for p in providers:
        print(f"{p.id:<5} {p.name:<25} {p.provider_type:<10} {p.storage_limit_gb or 'N/A':<12} {str(p.is_active):<8}")
    db.close()


def add_s3_storage():
    print("\n--- Add S3-Compatible Storage ---")
    name = input("Provider name (e.g., 'iDrive E2 Production'): ").strip()
    endpoint = input("S3 Endpoint URL (e.g., 'https://e2.us-east-1.idrivee2.com'): ").strip()
    bucket = input("Bucket name: ").strip()
    access_key = input("Access Key ID: ").strip()
    secret_key = input("Secret Access Key: ").strip()
    region = input("Region (default: us-east-1): ").strip() or "us-east-1"
    storage_limit = input("Storage limit in GB (or leave blank for unlimited): ").strip()
    
    config = {
        "endpoint_url": endpoint,
        "bucket": bucket,
        "access_key_id": access_key,
        "secret_access_key": secret_key,
        "region": region,
    }
    
    db = get_db()
    provider = models.StorageProvider(
        name=name,
        provider_type="s3",
        config_encrypted=encrypt_credential(json.dumps(config)),
        storage_limit_gb=int(storage_limit) if storage_limit else None,
        is_active=True,
    )
    db.add(provider)
    db.commit()
    
    print(f"\n✅ Storage provider added: {name}")
    print(f"   ID: {provider.id}")
    db.close()


def set_provider_limit():
    list_storage_providers()
    provider_id = input("\nEnter provider ID: ").strip()
    limit_gb = input("New storage limit (GB): ").strip()
    
    db = get_db()
    provider = db.query(models.StorageProvider).filter(models.StorageProvider.id == int(provider_id)).first()
    if not provider:
        print(f"❌ Provider not found: {provider_id}")
        db.close()
        return
    
    provider.storage_limit_gb = int(limit_gb)
    db.commit()
    print(f"✅ Storage limit set to {limit_gb} GB for {provider.name}")
    db.close()


# ==================== NODE MANAGEMENT ====================

def list_nodes():
    db = get_db()
    nodes = db.query(models.Node).all()
    
    print(f"\n{'ID':<5} {'Hostname':<30} {'Status':<10} {'Quota (GB)':<12}")
    print("-" * 60)
    for n in nodes:
        print(f"{n.id:<5} {n.hostname:<30} {n.status.value:<10} {n.storage_quota_gb:<12}")
    db.close()


def approve_node():
    db = get_db()
    pending = db.query(models.Node).filter(models.Node.status == models.NodeStatus.PENDING).all()
    
    if not pending:
        print("\n✅ No pending nodes.")
        db.close()
        return
    
    print("\n--- Pending Nodes ---")
    for n in pending:
        print(f"  ID {n.id}: {n.hostname} ({n.ip_address})")
    
    node_id = input("\nEnter node ID to approve: ").strip()
    node = db.query(models.Node).filter(models.Node.id == int(node_id)).first()
    
    if node:
        node.status = models.NodeStatus.ACTIVE
        db.commit()
        print(f"✅ Node approved: {node.hostname}")
    db.close()


def block_node():
    list_nodes()
    node_id = input("\nEnter node ID to block: ").strip()
    
    db = get_db()
    node = db.query(models.Node).filter(models.Node.id == int(node_id)).first()
    if node:
        node.status = models.NodeStatus.BLOCKED
        db.commit()
        print(f"✅ Node blocked: {node.hostname}")
    db.close()


def set_node_quota():
    list_nodes()
    node_id = input("\nEnter node ID: ").strip()
    quota = input("New quota (GB): ").strip()
    
    db = get_db()
    node = db.query(models.Node).filter(models.Node.id == int(node_id)).first()
    if node:
        node.storage_quota_gb = int(quota)
        db.commit()
        print(f"✅ Quota set to {quota} GB for {node.hostname}")
    db.close()


# ==================== SYSTEM ====================

def system_status():
    db = get_db()
    
    users = db.query(models.User).count()
    nodes = db.query(models.Node).count()
    sites = db.query(models.Site).count()
    backups = db.query(models.Backup).count()
    providers = db.query(models.StorageProvider).count()
    
    total_quota = db.query(models.Node).with_entities(
        models.Node.storage_quota_gb
    ).all()
    total_allocated = sum(q[0] or 0 for q in total_quota)
    
    print(f"""
╔═══════════════════════════════════════╗
║           System Status               ║
╠═══════════════════════════════════════╣
║  Users:              {users:<16}║
║  Nodes:              {nodes:<16}║
║  Sites:              {sites:<16}║
║  Backups:            {backups:<16}║
║  Storage Providers:  {providers:<16}║
║  Total Allocated:    {total_allocated:<10} GB   ║
╚═══════════════════════════════════════╝
""")
    db.close()


def reset_quotas():
    confirm = input("⚠️  Reset ALL node quotas to 0? (type 'yes'): ").strip()
    if confirm != "yes":
        print("Cancelled.")
        return
    
    db = get_db()
    db.query(models.Node).update({"storage_quota_gb": 0})
    db.commit()
    print("✅ All quotas reset to 0.")
    db.close()


def clear_stale_stats():
    from datetime import datetime, timedelta
    db = get_db()
    cutoff = datetime.utcnow() - timedelta(hours=1)
    deleted = db.query(models.NodeStats).filter(models.NodeStats.timestamp < cutoff).delete()
    db.commit()
    print(f"✅ Cleared {deleted} stale stats records.")
    db.close()


def danger_reset_db():
    print("\n⚠️  DANGER: This will DELETE ALL DATA!")
    confirm = input("Type 'DELETE EVERYTHING' to confirm: ").strip()
    if confirm != "DELETE EVERYTHING":
        print("Cancelled.")
        return
    
    from master.db.session import engine
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    print("✅ Database reset. All data deleted.")
    print("   Run './deploy.sh master' to re-initialize.")


# ==================== MAIN MENU HANDLERS ====================

def handle_user_menu():
    while True:
        print_user_menu()
        choice = input("Select option: ").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            list_users()
        elif choice == "2":
            reset_password()
        elif choice == "3":
            disable_mfa()
        elif choice == "4":
            create_admin()
        elif choice == "5":
            verify_user_email()


def handle_storage_menu():
    while True:
        print_storage_menu()
        choice = input("Select option: ").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            list_storage_providers()
        elif choice == "2":
            add_s3_storage()
        elif choice == "3":
            set_provider_limit()


def handle_node_menu():
    while True:
        print_node_menu()
        choice = input("Select option: ").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            list_nodes()
        elif choice == "2":
            approve_node()
        elif choice == "3":
            block_node()
        elif choice == "4":
            set_node_quota()


def handle_system_menu():
    while True:
        print_system_menu()
        choice = input("Select option: ").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            system_status()
        elif choice == "3":
            reset_quotas()
        elif choice == "4":
            clear_stale_stats()
        elif choice == "5":
            danger_reset_db()


def main():
    # Handle CLI arguments for non-interactive use
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "reset-password" and len(sys.argv) > 2:
            reset_password(sys.argv[2])
        elif cmd == "disable-mfa" and len(sys.argv) > 2:
            disable_mfa(sys.argv[2])
        elif cmd == "list-users":
            list_users()
        elif cmd == "list-nodes":
            list_nodes()
        elif cmd == "list-storage":
            list_storage_providers()
        elif cmd == "status":
            system_status()
        else:
            print(f"Unknown command: {cmd}")
            print("Available: reset-password, disable-mfa, list-users, list-nodes, list-storage, status")
        return
    
    # Interactive menu
    while True:
        print_menu()
        choice = input("Select option: ").strip()
        
        if choice == "0":
            print("Goodbye!")
            break
        elif choice == "1":
            handle_user_menu()
        elif choice == "2":
            handle_storage_menu()
        elif choice == "3":
            handle_node_menu()
        elif choice == "4":
            handle_system_menu()


if __name__ == "__main__":
    main()
