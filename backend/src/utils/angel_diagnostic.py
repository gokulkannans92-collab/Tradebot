"""
Angel Broker TOTP Diagnostic Tool
========================

Run this script to debug Angel One login issues.

Usage:
    python -m src.utils.angel_diagnostic

Or import and call:
    from src.utils.angel_diagnostic import run_diagnostic
    run_diagnostic()
"""

import os
import sys
import logging
import argparse
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%y%m%d %H:%M:%S'
)
logger = logging.getLogger("AngelDiagnostics")


def getCredential(key, env_vars):
    """Get credential from config dict or environment."""
    if key in env_vars and env_vars[key]:
        return env_vars[key]
    # Try environment variables
    env_key = f"ANGEL_{key}" if not key.startswith("ANGEL_") else key
    return os.getenv(env_key, "")


def cleanTotpSecret(secret):
    """Remove spaces and convert to uppercase."""
    if not secret:
        return ""
    return secret.replace(" ", "").replace("-", "").upper().strip()


def validateBase32(secret):
    """Validate if string is valid base32."""
    if not secret:
        return False, "Empty secret"
    
    # Base32 allowed characters (A-Z, 2-7)
    base32_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    secret = secret.upper()
    
    for char in secret:
        if char not in base32_chars:
            return False, f"Invalid character: {char}"
    
    if len(secret) < 16:
        return False, f"Too short: {len(secret)} (need 16-32)"
    
    if len(secret) > 32:
        return False, f"Too long: {len(secret)} (need 16-32)"
    
    return True, "Valid"


def testTotpGeneration(totp_secret):
    """Test TOTP code generation."""
    try:
        import pyotp
    except ImportError:
        logger.error("pyotp not installed!")
        logger.info("Install with: pip install pyotp")
        return False
    
    # Clean the secret
    clean_secret = cleanTotpSecret(totp_secret)
    if not clean_secret:
        logger.error("TOTP secret is empty!")
        return False
    
    # Validate format
    is_valid, msg = validateBase32(clean_secret)
    if not is_valid:
        logger.error(f"TOTP secret format invalid: {msg}")
        return False
    
    logger.info(f"✓ TOTP secret format valid ({len(clean_secret)} chars)")
    
    # Generate codes for verification
    try:
        totp = pyotp.TOTP(clean_secret)
        now = totp.now()
        logger.info(f"="*50)
        logger.info(f"CURRENT TOTP CODE: {now}")
        logger.info(f"Valid for: ~{30 - datetime.now().second % 30}s")
        logger.info(f"="*50)
        
        # Show next few codes
        logger.info("\nUpcoming codes (for manual verification):")
        for i in range(3):
            code = totp.at(datetime.now().timestamp() + i * 30)
            logger.info(f"  +{i*30}s: {code}")
        
        return True
        
    except Exception as e:
        logger.error(f"TOTP generation failed: {e}")
        return False


def testAngelConnectivity():
    """Test connectivity to Angel One servers."""
    import requests
    
    test_urls = [
        "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword",
        "https://smartapi.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword",
    ]
    
    logger.info("\nTesting Angel One server connectivity...")
    
    for url in test_urls:
        try:
            # Just test HEAD connection (don't post credentials)
            resp = requests.head(url, timeout=10)
            logger.info(f"✓ {url}")
            logger.info(f"  Status: {resp.status_code}")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"✗ {url}")
            logger.warning(f"  Connection failed: {str(e)[:100]}")
        except Exception as e:
            logger.warning(f"✗ {url}")
            logger.warning(f"  Error: {e}")
    
    return True


def testLoginApi(api_key, client_id, password, totp_secret):
    """Test actual Angel One login API."""
    try:
        from SmartApi import SmartConnect
        import pyotp
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.info("Install with: pip install smartapi-python pyotp")
        return False
    
    # Clean inputs
    client_id = client_id.strip().upper()
    totp_secret = cleanTotpSecret(totp_secret)
    
    if not api_key or not client_id or not password or not totp_secret:
        logger.error("Missing required credentials!")
        return False
    
    # Generate TOTP
    try:
        totp = pyotp.TOTP(totp_secret)
        totp_code = totp.now()
    except Exception as e:
        logger.error(f"TOTP generation failed: {e}")
        return False
    
    logger.info("="*50)
    logger.info("Attempting Angel One login...")
    logger.info(f"Client ID: {client_id}")
    logger.info(f"TOTP Code: {totp_code}")
    logger.info("="*50)
    
    try:
        obj = SmartConnect(
            api_key=api_key,
            clientLocalIP="127.0.0.1",
            clientPublicIP="1.1.1.1",
            disable_ssl=False
        )
        
        data = obj.generateSession(client_id, password, totp_code)
        
        if data and data.get("status"):
            logger.info("="*50)
            logger.info("✓ LOGIN SUCCESSFUL!")
            logger.info(f"✓ User: {data.get('data', {}).get('name', 'N/A')}")
            logger.info("="*50)
            return True
        else:
            msg = data.get('message', 'Unknown error') if data else 'No response'
            err = data.get('errorcode', 'N/A') if data else 'N/A'
            logger.error(f"✗ LOGIN FAILED: {msg} (errorcode: {err})")
            return False
            
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Login error: {err_msg}")
        
        if "Invalid totp" in err_msg:
            logger.error("\n" + "="*50)
            logger.error("TOTP INVALID - Possible causes:")
            logger.error("1. Windows clock out of sync")
            logger.error("2. TOTP secret incorrect")
            logger.error("3. TOTP already used (30s window)")
            logger.error("="*50)
        
        return False


def run_diagnostic():
    """Run all diagnostics."""
    logger.info("="*60)
    logger.info("ANGEL BROKER TOTP DIAGNOSTIC TOOL")
    logger.info("="*60)
    
    # Get credentials from environment or config file
    # Try to load from .env
    from dotenv import load_dotenv
    
    # Try multiple env file locations
    env_files = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.getcwd())), ".env"),
    ]
    
    for ef in env_files:
        if os.path.exists(ef):
            load_dotenv(ef)
            logger.info(f"Loaded env from: {ef}")
            break
    
    # Gather credentials
    api_key = os.getenv("ANGEL_API_KEY", "") or os.getenv("API_KEY", "")
    client_id = os.getenv("ANGEL_CLIENT_ID", "") or os.getenv("CLIENT_ID", "")
    password = os.getenv("ANGEL_PASSWORD", "") or os.getenv("PASSWORD", "")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET", "") or os.getenv("TOTP_SECRET", "")
    
    # Allow CLI arguments to override
    parser = argparse.ArgumentParser(description="Angel Broker Diagnostic")
    parser.add_argument("--api-key", default=api_key, help="API Key")
    parser.add_argument("--client-id", default=client_id, help="Client ID")
    parser.add_argument("--password", default=password, help="Password")
    parser.add_argument("--totp-secret", default=totp_secret, help="TOTP Secret")
    parser.add_argument("--test-login", action="store_true", help="Test actual login (requires credentials)")
    args = parser.parse_args()
    
    api_key = args.api_key or api_key
    client_id = args.client_id or client_id
    password = args.password or password
    totp_secret = args.totp_secret or totp_secret
    
    # Run tests
    logger.info("\n" + "="*60)
    logger.info("STEP 1: TOTP FORMAT VALIDATION")
    logger.info("="*60)
    
    if totp_secret:
        testTotpGeneration(totp_secret)
    else:
        logger.warning("TOTP_SECRET not set - cannot test")
        logger.info("Set ANGEL_TOTP_SECRET in .env or pass --totp-secret")
    
    logger.info("\n" + "="*60)
    logger.info("STEP 2: CONNECTIVITY TEST")
    logger.info("="*60)
    testAngelConnectivity()
    
    if args.test_login and api_key and client_id and password and totp_secret:
        logger.info("\n" + "="*60)
        logger.info("STEP 3: LOGIN TEST")
        logger.info("="*60)
        testLoginApi(api_key, client_id, password, totp_secret)
    
    logger.info("\n" + "="*60)
    logger.info("DIAGNOSTIC COMPLETE")
    logger.info("="*60)
    logger.info("\nNext steps:")
    logger.info("1. If TOTP format invalid - check your TOTP_SECRET")
    logger.info("2. If connectivity fails - check internet/firewall")
    logger.info("3. If login fails - check Client ID, Password")
    logger.info("\nTo test login:")
    logger.info("  python -m src.utils.angel_diagnostic --test-login --api-key KEY --client-id ID --password PASS --totp-secret SECRET")
    
    return True


if __name__ == "__main__":
    run_diagnostic()