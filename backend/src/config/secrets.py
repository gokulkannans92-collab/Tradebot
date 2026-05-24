"""
Secrets Management

Handles encryption/decryption of sensitive credentials.
Uses PBKDF2-HMAC-SHA256 for key derivation.
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from pathlib import Path

from src.utils.security import encrypt_value, decrypt_value, EncryptionManager
from src.utils.paths import get_data_dir

logger = logging.getLogger(__name__)


class SecureCredentialVault:
    """
    Secure encrypted storage for API credentials.
    
    Replaces plaintext .env files with encrypted credential storage.
    """
    
    def __init__(self):
        self.data_dir = get_data_dir()
        self.vault_file = os.path.join(self.data_dir, "credentials.enc")
        self._encryption_manager = EncryptionManager()
        self._cache: Dict[str, str] = {}
        self._loaded = False
    
    def set_master_key(self, key: str) -> None:
        """Set the master encryption key for the vault."""
        self._encryption_manager.set_key(key)
        logger.info("Credential vault encryption key set")
    
    def store_credential(self, key: str, value: str) -> None:
        """Store an encrypted credential in the vault."""
        if not value or not value.strip():
            raise ValueError(f"Cannot store empty credential for key: {key}")
        
        self._cache[key] = value
        self._save_vault()
        logger.info(f"Credential stored securely: {key}")
    
    def get_credential(self, key: str, default: str = "") -> str:
        """Retrieve a decrypted credential from the vault."""
        if not self._loaded:
            self._load_vault()
        
        return self._cache.get(key, default)
    
    def list_credentials(self) -> list:
        """List all stored credential keys (without values)."""
        if not self._loaded:
            self._load_vault()
        
        return list(self._cache.keys())
    
    def delete_credential(self, key: str) -> bool:
        """Delete a credential from the vault."""
        if key in self._cache:
            del self._cache[key]
            self._save_vault()
            logger.info(f"Credential deleted: {key}")
            return True
        return False
    
    def _save_vault(self) -> None:
        """Save encrypted credentials to file."""
        try:
            encrypted_data = self._encryption_manager.encrypt(json.dumps(self._cache))
            with open(self.vault_file, 'w') as f:
                f.write(encrypted_data)
        except Exception as e:
            logger.error(f"Failed to save credential vault: {e}")
            raise
    
    def _load_vault(self) -> None:
        """Load and decrypt credentials from file."""
        if not os.path.exists(self.vault_file):
            self._cache = {}
            self._loaded = True
            return
        
        try:
            with open(self.vault_file, 'r') as f:
                encrypted_data = f.read().strip()
            
            if not encrypted_data:
                self._cache = {}
            else:
                decrypted_data = self._encryption_manager.decrypt(encrypted_data)
                self._cache = json.loads(decrypted_data)
            
            self._loaded = True
            logger.info(f"Loaded {len(self._cache)} credentials from vault")
        except Exception as e:
            logger.error(f"Failed to load credential vault: {e}")
            self._cache = {}
            self._loaded = False  # Mark as not loaded on failure
            raise RuntimeError(f"Could not load secure vault: {e}") from e


class SecretsManager:
    """
    Manages encrypted secrets and credentials.
    
    This class provides a secure interface for storing and retrieving
    sensitive configuration like API keys and passwords.
    """
    
    _instance: Optional["SecretsManager"] = None
    
    def __new__(cls):
        """Singleton pattern to ensure single encryption key."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._encryption_manager = EncryptionManager()
        self._cache: Dict[str, str] = {}
        self._initialized = True
    
    def set_master_key(self, key: str) -> None:
        """
        Set the master encryption key.
        
        Must be called before any encrypt/decrypt operations.
        
        Args:
            key: Master encryption key (min 12 characters recommended)
        """
        self._encryption_manager.set_key(key)
        logger.info("Master encryption key set")
    
    def encrypt(self, value: str) -> str:
        """
        Encrypt a value.
        
        Args:
            value: Plaintext value to encrypt
            
        Returns:
            Encrypted string (includes salt)
        """
        return self._encryption_manager.encrypt(value)
    
    def decrypt(self, encrypted_value: str) -> str:
        """
        Decrypt an encrypted value.
        
        Args:
            encrypted_value: Encrypted string from encrypt()
            
        Returns:
            Decrypted plaintext
            
        Raises:
            ValueError: If decryption fails
        """
        return self._encryption_manager.decrypt(encrypted_value)
    
    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """
        Encrypt a dictionary.
        
        Args:
            data: Dictionary to encrypt
            
        Returns:
            Encrypted JSON string
        """
        json_str = json.dumps(data)
        return self.encrypt(json_str)
    
    def decrypt_dict(self, encrypted_value: str) -> Dict[str, Any]:
        """
        Decrypt to dictionary.
        
        Args:
            encrypted_value: Encrypted JSON string
            
        Returns:
            Decrypted dictionary
            
        Raises:
            ValueError: If decryption fails
        """
        decrypted = self.decrypt(encrypted_value)
        return json.loads(decrypted)


# Convenience functions for module-level usage
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """Get or create the global secrets manager instance."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def encrypt_credentials(credentials: Dict[str, str]) -> str:
    """
    Encrypt credentials dictionary.
    
    Args:
        credentials: Dictionary of credentials to encrypt
        
    Returns:
        Encrypted string
    """
    return get_secrets_manager().encrypt_dict(credentials)


def decrypt_credentials(encrypted: str) -> Dict[str, str]:
    """
    Decrypt credentials string.
    
    Args:
        encrypted: Encrypted credentials
        
    Returns:
        Decrypted credentials dictionary
    """
    return get_secrets_manager().decrypt_dict(encrypted)


def set_encryption_key(key: str) -> None:
    """Set the global encryption key."""
    get_secrets_manager().set_master_key(key)


