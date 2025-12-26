from master.core.config import get_settings
from master.db.session import SessionLocal, engine
from master.db import models
from master.core.security import get_password_hash
import secrets
import socket

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
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        print(f"[*] Superuser already exists: {settings.FIRST_SUPERUSER}")
    
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
    
    db.close()

if __name__ == "__main__":
    print("Initializing Database...")
    init_db()
    print("Done!")

