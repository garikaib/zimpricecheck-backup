from master.core.config import get_settings
from master.db.session import SessionLocal, engine
from master.db import models
from master.core.security import get_password_hash

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
    else:
        print(f"[*] Superuser already exists: {settings.FIRST_SUPERUSER}")

if __name__ == "__main__":
    print("Initializing Database...")
    init_db()
    print("Done!")
