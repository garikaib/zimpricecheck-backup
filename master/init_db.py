from master.core.config import get_settings
from master.db.session import SessionLocal, engine
from master.db import models
from master.core.security import get_password_hash
from master.core.encryption import encrypt_credential
import secrets
import socket
import json
import logging
from sqlalchemy import inspect, text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_python_type(col_type):
    """Map SQLAlchemy types to SQLite types for ADD COLUMN."""
    type_str = str(col_type).lower()
    if "integer" in type_str: return "INTEGER"
    if "string" in type_str or "varchar" in type_str: return "VARCHAR"
    if "boolean" in type_str: return "BOOLEAN"
    if "datetime" in type_str: return "DATETIME"
    if "float" in type_str: return "FLOAT"
    # SQLite stores enums as strings (VARCHAR)
    return "VARCHAR"


def check_and_fix_schema():
    """
    Integrity Check: Compares DB schema against SQLAlchemy models 
    and adds missing columns automatically.
    """
    logger.info("[integrity] Starting Schema Integrity Check...")
    inspector = inspect(engine)
    db_tables = inspector.get_table_names()
    
    # Get all model classes from models.py
    import inspect as py_inspect
    from sqlalchemy.orm import DeclarativeMeta
    
    model_classes = []
    for name, obj in py_inspect.getmembers(models):
        if isinstance(obj, DeclarativeMeta) and hasattr(obj, "__tablename__"):
            model_classes.append(obj)
    
    with engine.connect() as conn:
        for model in model_classes:
            table_name = model.__tablename__
            
            # 1. Create table if missing
            if table_name not in db_tables:
                logger.info(f"[integrity] Table {table_name} missing. Creating...")
                model.__table__.create(engine)
                continue
                
            # 2. Check for missing columns
            existing_columns = {c["name"]: c for c in inspector.get_columns(table_name)}
            
            for col_name, col_obj in model.__table__.columns.items():
                if col_name not in existing_columns:
                    logger.info(f"[integrity] Missing column in {table_name}: {col_name}")
                    
                    # Determine basic type
                    col_type = get_python_type(col_obj.type)
                    
                    # Safe ADD COLUMN
                    # Note: We avoid DEFAULT clauses that might cause syntax errors with SQLite 
                    # unless strictly necessary. Better to ADD then UPDATE if needed.
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
                    
                    try:
                        conn.execute(text(sql))
                        conn.commit()
                        logger.info(f"[integrity] Added column {table_name}.{col_name}")
                        
                        # Populate default if available and simple
                        if col_obj.default and col_obj.default.arg is not None:
                            val = col_obj.default.arg
                            if not callable(val):
                                # Only apply static defaults
                                update_sql = text(f"UPDATE {table_name} SET {col_name} = :val WHERE {col_name} IS NULL")
                                conn.execute(update_sql, {"val": val})
                                conn.commit()
                                logger.info(f"[integrity] Populated default for {table_name}.{col_name}")

                    except Exception as e:
                        logger.error(f"[integrity] Failed to add column {table_name}.{col_name}: {e}")

    logger.info("[integrity] Schema Integrity Check Complete.")


def init_db():
    settings = get_settings()
    
    # 1. Integrity Check & Schema Repair
    check_and_fix_schema()
    
    # Ensure tables exist (redundant but safe)
    models.Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # 2. Setup Superuser requested by user (garikaib@gmail.com)
    target_email = "garikaib@gmail.com"
    user = db.query(models.User).filter(models.User.email == target_email).first()
    
    if not user:
        # Generate secure random password
        random_password = secrets.token_urlsafe(12)
        print(f"\n{'='*50}")
        print(f"[*] Creating SUPERUSER: {target_email}")
        print(f"[*] PASSWORD: {random_password}")
        print(f"{'='*50}\n")
        
        user = models.User(
            email=target_email,
            hashed_password=get_password_hash(random_password),
            full_name="Super Admin",
            role=models.UserRole.SUPER_ADMIN,
            is_verified=True, 
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        logger.info(f"[*] Superuser {target_email} already exists.")
        # Ensure verification
        if not user.is_verified:
            user.is_verified = True
            db.commit()
            logger.info("Verified existing superuser.")

    # 3. Ensure Master Node Record
    master_hostname = socket.gethostname()
    master_node = db.query(models.Node).filter(models.Node.hostname == master_hostname).first()
    if not master_node:
        logger.info(f"[*] Creating Master node record: {master_hostname}")
        master_node = models.Node(
            hostname=master_hostname,
            ip_address="127.0.0.1",
            api_key=secrets.token_urlsafe(32),
            status=models.NodeStatus.ACTIVE,
            storage_quota_gb=0,  # Start at 0 - allocations tied to remote storage
            admin_id=user.id,
        )
        db.add(master_node)
        db.commit()
    
    # 3b. Reset any inflated quotas (cleanup from old defaults)
    # Quotas should be 0 until remote storage is configured and allocations are made
    inflated_count = db.query(models.Node).filter(models.Node.storage_quota_gb > 0).count()
    if inflated_count > 0:
        logger.info(f"[cleanup] Resetting {inflated_count} nodes with inflated quotas to 0...")
        db.query(models.Node).update({"storage_quota_gb": 0})
        db.commit()
    
    # 4. Seed Communication Channels (Pulse API + SMTP)
    email_channel = db.query(models.CommunicationChannel).filter(
        models.CommunicationChannel.channel_type == models.ChannelType.EMAIL
    ).first()
    
    if not email_channel:
        logger.info("[*] Seeding default email channels...")
        
        # Pulse API
        pulse_config = {
            "client_id": "76cf1854fb85c6f412098f52c4cdbd2e",
            "client_secret": "5911e725763f45b67477e45c41abce0b",
            "from_email": "business@zimpricecheck.com",
            "from_name": "WordPress Backup",
        }
        pulse = models.CommunicationChannel(
            name="SendPulse API",
            channel_type=models.ChannelType.EMAIL,
            provider="sendpulse_api",
            config_encrypted=encrypt_credential(json.dumps(pulse_config)),
            allowed_roles=json.dumps(["verification", "notification", "alert", "login_link"]),
            is_default=True,
            priority=1,
        )
        db.add(pulse)
        
        # SMTP Fallback
        smtp_config = {
            "host": "smtp-pulse.com",
            "port": 587, 
            "username": "garikaib@gmail.com", 
            "password": "Zten4ifS4CWn",
            "from_email": "business@zimpricecheck.com",
            "from_name": "WordPress Backup",
            "use_tls": True
        }
        smtp = models.CommunicationChannel(
            name="SendPulse SMTP",
            channel_type=models.ChannelType.EMAIL,
            provider="smtp",
            config_encrypted=encrypt_credential(json.dumps(smtp_config)),
            allowed_roles=json.dumps(["verification", "notification", "alert", "login_link"]),
            is_default=False,
            priority=10,
        )
        db.add(smtp)
        db.commit()
        logger.info("[*] Email channels created.")

    # 5. Ensure System Settings
    default_settings = {
        "site_name": "WordPress Backup Master",
        "admin_email": target_email,
        "system_email_from": "business@zimpricecheck.com"
    }
    for key, val in default_settings.items():
        if not db.query(models.Settings).filter_by(key=key).first():
            db.add(models.Settings(key=key, value=val))
    db.commit()
    
    db.close()

if __name__ == "__main__":
    init_db()
