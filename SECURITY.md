# 🔐 Security & Credential Management Guide

## Overview
This document explains how to securely manage API credentials and sensitive data for TradeBot.

---

## ⚠️ Critical Rules

### NEVER DO THIS ❌
```
- Commit .env files to git
- Push API keys to public repositories
- Share credentials in messages or code
- Hardcode secrets in source files
- Log sensitive information
```

### ALWAYS DO THIS ✅
```
- Use .env files locally (add to .gitignore)
- Store secrets in GitHub Secrets for CI/CD
- Rotate API keys regularly
- Use environment variables for configuration
- Mask sensitive data in logs
```

---

## Local Development Setup

### 1. Copy Environment Template
```bash
cp .env.example .env
```

### 2. Add Your Credentials
Edit `.env` with your actual broker API credentials:
```env
ZERODHA_API_KEY=your_actual_key
ZERODHA_API_SECRET=your_actual_secret
ANGEL_ONE_API_KEY=your_actual_key
UPSTOX_API_KEY=your_actual_key
DATABASE_URL=sqlite:///./trades.db
```

### 3. Never Commit .env
The `.env` file is in `.gitignore` and will NOT be committed.

### 4. Load Environment Variables
```python
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv('ZERODHA_API_KEY')
```

---

## Production Deployment (GitHub Actions)

### Step 1: Add Secrets to GitHub

1. Go to **Repository → Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Add each credential:

```
Name: ZERODHA_API_KEY
Value: [Your actual API key]

Name: ZERODHA_API_SECRET
Value: [Your actual API secret]

Name: ANGEL_ONE_API_KEY
Value: [Your actual API key]

Name: UPSTOX_API_KEY
Value: [Your actual API key]

Name: DATABASE_URL
Value: [Your database connection string]

Name: SECRET_KEY
Value: [Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"]
```

### Step 2: Use Secrets in Workflows

Create `.github/workflows/deploy.yml`:
```yaml
name: Deploy

on:
  push:
    branches: [master]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Application
        env:
          ZERODHA_API_KEY: ${{ secrets.ZERODHA_API_KEY }}
          ZERODHA_API_SECRET: ${{ secrets.ZERODHA_API_SECRET }}
          ANGEL_ONE_API_KEY: ${{ secrets.ANGEL_ONE_API_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: python main.py
```

---

## Broker-Specific Setup

### Zerodha Kiteconnect
1. Login to [Zerodha Console](https://console.zerodha.com/)
2. Navigate to **API Credentials**
3. Copy **API Key** and **API Secret**
4. Add to `.env` or GitHub Secrets

### Angel One
1. Login to Angel One account
2. Go to **Profile → API**
3. Copy **API Key** and **Client Code**
4. Generate TOTP key for 2FA
5. Add to `.env` or GitHub Secrets

### Upstox
1. Login to [Upstox Console](https://upstox.com/)
2. Navigate to **API Tokens**
3. Generate new token
4. Copy **API Key** and **API Secret**
5. Add to `.env` or GitHub Secrets

---

## Rotation & Revocation

### If a Key is Exposed:
1. **Immediately revoke** the key in broker console
2. **Generate a new key**
3. **Update .env** locally
4. **Update GitHub Secrets**
5. **Inform your broker** (if necessary)
6. **Rotate JWT SECRET_KEY** as well

### Regular Rotation (Recommended)
- Rotate API keys **every 3 months**
- Rotate SECRET_KEY **every 6 months**
- Update after any security incident

---

## Best Practices

### 1. Principle of Least Privilege
- Use API keys with **minimal required permissions**
- Create separate keys for **different trading strategies** if possible
- Restrict IP access in broker console if available

### 2. Environment Separation
- **Development**: Use sandbox/paper trading keys
- **Production**: Use live trading keys (separate from dev)
- **Testing**: Use test API keys only

### 3. Logging & Monitoring
```python
# ❌ BAD - Logs the API key
logger.info(f"API Key: {api_key}")

# ✅ GOOD - Logs without sensitive data
logger.info("Successfully authenticated with Zerodha")
```

### 4. Error Handling
```python
# ❌ BAD - Exposes credentials in error message
except Exception as e:
    logger.error(f"Failed with credentials: {api_key}, {api_secret}, Error: {e}")

# ✅ GOOD - Generic error message
except Exception as e:
    logger.error(f"Authentication failed: {str(e)}")
```

---

## Verification Checklist

- [ ] `.env` file is in `.gitignore`
- [ ] `.env.example` exists without real credentials
- [ ] GitHub Secrets are configured for all required keys
- [ ] No hardcoded credentials in source files
- [ ] Environment variables are loaded from `.env` in development
- [ ] GitHub Actions use `${{ secrets.SECRET_NAME }}` syntax
- [ ] Secrets are masked in workflow logs
- [ ] Database URL is in secrets, not hardcoded
- [ ] JWT SECRET_KEY is unique and secure
- [ ] API keys have been tested locally before deployment

---

## Useful Commands

### Generate Secure Secret Key
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Test if .env is loaded
```bash
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('ZERODHA_API_KEY'))"
```

### Check git history for leaked secrets
```bash
git log -p --all | grep -i "api_key\|password\|token"
```

### Revoke exposed secrets
Contact your broker's support and immediately regenerate keys.

---

## Additional Resources

- [GitHub Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Python-dotenv Documentation](https://python-dotenv.readthedocs.io/)
- [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

---

**Last Updated:** 2026-05-06  
**Version:** 1.0
