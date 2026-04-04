import bcrypt
import os
import base64
import hashlib
from cryptography.fernet import Fernet

_encryption_key = None

def set_encryption_key(key: str):
    global _encryption_key
    if key:
        _encryption_key = key

def _get_fernet():
    if _encryption_key is None:
        key = os.environ.get('ENCRYPTION_KEY', '')
        if not key:
            raise ValueError("ENCRYPTION_KEY not set")
    else:
        key = _encryption_key
    
    key_bytes = hashlib.sha256(key.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))

def encrypt_value(value: str) -> str:
    if not value:
        return value
    try:
        f = _get_fernet()
        return f.encrypt(value.encode('utf-8')).decode('utf-8')
    except Exception as e:
        print(f"Encryption error: {e}")
        return value

def decrypt_value(encrypted_value: str) -> str:
    if not encrypted_value:
        return encrypted_value
    try:
        f = _get_fernet()
        return f.decrypt(encrypted_value.encode('utf-8')).decode('utf-8')
    except Exception as e:
        # Silently return original value on decryption failure
        # This handles both plain text values and cases where encryption key changed
        return encrypted_value

def encrypt_credentials(credentials: dict) -> dict:
    if not credentials:
        return credentials
    encrypted = {}
    for key, value in credentials.items():
        if key in ('api_key', 'api_secret', 'access_token', 'password', 'totp_secret', 'client_id', 'groww_password', 'telegram_bot_token', 'telegram_chat_id'):
            encrypted[key] = encrypt_value(str(value)) if value else value
        else:
            encrypted[key] = value
    return encrypted

def decrypt_credentials(credentials: dict) -> dict:
    if not credentials:
        return credentials
    decrypted = {}
    for key, value in credentials.items():
        if key in ('api_key', 'api_secret', 'access_token', 'password', 'totp_secret', 'client_id', 'groww_password', 'telegram_bot_token', 'telegram_chat_id'):
            decrypted[key] = decrypt_value(str(value)) if value else value
        else:
            decrypted[key] = value
    return decrypted

def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
    try:
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except ValueError:
        return False

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode('utf-8')
