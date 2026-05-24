"""
Secure Credential Storage

Provides secure storage for sensitive credentials with:
- Key rotation support
- Versioned encryption
- Secure deletion
- Audit logging
"""

import os
import json
import hashlib
import secrets
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path

from src.utils.security import EncryptionManager

logger = logging.getLogger(__name__)


@dataclass
class KeyVersion:
    """Represents a key version for rotation tracking."""
    version: int
    created_at: datetime
    expires_at: Optional[datetime]
    hash_prefix: str  # First 8 chars of key hash for identification


class SecureCredentialStore:
    """
    Secure storage for sensitive credentials with key rotation.
    
    Features:
    - Automatic key rotation
    - Versioned encryption
    - Secure deletion (overwrite before delete)
    - Metadata tracking
    """
    
    def __init__(self, storage_path: str, rotation_days: int = 90):
        """
        Initialize secure credential store.
        
        Args:
            storage_path: Path to encrypted credential file
            rotation_days: Days between key rotations
        """
        self.storage_path = Path(storage_path)
        self.rotation_days = rotation_days
        self.metadata_path = self.storage_path.parent / f"{self.storage_path.stem}.meta"
        
        self._encryption_manager = EncryptionManager()
        self._current_key_version = 1
        self._key_versions: Dict[int, KeyVersion] = {}
        
        self._load_metadata()
    
    def _load_metadata(self):
        """Load key version metadata."""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, 'r') as f:
                    data = json.load(f)
                    self._current_key_version = data.get('current_version', 1)
                    versions = data.get('versions', {})
                    for v, info in versions.items():
                        self._key_versions[int(v)] = KeyVersion(
                            version=int(v),
                            created_at=datetime.fromisoformat(info['created_at']),
                            expires_at=datetime.fromisoformat(info['expires_at']) if info.get('expires_at') else None,
                            hash_prefix=info['hash_prefix']
                        )
            except Exception as e:
                logger.warning(f"Failed to load key metadata: {e}")
                self._current_key_version = 1
                self._key_versions = {}
    
    def _save_metadata(self):
        """Save key version metadata."""
        data = {
            'current_version': self._current_key_version,
            'versions': {
                str(v.version): {
                    'created_at': v.created_at.isoformat(),
                    'expires_at': v.expires_at.isoformat() if v.expires_at else None,
                    'hash_prefix': v.hash_prefix
                }
                for v in self._key_versions.values()
            }
        }
        
        # Write to temp file then move (atomic operation)
        temp_path = self.metadata_path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=2)
        temp_path.replace(self.metadata_path)
    
    def _check_rotation_needed(self) -> bool:
        """Check if key rotation is needed."""
        current = self._key_versions.get(self._current_key_version)
        if not current:
            return True
        
        age = datetime.now() - current.created_at
        return age > timedelta(days=self.rotation_days)
    
    def rotate_key(self, new_key: str):
        """
        Rotate to a new encryption key.
        
        Args:
            new_key: New encryption key
            
        Note:
            This will re-encrypt all stored credentials with the new key.
        """
        if not new_key:
            raise ValueError("New key cannot be empty")
        
        logger.info(f"Starting key rotation from version {self._current_key_version}")
        
        # Load all existing credentials
        credentials = self.load_all_credentials()
        
        # Archive old key version
        old_version = self._key_versions.get(self._current_key_version)
        if old_version:
            old_version.expires_at = datetime.now() + timedelta(days=30)  # 30 day grace period
        
        # Create new key version
        self._current_key_version += 1
        key_hash = hashlib.sha256(new_key.encode()).hexdigest()[:16]
        
        self._key_versions[self._current_key_version] = KeyVersion(
            version=self._current_key_version,
            created_at=datetime.now(),
            expires_at=None,
            hash_prefix=key_hash[:8]
        )
        
        # Set new key
        self._encryption_manager.set_key(new_key)
        
        # Re-encrypt all credentials
        self._save_all_credentials(credentials)
        self._save_metadata()
        
        logger.info(f"Key rotation complete. New version: {self._current_key_version}")
    
    def store_credential(self, key: str, value: str, metadata: Optional[Dict] = None):
        """
        Store a credential securely.
        
        Args:
            key: Credential identifier
            value: Credential value to encrypt
            metadata: Optional metadata (stored unencrypted)
        """
        if not key or not value:
            raise ValueError("Key and value cannot be empty")
        
        # Check if rotation needed
        if self._check_rotation_needed():
            logger.warning("Key rotation overdue! Consider rotating keys.")
        
        # Load existing credentials
        credentials = self.load_all_credentials()
        
        # Store with encryption
        encrypted_value = self._encryption_manager.encrypt(value)
        
        credentials[key] = {
            'value': encrypted_value,
            'version': self._current_key_version,
            'stored_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        self._save_all_credentials(credentials)
        logger.debug(f"Stored credential: {key} (version {self._current_key_version})")
    
    def load_credential(self, key: str) -> Optional[str]:
        """
        Load and decrypt a credential.
        
        Args:
            key: Credential identifier
            
        Returns:
            Decrypted value or None if not found
        """
        credentials = self.load_all_credentials()
        
        if key not in credentials:
            return None
        
        cred_data = credentials[key]
        encrypted_value = cred_data.get('value')
        
        if not encrypted_value:
            return None
        
        try:
            decrypted = self._encryption_manager.decrypt(encrypted_value)
            return decrypted
        except Exception as e:
            # Log at DEBUG - will fall back to .env credentials
            logger.debug(f"Could not decrypt credential {key} (using .env fallback): {e}")
            return None
    
    def delete_credential(self, key: str, secure: bool = True):
        """
        Delete a credential securely.
        
        Args:
            key: Credential identifier
            secure: If True, overwrite data before deletion
        """
        if not self.storage_path.exists():
            return
        
        if secure:
            # Load and overwrite the specific credential
            credentials = self.load_all_credentials()
            
            if key in credentials:
                # Overwrite with random data before deletion
                credentials[key]['value'] = secrets.token_hex(256)
                credentials[key]['metadata'] = {'deleted': True}
                self._save_all_credentials(credentials)
        
        # Now remove it
        credentials = self.load_all_credentials()
        credentials.pop(key, None)
        self._save_all_credentials(credentials)
        
        logger.info(f"Securely deleted credential: {key}")
    
    def load_all_credentials(self) -> Dict[str, Any]:
        """Load all credentials from storage."""
        if not self.storage_path.exists():
            return {}
        
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error("Corrupted credential storage")
            return {}
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return {}
    
    def _save_all_credentials(self, credentials: Dict[str, Any]):
        """Save all credentials to storage atomically."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        temp_path = self.storage_path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(credentials, f, indent=2)
        
        # Atomic replace
        temp_path.replace(self.storage_path)
        
        # Set restrictive permissions (owner read/write only)
        os.chmod(self.storage_path, 0o600)
    
    def list_credentials(self) -> Dict[str, Dict]:
        """
        List all stored credentials (metadata only, no values).
        
        Returns:
            Dict of credential keys to their metadata
        """
        credentials = self.load_all_credentials()
        return {
            key: {
                'version': data.get('version'),
                'stored_at': data.get('stored_at'),
                'metadata': data.get('metadata', {})
            }
            for key, data in credentials.items()
        }
    
    def audit_log(self) -> str:
        """Generate audit log of credential storage."""
        credentials = self.list_credentials()
        
        log_lines = [
            f"Secure Storage Audit - {datetime.now().isoformat()}",
            f"Storage Path: {self.storage_path}",
            f"Current Key Version: {self._current_key_version}",
            f"Key Rotation Period: {self.rotation_days} days",
            "",
            "Key Versions:",
        ]
        
        for version in sorted(self._key_versions.values(), key=lambda v: v.version):
            status = "ACTIVE" if version.version == self._current_key_version else "ARCHIVED"
            if version.expires_at and version.expires_at < datetime.now():
                status = "EXPIRED"
            log_lines.append(f"  Version {version.version}: {status} (hash: {version.hash_prefix}...)")
        
        log_lines.extend(["", "Stored Credentials:"])
        for key, meta in credentials.items():
            log_lines.append(f"  {key}: version {meta['version']}, stored {meta['stored_at']}")
        
        return '\n'.join(log_lines)


# Singleton instance for application-wide use
_credential_store: Optional[SecureCredentialStore] = None


def init_secure_storage(storage_path: str, rotation_days: int = 90) -> SecureCredentialStore:
    """Initialize global secure credential storage."""
    global _credential_store
    _credential_store = SecureCredentialStore(storage_path, rotation_days)
    return _credential_store


def get_secure_storage() -> Optional[SecureCredentialStore]:
    """Get global secure credential storage instance."""
    return _credential_store


def store_credential(key: str, value: str, metadata: Optional[Dict] = None):
    """Store credential in global secure storage."""
    if _credential_store is None:
        raise RuntimeError("Secure storage not initialized. Call init_secure_storage() first.")
    _credential_store.store_credential(key, value, metadata)


def load_credential(key: str) -> Optional[str]:
    """Load credential from global secure storage."""
    if _credential_store is None:
        raise RuntimeError("Secure storage not initialized")
    return _credential_store.load_credential(key)


def delete_credential(key: str, secure: bool = True):
    """Delete credential from global secure storage."""
    if _credential_store is None:
        raise RuntimeError("Secure storage not initialized")
    _credential_store.delete_credential(key, secure)
