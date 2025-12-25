import sys
import argparse
from sqlalchemy.orm import Session
from master.db import models
from master.db.session import SessionLocal
from master.core.security import get_password_hash

def create_admin(email, password, full_name="Admin"):
    db = SessionLocal()
    
    # Check if exists
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        print(f"[!] User {email} already exists.")
        return

    user = models.User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name,
        role=models.UserRole.SUPER_ADMIN,
        is_active=True
    )
    db.add(user)
    db.commit()
    print(f"[+] Super Admin created: {email}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new Super Admin")
    parser.add_argument("email", help="Admin Email")
    parser.add_argument("password", help="Admin Password")
    parser.add_argument("--name", default="Admin", help="Full Name")
    
    args = parser.parse_args()
    
    create_admin(args.email, args.password, args.name)
