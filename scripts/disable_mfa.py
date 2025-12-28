
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.getcwd())

from master.db import models
from master.core.config import get_settings

def disable_mfa(email: str):
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            print(f"User {email} not found.")
            return

        print(f"Disabling MFA for user: {user.email}")
        user.mfa_enabled = False
        user.mfa_channel_id = None
        user.login_otp = None
        user.login_otp_expires = None
        
        db.commit()
        print("MFA disabled successfully.")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python disable_mfa.py <email>")
        sys.exit(1)
    
    disable_mfa(sys.argv[1])
