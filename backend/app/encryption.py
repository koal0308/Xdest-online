"""
Encryption module for sensitive data like API tokens and keys.
Uses Fernet symmetric encryption (AES-128-CBC with HMAC).
"""
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def get_encryption_key() -> bytes:
    """
    Get or derive the encryption key from environment variable.
    Uses PBKDF2 to derive a proper Fernet key from the secret.
    """
    secret = os.getenv("ENCRYPTION_KEY", "dev-encryption-key-change-in-production")
    
    # Use PBKDF2 to derive a proper 32-byte key from any secret
    salt = b"xdest_salt_v1"  # Static salt (app-specific)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    return key


# Global Fernet instance
_fernet = None

def get_fernet() -> Fernet:
    """Get or create the Fernet instance."""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_encryption_key())
    return _fernet


def encrypt_token(plaintext: str) -> str:
    """
    Encrypt a plaintext string (e.g., API token).
    Returns base64-encoded encrypted string.
    """
    if not plaintext:
        return ""
    
    fernet = get_fernet()
    encrypted = fernet.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt_token(encrypted: str) -> str:
    """
    Decrypt an encrypted string back to plaintext.
    Returns empty string if decryption fails.
    """
    if not encrypted:
        return ""
    
    try:
        fernet = get_fernet()
        decrypted = fernet.decrypt(encrypted.encode())
        return decrypted.decode()
    except Exception:
        # If decryption fails, it might be an old unencrypted token
        # Return as-is for backwards compatibility during migration
        return encrypted


def is_encrypted(value: str) -> bool:
    """
    Check if a value appears to be Fernet-encrypted.
    Fernet tokens start with 'gAAAAA'.
    """
    if not value:
        return False
    return value.startswith("gAAAAA")
