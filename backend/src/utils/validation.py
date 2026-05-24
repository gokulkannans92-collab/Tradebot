import os
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

class CredentialValidator:
    """Validates that necessary credentials are present and correctly formatted."""
    
    @staticmethod
    def validate_credentials(creds: dict, broker_type: str) -> Tuple[bool, List[str]]:
        """
        Generic validation for a dictionary of credentials.
        Returns (is_valid, list_of_errors).
        """
        errors = []
        broker_type = broker_type.lower()
        
        if not broker_type:
            errors.append("Broker type is not specified")
            return False, errors
            
        if broker_type == "angel":
            required = [
                ("api_key", "ANGEL_API_KEY", "API Key"),
                ("client_id", "ANGEL_CLIENT_ID", "Client ID"),
                ("password", "ANGEL_PASSWORD", "Password"),
                ("totp_secret", "ANGEL_TOTP_SECRET", "TOTP Secret")
            ]
        elif broker_type == "zerodha":
            required = [
                ("api_key", "ZERODHA_API_KEY", "API Key"),
                ("access_token", "ZERODHA_ACCESS_TOKEN", "Access Token")
            ]
        elif broker_type == "upstox":
            required = [
                ("api_key", "UPSTOX_API_KEY", "API Key"),
                ("access_token", "UPSTOX_ACCESS_TOKEN", "Access Token")
            ]
        elif broker_type == "mock":
            return True, []
        else:
            errors.append(f"Unsupported broker type: {broker_type}")
            return False, errors
            
        for key, env_fallback, label in required:
            # Check dictionary first, then fallback to env if keys match
            value = creds.get(key) or os.getenv(env_fallback, "")
            value = str(value).strip() if value else ""
            
            if not value or value.startswith("REPLACE_WITH"):
                errors.append(f"Missing or placeholder value for {label}")
                
        # Basic format checks
        if broker_type == "angel":
            totp = creds.get("totp_secret") or os.getenv("ANGEL_TOTP_SECRET", "")
            totp = str(totp).strip() if totp else ""
            if totp and len(totp) < 16:
                errors.append("TOTP Secret seems too short (should be 16+ characters)")
                
        is_valid = len(errors) == 0
        return is_valid, errors

    @staticmethod
    def validate_env_credentials() -> Tuple[bool, List[str]]:
        """
        Validates the credentials in the environment (loaded from .env).
        Returns (is_valid, list_of_errors).
        """
        broker_type = os.getenv("BROKER_TYPE", "angel").lower()
        # Create a dummy dict to trigger env fallbacks in validate_credentials
        return CredentialValidator.validate_credentials({}, broker_type)

    @staticmethod
    def log_validation_results(is_valid: bool, errors: List[str]):
        """Logs the results of the validation."""
        if is_valid:
            logger.info("Credential validation passed.")
        else:
            logger.error("Credential validation FAILED:")
            for error in errors:
                logger.error(f"  - {error}")
            logger.info("Please update your Config in the UI or data/.env file with valid credentials.")
