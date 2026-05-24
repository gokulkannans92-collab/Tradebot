"""
Input Validation & Sanitization Module

Provides centralized, secure validation and sanitization for:
- User inputs from configuration files
- API parameters and responses
- File paths and filenames
- Credentials and sensitive data

SECURITY PRINCIPLES:
    ✓ Whitelist validation (allow known good, not blacklist known bad)
    ✓ Fail securely (reject invalid data, never patch/coerce)
    ✓ Validate all external inputs (files, environment, API)
    ✓ Sanitize before logging (prevent log injection)
    ✓ No silent fallbacks for validation failures
    ✓ Log all validation errors for audit trails
"""

import re
import os
import logging
from typing import Any, Dict, Optional, Union, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class InputValidator:
    """
    Secure input validation with whitelist-first approach.
    
    All methods raise ValidationError on failure (never silently accept bad data).
    """
    
    # Whitelist patterns (what IS allowed)
    USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{1,50}$")
    SYMBOL_PATTERN = re.compile(r"^[A-Z0-9\-]{1,10}$")
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    
    # Safe pattern for trading symbols (alphanumeric, space, and common special chars)
    SAFE_SYMBOL_PATTERN = re.compile(r'^[\w\s\-\._&]+$')
    
    # Dangerous characters for file paths (blacklist)
    PATH_DANGEROUS_CHARS = ['..', '~', '$', '`', '|', ';', '&']
    
    # Maximum safe lengths
    MAX_SYMBOL_LENGTH = 50
    MAX_FILENAME_LENGTH = 255
    MAX_PATH_LENGTH = 4096
    MAX_USER_ID_LENGTH = 50
    MAX_NAME_LENGTH = 100
    MAX_CREDENTIAL_LENGTH = 10000
    
    @staticmethod
    def validate_user_id(value: str) -> str:
        """
        Validate user_id format (whitelist: alphanumeric, underscore, hyphen).
        
        Args:
            value: user_id to validate
            
        Returns:
            str: Validated user_id
            
        Raises:
            ValidationError: If format is invalid
        """
        if not isinstance(value, str):
            raise ValidationError(f"user_id must be string, got {type(value).__name__}")
        
        value = value.strip()
        
        if not value:
            raise ValidationError("user_id cannot be empty")
        
        if not InputValidator.USER_ID_PATTERN.match(value):
            raise ValidationError(
                f"Invalid user_id format: must be 1-{InputValidator.MAX_USER_ID_LENGTH} chars "
                "of alphanumeric, underscore, or hyphen only"
            )
        
        return value
    
    @staticmethod
    def validate_user_name(value: str) -> str:
        """
        Validate user display name (no control characters, null bytes).
        
        Args:
            value: User display name
            
        Returns:
            str: Validated name
            
        Raises:
            ValidationError: If invalid
        """
        if not isinstance(value, str):
            raise ValidationError(f"name must be string, got {type(value).__name__}")
        
        value = value.strip()
        
        if not value:
            raise ValidationError("name cannot be empty")
        
        if len(value) > InputValidator.MAX_NAME_LENGTH:
            raise ValidationError(f"name too long (max {InputValidator.MAX_NAME_LENGTH} chars)")
        
        if '\x00' in value:
            raise ValidationError("name contains null bytes (possible injection)")
        
        # Check for control characters (except tab, newline, carriage return)
        if any(ord(c) < 32 for c in value if c not in '\t\n\r'):
            raise ValidationError("name contains invalid control characters")
        
        return value
    
    @staticmethod
    def validate_credential(value: str, field_name: str = "credential") -> str:
        """
        Validate credential (API key, token, password format).
        
        Checks length and control characters, but NOT validity of the actual credential.
        
        Args:
            value: Credential string
            field_name: Name for error messages
            
        Returns:
            str: Validated credential
            
        Raises:
            ValidationError: If format is invalid
        """
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be string, got {type(value).__name__}")
        
        # Don't strip credentials (whitespace might be intentional)
        
        if not value:
            raise ValidationError(f"{field_name} cannot be empty")
        
        if len(value) < 4:
            raise ValidationError(f"{field_name} too short (minimum 4 characters)")
        
        if len(value) > InputValidator.MAX_CREDENTIAL_LENGTH:
            raise ValidationError(f"{field_name} too long (maximum {InputValidator.MAX_CREDENTIAL_LENGTH})")
        
        if '\x00' in value:
            raise ValidationError(f"{field_name} contains null bytes")
        
        return value
    
    @staticmethod
    def validate_positive_float(
        value: Any,
        field_name: str = "value",
        min_val: float = 0.01,
        max_val: float = 100_000_000
    ) -> float:
        """
        Validate and convert to positive float with range checking.
        
        Args:
            value: Value to validate
            field_name: Name for error messages
            min_val: Minimum allowed value (exclusive)
            max_val: Maximum allowed value (inclusive)
            
        Returns:
            float: Validated positive float
            
        Raises:
            ValidationError: If invalid or out of range
        """
        try:
            fval = float(value)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"{field_name} must be numeric, got {value}") from e
        
        if fval <= min_val:
            raise ValidationError(f"{field_name} must be > {min_val}, got {fval}")
        
        if fval > max_val:
            raise ValidationError(f"{field_name} must be <= {max_val}, got {fval}")
        
        return fval
    
    @staticmethod
    def validate_positive_int(
        value: Any,
        field_name: str = "value",
        min_val: int = 1,
        max_val: int = 1_000_000
    ) -> int:
        """
        Validate and convert to positive integer with range checking.
        
        Args:
            value: Value to validate
            field_name: Name for error messages
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)
            
        Returns:
            int: Validated positive integer
            
        Raises:
            ValidationError: If invalid or out of range
        """
        try:
            ival = int(value)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"{field_name} must be integer, got {value}") from e
        
        if ival < min_val:
            raise ValidationError(f"{field_name} must be >= {min_val}, got {ival}")
        
        if ival > max_val:
            raise ValidationError(f"{field_name} must be <= {max_val}, got {ival}")
        
        return ival
    
    @classmethod
    def validate_symbol(cls, symbol: str, allow_empty: bool = False) -> str:
        """
        Validate and sanitize trading symbol (whitelist pattern).
        
        Args:
            symbol: Trading symbol to validate
            allow_empty: Whether empty string is allowed
            
        Returns:
            Sanitized symbol (uppercase)
            
        Raises:
            ValidationError: If symbol contains dangerous characters
        """
        if not symbol:
            if allow_empty:
                return ""
            raise ValidationError("Symbol cannot be empty")
        
        symbol = symbol.strip().upper()
        
        if len(symbol) > cls.MAX_SYMBOL_LENGTH:
            raise ValidationError(f"Symbol too long: {len(symbol)} > {cls.MAX_SYMBOL_LENGTH}")
        
        # Whitelist pattern check
        if not cls.SAFE_SYMBOL_PATTERN.match(symbol):
            raise ValidationError(
                f"Symbol '{symbol}' contains invalid characters (alphanumeric, space, hyphen, period, underscore only)"
            )
        
        return symbol
    
    @classmethod
    def validate_filepath(
        cls,
        filepath: str,
        must_exist: bool = False,
        base_dir: Optional[str] = None
    ) -> str:
        """
        Validate file path to prevent path traversal attacks.
        
        Args:
            filepath: Path to validate
            must_exist: Whether file must exist
            base_dir: Optional base directory that path must be under
            
        Returns:
            Normalized absolute path
            
        Raises:
            ValidationError: If path is dangerous or outside allowed directory
        """
        if not filepath:
            raise ValidationError("Filepath cannot be empty")
        
        if len(filepath) > cls.MAX_PATH_LENGTH:
            raise ValidationError(f"Path too long: {len(filepath)}")
        
        # Check for dangerous patterns (blacklist)
        for dangerous in cls.PATH_DANGEROUS_CHARS:
            if dangerous in filepath:
                raise ValidationError(f"Path contains dangerous pattern: {dangerous}")
        
        # Normalize and get absolute path
        try:
            normalized = os.path.normpath(os.path.abspath(filepath))
        except Exception as e:
            raise ValidationError(f"Invalid path format: {e}") from e
        
        # Check base directory constraint
        if base_dir:
            base_normalized = os.path.normpath(os.path.abspath(base_dir))
            if not (normalized.startswith(base_normalized + os.sep) or normalized == base_normalized):
                raise ValidationError(f"Path outside allowed directory: {base_dir}")
        
        # Check existence if required
        if must_exist and not os.path.exists(normalized):
            raise ValidationError(f"Path does not exist: {normalized}")
        
        return normalized
    
    @classmethod
    def validate_filename(cls, filename: str) -> str:
        """
        Validate filename to prevent directory traversal in filenames.
        
        Args:
            filename: Filename to validate
            
        Returns:
            Sanitized filename
            
        Raises:
            ValidationError: If filename is dangerous
        """
        if not filename:
            raise ValidationError("Filename cannot be empty")
        
        if len(filename) > cls.MAX_FILENAME_LENGTH:
            raise ValidationError(f"Filename too long: {len(filename)}")
        
        # Check for path separators
        if os.sep in filename or '/' in filename or '\\' in filename:
            raise ValidationError("Filename cannot contain path separators")
        
        # Check for dangerous patterns
        if filename.startswith('.') or filename.startswith('~'):
            raise ValidationError(f"Dangerous filename pattern")
        
        # Check for null bytes
        if '\x00' in filename:
            raise ValidationError("Filename contains null bytes")
        
        return filename
    
    @staticmethod
    def validate_risk_rules(risk_rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate risk management rules with range checking.
        
        Args:
            risk_rules: Risk configuration dictionary
            
        Returns:
            Dict: Validated and sanitized risk rules
            
        Raises:
            ValidationError: If any rule is invalid
        """
        if not isinstance(risk_rules, dict):
            raise ValidationError("risk_rules must be a dictionary")
        
        validated = {}
        
        if "total_capital" in risk_rules:
            validated["total_capital"] = InputValidator.validate_positive_float(
                risk_rules["total_capital"],
                "total_capital",
                min_val=100,
                max_val=100_000_000
            )
        
        if "trade_capital" in risk_rules:
            validated["trade_capital"] = InputValidator.validate_positive_float(
                risk_rules["trade_capital"],
                "trade_capital",
                min_val=100,
                max_val=100_000_000
            )
        
        if "max_trades_per_day" in risk_rules:
            validated["max_trades_per_day"] = InputValidator.validate_positive_int(
                risk_rules["max_trades_per_day"],
                "max_trades_per_day",
                min_val=1,
                max_val=100
            )
        
        if "max_daily_loss_pct" in risk_rules:
            val = InputValidator.validate_positive_float(
                risk_rules["max_daily_loss_pct"],
                "max_daily_loss_pct",
                min_val=-0.01,
                max_val=100
            )
            if val < 0 or val > 100:
                raise ValidationError(f"max_daily_loss_pct must be 0-100, got {val}")
            validated["max_daily_loss_pct"] = val
        
        return validated
    
    @staticmethod
    def sanitize_for_logging(message: str, max_length: int = 1000) -> str:
        """
        Sanitize message for logging (prevent log injection attacks).
        
        Removes newlines and other control characters that could break log format.
        
        Args:
            message: Message to sanitize
            max_length: Maximum length before truncation
            
        Returns:
            str: Sanitized message safe for logging
        """
        if not isinstance(message, str):
            message = str(message)
        
        # Replace null bytes
        message = message.replace('\x00', '\\x00')
        
        # Replace newlines/carriage returns to prevent log injection
        message = message.replace('\n', '\\n').replace('\r', '\\r')
        
        # Limit length to prevent log flooding
        if len(message) > max_length:
            message = message[:max_length] + "...(truncated)"
        
        return message
    
    @classmethod
    def sanitize_user_input(cls, user_input: str, max_length: int = 1000) -> str:
        """
        General user input sanitization.
        
        Args:
            user_input: Raw user input
            max_length: Maximum allowed length
            
        Returns:
            Sanitized input
        """
        if not user_input:
            return ""
        
        if len(user_input) > max_length:
            raise ValidationError(f"Input too long: {len(user_input)} > {max_length}")
        
        # Remove control characters except common whitespace
        sanitized = ''.join(char for char in user_input if ord(char) >= 32 or char in '\n\r\t')
        
        # Strip dangerous HTML/script tags if any
        sanitized = cls._strip_dangerous_html(sanitized)
        
        return sanitized.strip()
    
    @classmethod
    def validate_api_key(cls, api_key: str) -> str:
        """
        Validate API key format.
        
        Args:
            api_key: API key to validate
            
        Returns:
            Validated API key
            
        Raises:
            ValidationError: If API key format is invalid
        """
        if not api_key:
            raise ValidationError("API key cannot be empty")
        
        if len(api_key) < 10:
            raise ValidationError("API key too short (min 10 chars)")
        
        if len(api_key) > 200:
            raise ValidationError("API key too long")
        
        # Check for obviously fake/test keys
        test_patterns = ['test', 'fake', 'dummy', '123456', 'abcdef']
        key_lower = api_key.lower()
        for pattern in test_patterns:
            if pattern in key_lower:
                logger.warning(f"API key contains suspicious pattern: {pattern}")
        
        return api_key
    
    @classmethod
    def _find_dangerous_chars(cls, text: str, safe_pattern: re.Pattern) -> List[str]:
        """Find characters that don't match safe pattern."""
        dangerous = []
        for char in text:
            if not safe_pattern.match(char):
                dangerous.append(repr(char))
        return dangerous[:5]  # Limit output
    
    @classmethod
    def _strip_dangerous_html(cls, text: str) -> str:
        """Remove potentially dangerous HTML/script content."""
        # Remove script tags and their contents
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Remove event handlers
        text = re.sub(r'\s*on\w+\s*=\s*"[^"]*"', '', text, flags=re.IGNORECASE)
        text = re.sub(r"\s*on\w+\s*=\s*'[^']*'", '', text, flags=re.IGNORECASE)
        return text


def safe_symbol(symbol: str, default: Optional[str] = None) -> str:
    """
    Safe symbol getter with default fallback.
    
    Args:
        symbol: Symbol to validate
        default: Default value if validation fails
        
    Returns:
        Validated symbol or default
    """
    try:
        return InputValidator.validate_symbol(symbol)
    except ValidationError as e:
        logger.warning(f"Symbol validation failed: {e}")
        if default is not None:
            return default
        raise


def safe_filepath(filepath: str, base_dir: Optional[str] = None, 
                  must_exist: bool = False) -> Optional[str]:
    """
    Safe filepath getter with error handling.
    
    Args:
        filepath: Path to validate
        base_dir: Optional base directory constraint
        must_exist: Whether file must exist
        
    Returns:
        Validated path or None on failure
    """
    try:
        return InputValidator.validate_filepath(filepath, must_exist, base_dir)
    except ValidationError as e:
        logger.error(f"Path validation failed: {e}")
        return None


# Convenience function for secure path joining
def secure_join(base_dir: str, *paths: str) -> str:
    """
    Securely join paths and validate result is under base_dir.
    
    Args:
        base_dir: Base directory that result must be under
        *paths: Path components to join
        
    Returns:
        Validated absolute path
        
    Raises:
        ValidationError: If result path escapes base_dir
    """
    joined = os.path.join(base_dir, *paths)
    normalized = os.path.normpath(os.path.abspath(joined))
    base_normalized = os.path.normpath(os.path.abspath(base_dir))
    
    # Ensure normalized path starts with base path
    if not normalized.startswith(base_normalized + os.sep) and normalized != base_normalized:
        raise ValidationError(f"Path traversal attempt detected: {joined}")
    
    return normalized
