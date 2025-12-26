from master.core.config import get_settings
from master.db.session import SessionLocal, engine
from master.db import models
from master.core.security import get_password_hash, encrypt_value
import secrets
import socket
import json

def init_db():
    settings = get_settings()
    # Create Tables
    models.Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Check if superuser exists
    user = db.query(models.User).filter(models.User.email == settings.FIRST_SUPERUSER).first()
    if not user:
        print(f"[*] Creating first superuser: {settings.FIRST_SUPERUSER}")
        user = models.User(
            email=settings.FIRST_SUPERUSER,
            hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
            full_name="Super Admin",
            role=models.UserRole.SUPER_ADMIN,
            is_verified=True,  # First user is auto-verified
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        print(f"[*] Superuser already exists: {settings.FIRST_SUPERUSER}")
        # Migrate: ensure existing users are verified
        if not user.is_verified:
            user.is_verified = True
            db.commit()
            print(f"[*] Marked existing superuser as verified")
    
    # Migrate: mark ALL existing users as verified
    unverified_count = db.query(models.User).filter(
        models.User.is_verified == False
    ).update({"is_verified": True})
    if unverified_count > 0:
        db.commit()
        print(f"[*] Migrated {unverified_count} existing users to verified status")
    
    # Check if Master node exists
    master_hostname = socket.gethostname()
    master_node = db.query(models.Node).filter(models.Node.hostname == master_hostname).first()
    if not master_node:
        print(f"[*] Creating Master node: {master_hostname}")
        master_node = models.Node(
            hostname=master_hostname,
            ip_address="127.0.0.1",
            api_key=secrets.token_urlsafe(32),
            status=models.NodeStatus.ACTIVE,
            storage_quota_gb=1000,  # Master has large quota
            admin_id=user.id,  # Assign to superuser
        )
        db.add(master_node)
        db.commit()
        print(f"[*] Master node created with ID: {master_node.id}")
    else:
        print(f"[*] Master node already exists: {master_hostname}")
    
    # Seed default email channel if none exists
    email_channel = db.query(models.CommunicationChannel).filter(
        models.CommunicationChannel.channel_type == models.ChannelType.EMAIL
    ).first()
    
    if not email_channel:
        print("[*] Creating default SendPulse API email channel")
        config = {
            "api_id": "76cf1854fb85c6f412098f52c4cdbd2e",
            "api_secret": "5911e725763f45b67477e45c41abce0b",
            "from_email": "business@zimpricecheck.com",
            "from_name": "WordPress Backup",
        }
        channel = models.CommunicationChannel(
            name="SendPulse API",
            channel_type=models.ChannelType.EMAIL,
            provider="sendpulse_api",
            config_encrypted=encrypt_value(json.dumps(config)),
            allowed_roles=json.dumps(["verification", "notification", "alert", "login_link"]),
            is_default=True,
            priority=1,
        )
        db.add(channel)
        
        # Also add SMTP fallback
        smtp_config = {
            "host": "smtp-pulse.com",
            "port": 587,
            "encryption": "tls",
            "username": "garikaib@gmail.com",
            "password": "Zten4ifS4CWn",
            "from_email": "business@zimpricecheck.com",
            "from_name": "WordPress Backup",
        }
        smtp_channel = models.CommunicationChannel(
            name="SendPulse SMTP",
            channel_type=models.ChannelType.EMAIL,
            provider="smtp",
            config_encrypted=encrypt_value(json.dumps(smtp_config)),
            allowed_roles=json.dumps(["verification", "notification", "alert", "login_link"]),
            is_default=False,
            priority=10,  # Lower priority (fallback)
        )
        db.add(smtp_channel)
        db.commit()
        print("[*] Created SendPulse API and SMTP email channels")
    else:
        print(f"[*] Email channel already exists: {email_channel.name}")
    
    db.close()

if __name__ == "__main__":
    print("Initializing Database...")
    init_db()
    print("Done!")


