"""
Cloudflare Turnstile verification utility.
"""
import httpx
from sqlalchemy.orm import Session
from master.db import models


TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def get_turnstile_secret(db: Session) -> str | None:
    """Get Turnstile secret from settings."""
    setting = db.query(models.Settings).filter(models.Settings.key == "turnstile_secret").first()
    return setting.value if setting else None


def is_turnstile_enabled(db: Session) -> bool:
    """Check if Turnstile is enabled."""
    setting = db.query(models.Settings).filter(models.Settings.key == "turnstile_enabled").first()
    return setting.value == "true" if setting else False


def verify_turnstile_token(token: str, secret: str, ip: str = None) -> bool:
    """
    Verify a Turnstile token with Cloudflare.
    Returns True if valid, False otherwise.
    """
    if not token or not secret:
        return False
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                TURNSTILE_VERIFY_URL,
                data={
                    "secret": secret,
                    "response": token,
                    "remoteip": ip,
                }
            )
            result = response.json()
            return result.get("success", False)
    except Exception as e:
        print(f"[Turnstile] Verification error: {e}")
        return False
