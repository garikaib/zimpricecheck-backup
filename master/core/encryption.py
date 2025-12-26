"""
Credential Encryption Utility

Uses Fernet symmetric encryption with key derived from SECRET_KEY.
Credentials are encrypted at rest and decrypted only when needed.
"""
import base64
import hashlib
from cryptography.fernet import Fernet
from master.core.config import get_settings


def _get_fernet() -> Fernet:
    """Get Fernet instance using derived key from SECRET_KEY."""
    settings = get_settings()
    # Derive a 32-byte key from SECRET_KEY using SHA256
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    # Fernet requires base64-encoded 32-byte key
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt_credential(value: str) -> str:
    """
    Encrypt a credential value.
    Returns base64-encoded encrypted string.
    """
    if not value:
        return ""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(value.encode())
    return encrypted.decode()


def decrypt_credential(encrypted: str) -> str:
    """
    Decrypt an encrypted credential value.
    Returns the original plaintext string.
    """
    if not encrypted:
        return ""
    try:
        fernet = _get_fernet()
        decrypted = fernet.decrypt(encrypted.encode())
        return decrypted.decode()
    except Exception as e:
        print(f"[Encryption] Decryption failed: {e}")
        return ""
