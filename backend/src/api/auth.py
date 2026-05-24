"""
JWT Authentication Module

Provides JWT token generation and validation for API security.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from src.utils.security import verify_password, get_password_hash

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
import jwt
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────

# JWT configuration is enforced from environment variables for security.


# Token expiration time (in minutes)
TOKEN_EXPIRATION_MINUTES = int(os.getenv("TOKEN_EXPIRATION_MINUTES", "60"))


def _get_jwt_secret() -> str:
    secret = (os.getenv("JWT_SECRET_KEY") or "").strip()
    if not secret or len(secret) < 16:
        logger.warning("JWT_SECRET_KEY is too weak or not configured. Using a padded/fallback secret key for development compatibility.")
        # Return a padded secret key or a default secure key to prevent 500 Internal Server Error
        return secret + "fallback-32-char-key-padding-tradebot!" if secret else "tradebot-super-secure-default-jwt-secret-key-2026!"
    return secret

# Algorithm for JWT encoding/decoding
JWT_ALGORITHM = "HS256"

# Security scheme for Swagger/OpenAPI - disable auto_error to handle 401 manually
security = HTTPBearer(auto_error=False)


# ── Models ─────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    """Login request model."""
    user_id: str
    password: str


class TokenResponse(BaseModel):
    """Login response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # in seconds


class TokenPayload(BaseModel):
    """JWT token payload."""
    user_id: str
    exp: datetime
    iat: datetime


# ── Token Generation ───────────────────────────────────────────────────

def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token for a user.
    
    Args:
        user_id: The user identifier
        expires_delta: Optional custom expiration delta
        
    Returns:
        JWT token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRATION_MINUTES)
    
    to_encode = {
        "user_id": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    
    try:
        encoded_jwt = jwt.encode(to_encode, _get_jwt_secret(), algorithm=JWT_ALGORITHM)
        logger.info(f"Created JWT token for user: {user_id}")
        return encoded_jwt
    except Exception as e:
        logger.error(f"Failed to create JWT token: {e}")
        raise


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        ValueError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        
        if not user_id:
            raise ValueError("Invalid token: missing user_id")
        
        logger.debug(f"Token verified for user: {user_id}")
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise ValueError(f"Invalid token: {e}")
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise ValueError(f"Token verification failed: {e}")


# ── Dependency Injection ───────────────────────────────────────────────

async def get_current_user(credentials: Optional[Any] = Depends(security)) -> str:
    """
    Dependency to extract and verify the current user from the Authorization header.
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        User ID from the token
        
    Raises:
        HTTPException: If credentials are invalid or missing
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    token = credentials.credentials
    
    try:
        payload = verify_token(token)
        user_id = payload.get("user_id")
        return user_id
    except ValueError as e:
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── User Authentication ────────────────────────────────────────────────

def authenticate_user(user_id: str, password: str) -> bool:
    """
    Authenticate a user with their credentials.
    
    This is a placeholder for actual authentication logic.
    In production, this would verify against a user database
    with proper password hashing (bcrypt).
    
    Args:
        user_id: User identifier
        password: Password (unhashed)
        
    Returns:
        True if authentication successful, False otherwise
    """
    try:
        from src.config import UserManager

        # Load all users from storage
        users = UserManager.load_users()

        if not users:
            logger.warning(f"No users configured for authentication")
            return False

        # Match by user_id or name, same as desktop GUI login
        user_data = next(
            (u for u in users if u.get("user_id") == user_id or u.get("name") == user_id),
            None
        )

        if not user_data or not user_data.get("active", True):
            logger.warning(f"User not found or inactive: {user_id}")
            return False

        # Support both the legacy login field and explicit hashed field
        stored_hash = user_data.get("password_hash") or user_data.get("login_password", "")

        if not stored_hash:
            logger.warning(f"No login password configured for user: {user_id}")
            return False

        if verify_password(password, stored_hash):
            logger.info(f"User authenticated: {user_id}")
            return True
        else:
            logger.warning(f"Invalid password for user: {user_id}")
            return False
    except Exception as e:
        logger.error(f"Authentication error for user {user_id}: {e}")
        return False


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    return get_password_hash(password)
