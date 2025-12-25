from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from master.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
