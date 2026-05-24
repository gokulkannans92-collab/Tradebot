"""
User Manager Module

Manages user data - loading, saving, validation.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from src.utils.security import decrypt_credentials, encrypt_credentials
from src.utils.paths import ensure_paths

logger = logging.getLogger(__name__)

DATA_DIR = ensure_paths()


class UserManager:
    """Manages user data - loading, saving, validation."""
    
    USERS_FILE = os.path.join(DATA_DIR, "users.json")
    
    @staticmethod
    def validate_user(user: dict) -> bool:
        """Validate user data structure."""
        required = ["user_id", "name", "broker_type"]
        for field in required:
            if field not in user or not user[field]:
                return False
        
        # Validate broker type
        valid_brokers = ["ZERODHA", "ANGEL", "UPSTOX", "GROWW", "MOCK"]
        if user.get("broker_type", "").upper() not in valid_brokers:
            return False
        
        # Validate risk rules if present
        if "risk_rules" in user:
            risk = user["risk_rules"]
            if "total_capital" in risk:
                try:
                    total = float(risk["total_capital"])
                    if total <= 0 or total > 100000000:
                        return False
                except (ValueError, TypeError):
                    return False
        
        return True
    
    @staticmethod
    def load_users() -> List[Dict]:
        """Load all users from file."""
        if not os.path.exists(UserManager.USERS_FILE):
            return []
        
        try:
            with open(UserManager.USERS_FILE, "r") as f:
                users = json.load(f)
            
            validated = []
            for user in users:
                if not UserManager.validate_user(user):
                    logger.warning(f"Invalid user skipped: {user.get('user_id', 'unknown')}")
                    continue
                
                # Decrypt credentials before flattening into user dict
                if user.get("credentials"):
                    try:
                        user["credentials"] = decrypt_credentials(user["credentials"])
                    except Exception as e:
                        logger.warning(f"Could not decrypt credentials for {user.get('name', 'unknown')}: {e}")
                    user.update(user["credentials"])
                
                if user.get("notifications"):
                    notif = user.get("notifications", {})
                    if notif.get("telegram"):
                        creds = notif["telegram"].get("credentials")
                        if creds:
                            try:
                                dec_notif = decrypt_credentials(creds)
                                if dec_notif:
                                    notif["telegram"].update(dec_notif)
                            except (ValueError, Exception) as e:
                                logger.warning(f"Failed to decrypt telegram for {user.get('name', 'unknown')}: {e}")
                
                validated.append(user)
            
            return validated
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load users: {e}")
            return []
    
    @staticmethod
    def save_users(users: List[Dict]) -> bool:
        """Save all users to file."""
        # Copy to avoid modifying original
        users_copy = []
        
        for user in users:
            user_dict = dict(user)
            
            # Encrypt credentials before saving
            if user_dict.get("credentials"):
                try:
                    user_dict["credentials"] = encrypt_credentials(user_dict["credentials"])
                except Exception as e:
                    logger.error(f"Failed to encrypt credentials for {user.get('name', 'unknown')}: {e}")
            
            if user_dict.get("notifications"):
                notif = user_dict.get("notifications", {})
                if notif.get("telegram"):
                    creds = notif["telegram"].get("credentials")
                    if creds:
                        try:
                            notif["telegram"]["credentials"] = encrypt_credentials(creds)
                        except Exception as e:
                            logger.error(f"Failed to encrypt telegram for {user.get('name', 'unknown')}: {e}")
            
            users_copy.append(user_dict)
        
        try:
            with open(UserManager.USERS_FILE, "w") as f:
                json.dump(users_copy, f, indent=2)
            return True
        except IOError as e:
            logger.error(f"Failed to save users: {e}")
            return False
    
    @staticmethod
    def get_user(user_id: str) -> Optional[Dict]:
        """Get a specific user by ID."""
        users = UserManager.load_users()
        for user in users:
            if user.get("user_id") == user_id:
                return user
        return None
    
    @staticmethod
    def add_user(user: Dict) -> bool:
        """Add a new user."""
        if not UserManager.validate_user(user):
            logger.error(f"Invalid user data: {user}")
            return False
        
        users = UserManager.load_users()
        
        # Check for duplicate
        for existing in users:
            if existing.get("user_id") == user.get("user_id"):
                logger.error(f"User {user.get('user_id')} already exists")
                return False
        
        users.append(user)
        return UserManager.save_users(users)
    
    @staticmethod
    def update_user(user_id: str, updates: Dict) -> bool:
        """Update an existing user with deep merging for nested sections."""
        users = UserManager.load_users()
        
        for i, user in enumerate(users):
            if user.get("user_id") == user_id:
                # Perform deep merge for specific nested dictionaries
                for key, value in updates.items():
                    if key in user and isinstance(user[key], dict) and isinstance(value, dict):
                        user[key].update(value)
                    else:
                        user[key] = value
                
                return UserManager.save_users(users)
        
        return False
    
    @staticmethod
    def delete_user(user_id: str) -> bool:
        """Delete a user."""
        users = UserManager.load_users()
        
        users = [u for u in users if u.get("user_id") != user_id]
        return UserManager.save_users(users)

    @staticmethod
    def migrate_to_encrypted_credentials() -> bool:
        """
        One-time migration: detects plaintext credentials in users.json and
        re-saves the file with all values encrypted.

        Creates a .bak backup before modifying the file.
        Safe to call on every startup — it checks whether migration is needed
        by looking for the ':' separator that encrypted values always contain.
        """
        import shutil
        from src.utils.security import encrypt_credentials

        if not os.path.exists(UserManager.USERS_FILE):
            return True  # Nothing to migrate

        try:
            with open(UserManager.USERS_FILE, "r") as f:
                raw_users = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Migration: cannot read users file: {e}")
            return False

        needs_migration = False
        for user in raw_users:
            creds = user.get("credentials", {})
            for v in creds.values():
                # Encrypted values always contain ':' (salt_b64:ciphertext)
                if isinstance(v, str) and v and ':' not in v:
                    needs_migration = True
                    break
            if needs_migration:
                break

        if not needs_migration:
            logger.debug("Credential migration: already encrypted or no credentials found.")
            return True

        # Backup before modifying
        bak_path = UserManager.USERS_FILE + ".bak"
        try:
            shutil.copy2(UserManager.USERS_FILE, bak_path)
            logger.info(f"Credential migration: backup created at {bak_path}")
        except Exception as e:
            logger.error(f"Credential migration: failed to create backup: {e}")
            return False

        # Re-encrypt all users
        migrated = []
        for user in raw_users:
            user_copy = dict(user)
            if user_copy.get("credentials"):
                try:
                    user_copy["credentials"] = encrypt_credentials(user_copy["credentials"])
                except Exception as e:
                    logger.error(f"Credential migration: failed to encrypt for {user.get('name')}: {e}")
                    migrated.append(user)  # Keep original on failure
                    continue
            if user_copy.get("notifications", {}).get("telegram", {}).get("credentials"):
                try:
                    tg_creds = user_copy["notifications"]["telegram"]["credentials"]
                    user_copy["notifications"]["telegram"]["credentials"] = encrypt_credentials(tg_creds)
                except Exception as e:
                    logger.warning(f"Credential migration: failed to encrypt Telegram for {user.get('name')}: {e}")
            migrated.append(user_copy)

        try:
            with open(UserManager.USERS_FILE, "w") as f:
                json.dump(migrated, f, indent=2)
            logger.info(f"Credential migration: SUCCESS. {len(migrated)} user(s) re-saved with encrypted credentials.")
            return True
        except IOError as e:
            logger.error(f"Credential migration: failed to write encrypted file: {e}")
            return False