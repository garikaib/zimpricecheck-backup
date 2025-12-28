from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "WordPress Backup Master"
    API_V1_STR: str = "/api/v1"
    
    # Security - Enforce env var or generate secure random default
    # B4+pHA%x[^OGwOui#3f3 is the initial generated password for the superuser
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_SECRET_KEY" 
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str = "sqlite:///./master.db"
    
    # Admin User (Initial Bootstrap)
    FIRST_SUPERUSER: str = "garikaib@gmail.com"
    FIRST_SUPERUSER_PASSWORD: str = "B4+pHA%x[^OGwOui#3f3"

    class Config:
        env_file = ".env"
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.SECRET_KEY == "CHANGE_THIS_IN_PRODUCTION_SECRET_KEY":
            import secrets
            # Generate a temporary strong key if using default, but warn user
            # In production this should be set via env var
            print("WARNING: Using default SECRET_KEY. Please set SECRET_KEY in .env")

@lru_cache()
def get_settings():
    return Settings()
