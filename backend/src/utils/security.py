import bcrypt
import os
import base64
import hashlib
import logging
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class EncryptionManager:
    """
    Singleton class for managing encryption keys and operations.
    
    Replaces module-level global state with proper encapsulation.
    Thread-safe for the typical single-threaded startup use case.
    """
    _instance: Optional['EncryptionManager'] = None
    _encryption_key: Optional[str] = None
    
    def __new__(cls) -> 'EncryptionManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def set_key(self, key: str) -> None:
        """Set the encryption key."""
        if key:
            self._encryption_key = key
            logger.debug("Encryption key set successfully")
    
    def get_key(self) -> str:
        """Get the current encryption key or fall back to environment."""
        if self._encryption_key is not None:
            return self._encryption_key
        
        env_key = os.environ.get('ENCRYPTION_KEY', '')
        if not env_key:
            raise ValueError("ENCRYPTION_KEY not set. Call set_encryption_key() first or set ENCRYPTION_KEY environment variable.")
        return env_key
    
    def _derive_key(self, key: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """
        Derive encryption key using PBKDF2-HMAC-SHA256.
        
        This is a proper key derivation function (KDF) unlike simple SHA256 hashing.
        Uses 600,000 iterations (OWASP recommended minimum as of 2023).
        
        Args:
            key: Master password/key
            salt: Optional salt (generates random if None)
            
        Returns:
            Tuple of (derived_key, salt)
        """
        if salt is None:
            salt = secrets.token_bytes(16)  # 128-bit salt
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit key
            salt=salt,
            iterations=600000,  # OWASP 2023 recommendation
        )
        derived_key = kdf.derive(key.encode('utf-8'))
        return derived_key, salt
    
    def _get_fernet(self, salt: Optional[bytes] = None) -> Tuple[Fernet, bytes]:
        """
        Get Fernet instance with PBKDF2-derived key.
        
        Returns:
            Tuple of (Fernet instance, salt used)
        """
        key = self.get_key()
        derived_key, used_salt = self._derive_key(key, salt)
        fernet_key = base64.urlsafe_b64encode(derived_key)
        return Fernet(fernet_key), used_salt
    
    def encrypt(self, value: str) -> str:
        """
        Encrypt a value with salt prepended for storage.
        
        Format: base64(salt) + ':' + base64(encrypted_data)
        """
        if not value:
            return value
        try:
            f, salt = self._get_fernet()
            encrypted = f.encrypt(value.encode('utf-8'))
            # Prepend salt for decryption
            return base64.urlsafe_b64encode(salt).decode('utf-8') + ':' + encrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise ValueError(f"Failed to encrypt: {e}") from e
    
    def decrypt(self, encrypted_value: str) -> str:
        """
        Decrypt a value with salt extraction.
        
        Format expected: base64(salt) + ':' + base64(encrypted_data)
        
        SECURITY: Never silently return plaintext on failure.
        This prevents attackers from exploiting decryption failures.
        """
        if not encrypted_value:
            return encrypted_value
        
        try:
            # Check if value contains salt separator (new format)
            if ':' in encrypted_value:
                salt_b64, encrypted_data = encrypted_value.split(':', 1)
                salt = base64.urlsafe_b64decode(salt_b64.encode('utf-8'))
                f, _ = self._get_fernet(salt)
            else:
                # Legacy format without salt (will fail securely if wrong key)
                raise ValueError("Legacy format without salt detected")
            
            return f.decrypt(encrypted_data.encode('utf-8')).decode('utf-8')
            
        except (ValueError, TypeError) as e:
            # These are legitimate format errors - could be tampering or legacy format
            logger.error(f"Decryption format error: {e}")
            raise ValueError(f"Failed to decrypt - data may be corrupted or key incorrect") from e
            
        except Exception as e:
            # Any other error is a decryption failure
            logger.error(f"Decryption failed: {e}")
            raise ValueError(f"Failed to decrypt: incorrect key or corrupted data") from e


# Module-level convenience functions that delegate to singleton
_encryption_manager = EncryptionManager()

def set_encryption_key(key: str) -> None:
    """Set encryption key (delegates to EncryptionManager singleton)."""
    _encryption_manager.set_key(key)

def _get_fernet():
    """Get Fernet instance (delegates to EncryptionManager singleton)."""
    return _encryption_manager._get_fernet()

def encrypt_value(value: str) -> str:
    """Encrypt a single value using the EncryptionManager singleton."""
    return _encryption_manager.encrypt(value)

def decrypt_value(encrypted_value: str) -> str:
    """Decrypt a single value using the EncryptionManager singleton."""
    return _encryption_manager.decrypt(encrypted_value)

def encrypt_credentials(credentials: dict) -> dict:
    """
    Encrypt a dictionary of credential values using Fernet symmetric encryption.

    Each value is encrypted individually so partial decryption is safe.
    Non-string values (ints, bools) are preserved as-is.
    
    SECURITY: Raises ValueError if encryption key is not configured to prevent 
    unintentional storage of plaintext data.
    """
    encrypted = {}
    for k, v in credentials.items():
        if isinstance(v, str) and v:
            # This will raise ValueError if encryption key is missing
            encrypted[k] = _encryption_manager.encrypt(v)
        else:
            encrypted[k] = v  # Keep non-string values (ints, bools) as-is
    return encrypted


def decrypt_credentials(credentials: dict) -> dict:
    """
    Decrypt a dictionary of credential values encrypted by encrypt_credentials.

    Values that are not encrypted (plaintext legacy data) are returned as-is.
    
    SECURITY: If a value appears to be encrypted (contains ':') but decryption 
    fails, an error is raised and logged as CRITICAL to prevent data corruption.
    """
    decrypted = {}
    for k, v in credentials.items():
        if isinstance(v, str) and ':' in v:
            try:
                # Looks like an encrypted value (format: salt_b64:ciphertext)
                decrypted[k] = _encryption_manager.decrypt(v)
            except Exception as e:
                logger.critical(f"CRITICAL: Failed to decrypt credential for key '{k}': {e}")
                raise ValueError(f"Failed to decrypt credential '{k}'. The encryption key may be incorrect.") from e
        else:
            decrypted[k] = v  # Plaintext or non-string value
    return decrypted

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    pwd_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
    try:
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except (ValueError, TypeError) as e:
        logger.warning(f"Password verification error: {e}")
        return False

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode('utf-8')
