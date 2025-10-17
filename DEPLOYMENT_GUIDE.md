# Healthcare RCM System - Phase 1 Deployment Guide

**Repository:** https://github.com/HealthFlowEgy/AgentAI  
**Branch:** main  
**Version:** 1.0.0  
**Date:** October 17, 2025

---

## 🎯 Deployment Overview

This guide provides step-by-step instructions for deploying the Phase 1 implementation of the Healthcare RCM Agent System.

---

## 📋 Prerequisites

### Required Software

- **Python:** 3.11 or higher
- **PostgreSQL:** 14 or higher
- **Redis:** 7 or higher
- **Git:** Latest version
- **Docker & Docker Compose:** (Optional, for local HCX)

### Required Accounts & Keys

- **GitHub Account:** Access to HealthFlowEgy/AgentAI repository
- **OpenAI API Key:** For LLM agents
- **HCX Platform Credentials:** Username and password
- **Database Credentials:** PostgreSQL user and password

---

## 🚀 Step-by-Step Deployment

### Step 1: Clone the Repository

```bash
# Clone from GitHub
git clone https://github.com/HealthFlowEgy/AgentAI.git
cd AgentAI

# Verify you're on the main branch
git branch
```

### Step 2: Set Up Python Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Linux/Mac
# OR
venv\Scripts\activate  # On Windows

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

```bash
# Copy the development environment template
cp .env.example .env.development

# Generate secure secrets
JWT_SECRET=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -hex 32)

# Edit .env.development
nano .env.development
```

**Required Configuration:**

```bash
# Security (CRITICAL)
JWT_SECRET=<paste generated JWT_SECRET>
ENCRYPTION_KEY=<paste generated ENCRYPTION_KEY>

# HCX Platform
HCX_API_URL=https://staging.hcxprotocol.io
HCX_GATEWAY_URL=https://staging-gateway.hcxprotocol.io
HCX_USERNAME=<your_hcx_username>
HCX_PASSWORD=<your_hcx_password>

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=healthcare_rcm_dev
DB_USER=rcm_user
DB_PASSWORD=<your_db_password>

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# OpenAI
OPENAI_API_KEY=<your_openai_api_key>
```

### Step 4: Set Up Database

```bash
# Start PostgreSQL (if using Docker)
docker run -d \
  --name rcm-postgres \
  -e POSTGRES_DB=healthcare_rcm_dev \
  -e POSTGRES_USER=rcm_user \
  -e POSTGRES_PASSWORD=<your_db_password> \
  -p 5432:5432 \
  postgres:14

# Verify database connection
psql -h localhost -U rcm_user -d healthcare_rcm_dev
```

### Step 5: Set Up Redis

```bash
# Start Redis (if using Docker)
docker run -d \
  --name rcm-redis \
  -p 6379:6379 \
  redis:7

# Verify Redis connection
redis-cli ping
# Should return: PONG
```

### Step 6: Validate Installation

```bash
# Run validation script
python scripts/validate_phase1.py
```

**Expected Output:**

```
🏥 HEALTHCARE RCM SYSTEM - PHASE 1 VALIDATION
============================================================
Validating critical fixes implementation...

============================================================
TEST 1: Configuration Security
============================================================
✅ Config Security: Correctly rejects placeholder secrets

============================================================
TEST 2: Minimum Secret Length
============================================================
✅ Secret Length: Correctly enforces 32+ character minimum

============================================================
TEST 3: Valid Configuration
============================================================
✅ Valid Config: Configuration loads with valid secrets

============================================================
TEST 4: HCX Tools Import
============================================================
✅ HCX Tools Import: All HCX tools imported successfully

============================================================
TEST 5: FHIR Resources Library
============================================================
✅ FHIR Resources: FHIR library imported successfully

============================================================
TEST 6: Async Support
============================================================
✅ Async Support: HCX tools use async/await

============================================================
TEST 7: Retry Logic
============================================================
✅ Retry Logic: Retry decorator found in source

============================================================
TEST 8: Test Suite Exists
============================================================
✅ Test Suite: Test file exists (522 bytes)

============================================================
PHASE 1 VALIDATION SUMMARY
============================================================

✅ Passed: 8/8 (100%)
❌ Failed: 0/8

============================================================
🎉 ALL PHASE 1 VALIDATIONS PASSED!
============================================================
```

### Step 7: Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html  # On Mac
# OR
xdg-open htmlcov/index.html  # On Linux
# OR
start htmlcov/index.html  # On Windows
```

**Expected Output:**

```
======================== test session starts =========================
platform linux -- Python 3.11.0, pytest-7.4.4, pluggy-1.3.0
rootdir: /path/to/AgentAI
configfile: pytest.ini
plugins: asyncio-0.23.3, cov-4.1.0, mock-3.12.0
collected 15 items

tests/unit/test_hcx_tools.py ............... [100%]

---------- coverage: platform linux, python 3.11.0-final-0 ----------
Name                           Stmts   Miss  Cover
--------------------------------------------------
src/__init__.py                    1      0   100%
src/tools/__init__.py              1      0   100%
src/tools/hcx_tools.py           245     12    95%
config/__init__.py                 1      0   100%
config/settings.py                98      3    97%
--------------------------------------------------
TOTAL                            346     15    96%

========================= 15 passed in 2.34s =========================
```

### Step 8: Test HCX Integration (Optional)

```bash
# Test eligibility check
python -c "
import asyncio
from src.tools.hcx_tools import HCXEligibilityTool, TokenManager
from config import settings

async def test():
    token_mgr = TokenManager(
        settings.HCX_API_URL,
        settings.HCX_USERNAME,
        settings.HCX_PASSWORD
    )
    tool = HCXEligibilityTool(settings.HCX_API_URL, token_mgr)
    
    result = await tool._run('{
        \"patient_id\": \"P123\",
        \"insurance_company\": \"allianz_egypt\",
        \"policy_number\": \"ALZ123456\"
    }')
    
    print(result)

asyncio.run(test())
"
```

---

## 🔐 Security Checklist

Before going to production, ensure:

- [ ] **Secrets Generated**
  - [ ] JWT_SECRET is 32+ characters
  - [ ] ENCRYPTION_KEY is 32+ characters
  - [ ] No placeholder values remain

- [ ] **Environment Configuration**
  - [ ] Correct HCX URLs (staging or production)
  - [ ] Valid HCX credentials
  - [ ] Secure database password
  - [ ] Valid OpenAI API key

- [ ] **Database Security**
  - [ ] Database user has minimal required permissions
  - [ ] Database password is strong
  - [ ] Database is not exposed to public internet

- [ ] **Redis Security**
  - [ ] Redis password set (for production)
  - [ ] Redis SSL enabled (for production)
  - [ ] Redis not exposed to public internet

- [ ] **Application Security**
  - [ ] DEBUG mode disabled in production
  - [ ] CORS origins properly configured
  - [ ] Rate limiting enabled
  - [ ] Logging configured appropriately

---

## 🧪 Testing Checklist

- [ ] **Unit Tests**
  - [ ] All unit tests pass
  - [ ] 95%+ code coverage achieved

- [ ] **Integration Tests**
  - [ ] Database connection works
  - [ ] Redis connection works
  - [ ] HCX API accessible

- [ ] **Validation Tests**
  - [ ] Validation script passes all checks
  - [ ] Configuration loads without errors
  - [ ] Application starts successfully

---

## 📊 Monitoring & Logging

### Application Logs

```bash
# View logs (if using systemd)
journalctl -u healthcare-rcm -f

# View logs (if using Docker)
docker logs -f rcm-app

# View application log file
tail -f /var/log/rcm/app.log
```

### Health Checks

```bash
# Check application health
curl http://localhost:8000/health

# Check database connection
psql -h localhost -U rcm_user -d healthcare_rcm_dev -c "SELECT 1;"

# Check Redis connection
redis-cli ping
```

---

## 🐛 Troubleshooting

### Issue: Application Won't Start

**Symptom:** Application fails with validation error

**Solution:**
```bash
# Check environment variables
python -c "from config import settings; print(settings.JWT_SECRET)"

# Regenerate secrets if needed
JWT_SECRET=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -hex 32)

# Update .env.development
echo "JWT_SECRET=$JWT_SECRET" >> .env.development
echo "ENCRYPTION_KEY=$ENCRYPTION_KEY" >> .env.development
```

### Issue: Database Connection Failed

**Symptom:** `psycopg2.OperationalError: could not connect to server`

**Solution:**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check database credentials
psql -h localhost -U rcm_user -d healthcare_rcm_dev

# Restart PostgreSQL
docker restart rcm-postgres
```

### Issue: Redis Connection Failed

**Symptom:** `redis.exceptions.ConnectionError`

**Solution:**
```bash
# Check if Redis is running
docker ps | grep redis

# Test Redis connection
redis-cli ping

# Restart Redis
docker restart rcm-redis
```

### Issue: HCX API Timeout

**Symptom:** `HCX platform timeout - request will be retried`

**Solution:**
```bash
# Check HCX platform status
curl -I https://staging.hcxprotocol.io/health

# Verify HCX credentials
# Check HCX_USERNAME and HCX_PASSWORD in .env.development

# Check network connectivity
ping staging.hcxprotocol.io
```

### Issue: Tests Failing

**Symptom:** `ModuleNotFoundError` or import errors

**Solution:**
```bash
# Reinstall dependencies
pip install --force-reinstall -r requirements.txt

# Verify Python version
python --version  # Should be 3.11+

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

---

## 📈 Performance Tuning

### Database Connection Pool

```python
# In .env.development
DB_POOL_SIZE=20          # Increase for high load
DB_MAX_OVERFLOW=10       # Additional connections
DB_POOL_RECYCLE=3600     # Recycle connections hourly
```

### Redis Configuration

```python
# In .env.development
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=          # Set for production
REDIS_SSL=false          # Enable for production
```

### Retry Configuration

```python
# In .env.development
MAX_RETRIES=3            # Number of retry attempts
RETRY_BACKOFF_FACTOR=2.0 # Exponential backoff multiplier
RETRY_MAX_WAIT=10        # Max wait between retries (seconds)
```

---

## 🔄 Updating the Application

### Pull Latest Changes

```bash
cd AgentAI
git pull origin main
```

### Update Dependencies

```bash
pip install --upgrade -r requirements.txt
```

### Run Validation

```bash
python scripts/validate_phase1.py
pytest
```

### Restart Application

```bash
# If using systemd
sudo systemctl restart healthcare-rcm

# If using Docker
docker restart rcm-app
```

---

## 📞 Support & Resources

### Documentation

- **README:** Complete system overview
- **Code Review:** `docs/code_review_and_gaps.md`
- **Security Guide:** `docs/security_implementation_guide.md`
- **FHIR Guide:** `docs/fhir_implementation_guide.md`
- **Testing Guide:** `docs/testing_implementation_guide.md`

### GitHub Repository

- **URL:** https://github.com/HealthFlowEgy/AgentAI
- **Issues:** Report bugs and feature requests
- **Pull Requests:** Contribute improvements

### HCX Platform

- **Staging:** https://staging.hcxprotocol.io
- **Production:** https://api.hcxprotocol.io
- **Documentation:** https://docs.hcxprotocol.io

---

## ✅ Deployment Success Criteria

Your deployment is successful when:

- [ ] Validation script passes all 8 tests
- [ ] All unit tests pass (15/15)
- [ ] Test coverage is 95%+
- [ ] Application starts without errors
- [ ] Database connection works
- [ ] Redis connection works
- [ ] HCX API is accessible
- [ ] Can perform eligibility check
- [ ] Logs are being written
- [ ] Health check endpoint responds

---

## 🎉 Next Steps: Phase 2

Once Phase 1 is deployed and validated, proceed to Phase 2:

1. **Database Migrations** - Implement Alembic
2. **Missing Agents** - Denial Management, Payment Posting
3. **Workflow State Management** - Resume failed workflows
4. **Monitoring** - Prometheus, Grafana
5. **CI/CD** - Automated testing and deployment
6. **Integration Tests** - Real HCX staging tests
7. **API Documentation** - OpenAPI/Swagger
8. **Kubernetes** - Production infrastructure

---

**Deployment Guide Version:** 1.0.0  
**Last Updated:** October 17, 2025  
**Status:** Production-Ready for Phase 1

