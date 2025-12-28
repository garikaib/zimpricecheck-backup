import sys
import os

# Add project root to path (one level up from scripts)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def test_encryption():
    print("Testing encryption...")
    from master.core.encryption import encrypt_credential, decrypt_credential
    original = "secret_value"
    encrypted = encrypt_credential(original)
    decrypted = decrypt_credential(encrypted)
    
    assert original == decrypted
    assert original != encrypted
    print("Encryption test passed!")

def test_config():
    print("Testing config...")
    from master.core.config import get_settings
    settings = get_settings()
    print(f"SECRET_KEY length: {len(settings.SECRET_KEY)}")
    print(f"Superuser: {settings.FIRST_SUPERUSER}")
    # Verify default strong password is in place if not overridden
    if settings.FIRST_SUPERUSER == "garikaib@gmail.com":
         assert len(settings.FIRST_SUPERUSER_PASSWORD) > 10
    print("Config test passed!")

if __name__ == "__main__":
    try:
        test_encryption()
        test_config()
        print("All verification checks passed.")
    except Exception as e:
        print(f"Verification FAILED: {e}")
        sys.exit(1)
