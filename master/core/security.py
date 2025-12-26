from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from master.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def encrypt_value(value: str) -> str:
    """
    Encrypt a value for storage.
    
    For simplicity, uses base64 encoding with a simple XOR cipher.
    In production, use proper encryption (Fernet, etc.)
    """
    import base64
    key = settings.SECRET_KEY[:32].ljust(32, '0')
    encrypted = bytes(a ^ ord(b) for a, b in zip(value.encode(), (key * ((len(value) // len(key)) + 1))))
    return base64.b64encode(encrypted).decode()


def decrypt_value(encrypted: str) -> str:
    """
    Decrypt a value from storage.
    """
    import base64
    key = settings.SECRET_KEY[:32].ljust(32, '0')
    decoded = base64.b64decode(encrypted.encode())
    decrypted = bytes(a ^ ord(b) for a, b in zip(decoded, (key * ((len(decoded) // len(key)) + 1))))
    return decrypted.decode()
