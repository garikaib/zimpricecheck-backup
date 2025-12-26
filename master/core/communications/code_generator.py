"""
Verification Code Generator

Generates alphanumeric codes for email verification, consistent with node registration codes.
"""
import secrets
import string


def generate_verification_code(length: int = 6) -> str:
    """
    Generate an alphanumeric verification code.
    
    Uses uppercase letters and digits, excluding confusing characters
    (0, O, I, 1, L) for better readability.
    
    Args:
        length: Code length (default 6)
    
    Returns:
        Alphanumeric code like "A3X9K2"
    """
    # Base character set
    chars = string.ascii_uppercase + string.digits
    # Remove confusing characters: 0, O, I, 1, L
    excluded = '0OI1L'
    chars = ''.join(c for c in chars if c not in excluded)
    
    return ''.join(secrets.choice(chars) for _ in range(length))


def generate_magic_link_token(length: int = 32) -> str:
    """
    Generate a secure token for magic link login.
    
    Args:
        length: Token length in bytes (default 32)
    
    Returns:
        URL-safe token string
    """
    return secrets.token_urlsafe(length)
