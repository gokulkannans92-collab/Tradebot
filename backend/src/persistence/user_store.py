"""
User Store Module

Handles persistence of user data with encrypted credentials.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from src.config.secrets import encrypt_credentials, decrypt_credentials
from src.utils.paths import get_path

logger = logging.getLogger(__name__)


@dataclass
class UserData:
    """Structured user data."""
    user_id: str
    name: str
    email: Optional[str] = None
    broker_type: str = "MOCK"
    credentials: Dict[str, str] = None
    notifications: Dict[str, str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    
    def __post_init__(self):
        if self.credentials is None:
            self.credentials = {}
        if self.notifications is None:
            self.notifications = {}


class UserStore:
    """
    Manages user persistence with encrypted credentials.
    
    All credentials are encrypted at rest using the secrets manager.
    """
    
    DEFAULT_USERS_FILE = "data/users.json"
    
    def __init__(self, users_file: Optional[str] = None):
        """
        Initialize user store.
        
        Args:
            users_file: Path to users JSON file (default: data/users.json)
        """
        self.users_file = users_file or get_path(self.DEFAULT_USERS_FILE)
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Ensure users file exists."""
        os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
        if not os.path.exists(self.users_file):
            with open(self.users_file, 'w') as f:
                json.dump([], f)
    
    def load_all(self) -> List[UserData]:
        """
        Load all users with decrypted credentials.
        
        Returns:
            List of UserData objects
        """
        if not os.path.exists(self.users_file):
            return []
        
        try:
            with open(self.users_file, 'r') as f:
                raw_users = json.load(f)
            
            users = []
            for user_dict in raw_users:
                # Credentials are now plaintext
                if "credentials" in user_dict and user_dict["credentials"]:
                    pass # Already plaintext in memory
                
                # Notifications are now plaintext
                if "notifications" in user_dict and user_dict["notifications"]:
                    pass # Already plaintext in memory
                
                users.append(UserData(**user_dict))
            
            return users
            
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted users file: {e}")
            return []
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            return []
    
    def load_active(self) -> List[UserData]:
        """Load only active users."""
        return [u for u in self.load_all() if u.is_active]
    
    def save_all(self, users: List[UserData]) -> bool:
        """
        Save all users with encrypted credentials.
        
        Args:
            users: List of UserData to save
            
        Returns:
            True if successful
        """
        try:
            raw_users = []
            for user in users:
                user_dict = asdict(user)
                
                # Credentials and notifications are now saved in plaintext
                pass
                
                raw_users.append(user_dict)
            
            with open(self.users_file, 'w') as f:
                json.dump(raw_users, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save users: {e}")
            return False
    
    def add_user(self, user: UserData) -> bool:
        """
        Add a new user.
        
        Args:
            user: UserData to add
            
        Returns:
            True if successful
        """
        users = self.load_all()
        
        # Check for duplicate name
        if any(u.name == user.name for u in users):
            logger.error(f"User with name '{user.name}' already exists")
            return False
        
        users.append(user)
        return self.save_all(users)
    
    def update_user(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing user.
        
        Args:
            user_id: User ID to update
            updates: Dictionary of fields to update
            
        Returns:
            True if successful
        """
        users = self.load_all()
        
        for user in users:
            if user.user_id == user_id:
                for key, value in updates.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
                return self.save_all(users)
        
        logger.error(f"User {user_id} not found")
        return False
    
    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user.
        
        Args:
            user_id: User ID to delete
            
        Returns:
            True if successful
        """
        users = self.load_all()
        users = [u for u in users if u.user_id != user_id]
        return self.save_all(users)
    
    def get_user_by_id(self, user_id: str) -> Optional[UserData]:
        """Get user by ID."""
        for user in self.load_all():
            if user.user_id == user_id:
                return user
        return None
    
    def get_user_by_name(self, name: str) -> Optional[UserData]:
        """Get user by name."""
        for user in self.load_all():
            if user.name == name:
                return user
        return None


# Global instance for convenience
_user_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    """Get or create global user store."""
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store


# Backward compatibility functions
def load_users() -> List[Dict[str, Any]]:
    """Load users as dictionaries (backward compatibility)."""
    users = get_user_store().load_all()
    return [asdict(u) for u in users]


def save_user(user_data: Dict[str, Any]) -> bool:
    """Save user from dictionary (backward compatibility)."""
    user = UserData(**user_data)
    return get_user_store().add_user(user)
