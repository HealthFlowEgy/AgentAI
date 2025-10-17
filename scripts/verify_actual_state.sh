#!/bin/bash
# ============================================
# Verification Script - Measure Actual State
# Provides honest metrics about system completeness
# ============================================

set -e

echo "🔍 HEALTHCARE RCM SYSTEM - ACTUAL STATE VERIFICATION"
echo "========================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Results
PASSED=0
FAILED=0

# ============================================
# 1. Code Statistics
# ============================================
echo "=========================================="
echo "1. CODE STATISTICS"
echo "=========================================="

echo -n "Python files: "
PYTHON_FILES=$(find . -name "*.py" -type f | grep -v __pycache__ | grep -v venv | wc -l)
echo "$PYTHON_FILES"

echo -n "Total files: "
TOTAL_FILES=$(find . -type f | grep -v .git | grep -v __pycache__ | grep -v venv | wc -l)
echo "$TOTAL_FILES"

echo -n "Lines of Python code: "
PYTHON_LINES=$(find . -name "*.py" -type f | grep -v __pycache__ | grep -v venv | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
echo "$PYTHON_LINES"

echo ""

# ============================================
# 2. Test Coverage Measurement
# ============================================
echo "=========================================="
echo "2. TEST COVERAGE (ACTUAL)"
echo "=========================================="

if command -v pytest &> /dev/null; then
    echo "Running pytest with coverage..."
    
    # Create coverage report
    pytest --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=0 2>/dev/null || true
    
    # Extract coverage percentage
    if [ -f .coverage ]; then
        COVERAGE=$(coverage report | tail -1 | awk '{print $NF}')
        echo -e "${YELLOW}Actual Test Coverage: $COVERAGE${NC}"
        
        # Check if coverage meets threshold
        COVERAGE_NUM=$(echo $COVERAGE | sed 's/%//')
        if (( $(echo "$COVERAGE_NUM >= 70" | bc -l) )); then
            echo -e "${GREEN}✅ Coverage meets 70% threshold${NC}"
            ((PASSED++))
        else
            echo -e "${RED}❌ Coverage below 70% threshold${NC}"
            ((FAILED++))
        fi
    else
        echo -e "${RED}❌ No coverage data found${NC}"
        ((FAILED++))
    fi
else
    echo -e "${RED}❌ pytest not installed${NC}"
    ((FAILED++))
fi

echo ""

# ============================================
# 3. Medical Code Database Check
# ============================================
echo "=========================================="
echo "3. MEDICAL CODE DATABASE"
echo "=========================================="

if command -v psql &> /dev/null && [ ! -z "$DATABASE_URL" ]; then
    echo "Checking medical code database..."
    
    # Count ICD-10 codes
    ICD10_COUNT=$(psql $DATABASE_URL -t -c "SELECT COUNT(*) FROM icd10_codes;" 2>/dev/null || echo "0")
    ICD10_COUNT=$(echo $ICD10_COUNT | xargs)
    echo "ICD-10 codes: $ICD10_COUNT"
    
    if [ "$ICD10_COUNT" -gt 50000 ]; then
        echo -e "${GREEN}✅ ICD-10 database loaded (50K+ codes)${NC}"
        ((PASSED++))
    elif [ "$ICD10_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}⚠️  ICD-10 database has sample data only ($ICD10_COUNT codes)${NC}"
        ((FAILED++))
    else
        echo -e "${RED}❌ ICD-10 database empty${NC}"
        ((FAILED++))
    fi
    
    # Count CPT codes
    CPT_COUNT=$(psql $DATABASE_URL -t -c "SELECT COUNT(*) FROM cpt_codes;" 2>/dev/null || echo "0")
    CPT_COUNT=$(echo $CPT_COUNT | xargs)
    echo "CPT codes: $CPT_COUNT"
    
    if [ "$CPT_COUNT" -gt 8000 ]; then
        echo -e "${GREEN}✅ CPT database loaded (8K+ codes)${NC}"
        ((PASSED++))
    elif [ "$CPT_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}⚠️  CPT database has sample data only ($CPT_COUNT codes)${NC}"
        ((FAILED++))
    else
        echo -e "${RED}❌ CPT database empty${NC}"
        ((FAILED++))
    fi
else
    echo -e "${YELLOW}⚠️  Database not accessible (psql not installed or DATABASE_URL not set)${NC}"
    echo "Cannot verify medical code counts"
    ((FAILED++))
fi

echo ""

# ============================================
# 4. Integration Tests
# ============================================
echo "=========================================="
echo "4. INTEGRATION TESTS"
echo "=========================================="

if [ -d "tests/integration" ]; then
    INTEGRATION_TESTS=$(find tests/integration -name "test_*.py" | wc -l)
    echo "Integration test files: $INTEGRATION_TESTS"
    
    if [ "$INTEGRATION_TESTS" -gt 0 ]; then
        echo -e "${GREEN}✅ Integration tests exist${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ No integration tests found${NC}"
        ((FAILED++))
    fi
else
    echo -e "${RED}❌ Integration test directory missing${NC}"
    ((FAILED++))
fi

echo ""

# ============================================
# 5. Security Scan
# ============================================
echo "=========================================="
echo "5. SECURITY SCAN"
echo "=========================================="

# Check for hardcoded secrets
echo "Scanning for hardcoded secrets..."
HARDCODED_SECRETS=$(grep -r "password\s*=\s*['\"]" --include="*.py" src/ 2>/dev/null | wc -l)
HARDCODED_SECRETS=$((HARDCODED_SECRETS + $(grep -r "api_key\s*=\s*['\"]" --include="*.py" src/ 2>/dev/null | wc -l)))
HARDCODED_SECRETS=$((HARDCODED_SECRETS + $(grep -r "secret\s*=\s*['\"]" --include="*.py" src/ 2>/dev/null | wc -l)))

if [ "$HARDCODED_SECRETS" -eq 0 ]; then
    echo -e "${GREEN}✅ No hardcoded secrets found${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ Found $HARDCODED_SECRETS potential hardcoded secrets${NC}"
    ((FAILED++))
fi

# Check for bandit
if command -v bandit &> /dev/null; then
    echo "Running bandit security scan..."
    bandit -r src/ -f txt -o bandit_report.txt 2>/dev/null || true
    
    if [ -f bandit_report.txt ]; then
        HIGH_ISSUES=$(grep -c "Severity: High" bandit_report.txt || echo "0")
        if [ "$HIGH_ISSUES" -eq 0 ]; then
            echo -e "${GREEN}✅ No high-severity security issues${NC}"
            ((PASSED++))
        else
            echo -e "${RED}❌ Found $HIGH_ISSUES high-severity security issues${NC}"
            ((FAILED++))
        fi
    fi
else
    echo -e "${YELLOW}⚠️  bandit not installed, skipping security scan${NC}"
fi

echo ""

# ============================================
# 6. Agent Implementation Check
# ============================================
echo "=========================================="
echo "6. AGENT IMPLEMENTATION"
echo "=========================================="

AGENT_FILES=$(find src/agents -name "*.py" -type f 2>/dev/null | wc -l)
echo "Agent files: $AGENT_FILES"

if [ "$AGENT_FILES" -ge 5 ]; then
    echo -e "${GREEN}✅ Multiple agent files exist${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ Insufficient agent implementations${NC}"
    ((FAILED++))
fi

echo ""

# ============================================
# 7. Documentation Check
# ============================================
echo "=========================================="
echo "7. DOCUMENTATION"
echo "=========================================="

REQUIRED_DOCS=("README.md" "DEPLOYMENT_GUIDE.md" "HONEST_ASSESSMENT.md")
DOC_COUNT=0

for doc in "${REQUIRED_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        ((DOC_COUNT++))
        echo -e "${GREEN}✅ $doc exists${NC}"
    else
        echo -e "${RED}❌ $doc missing${NC}"
    fi
done

if [ "$DOC_COUNT" -eq ${#REQUIRED_DOCS[@]} ]; then
    ((PASSED++))
else
    ((FAILED++))
fi

echo ""

# ============================================
# 8. Configuration Validation
# ============================================
echo "=========================================="
echo "8. CONFIGURATION"
echo "=========================================="

if [ -f ".env.example" ]; then
    echo -e "${GREEN}✅ .env.example exists${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ .env.example missing${NC}"
    ((FAILED++))
fi

if [ -f "config/settings.py" ]; then
    echo -e "${GREEN}✅ settings.py exists${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ settings.py missing${NC}"
    ((FAILED++))
fi

echo ""

# ============================================
# SUMMARY
# ============================================
echo "=========================================="
echo "VERIFICATION SUMMARY"
echo "=========================================="
echo ""

TOTAL=$((PASSED + FAILED))
PERCENTAGE=$((PASSED * 100 / TOTAL))

echo "Checks Passed: $PASSED/$TOTAL ($PERCENTAGE%)"
echo "Checks Failed: $FAILED/$TOTAL"
echo ""

if [ "$PERCENTAGE" -ge 80 ]; then
    echo -e "${GREEN}✅ SYSTEM STATUS: GOOD${NC}"
    echo "Production Readiness: 80%+"
elif [ "$PERCENTAGE" -ge 60 ]; then
    echo -e "${YELLOW}⚠️  SYSTEM STATUS: FAIR${NC}"
    echo "Production Readiness: 60-80%"
else
    echo -e "${RED}❌ SYSTEM STATUS: NEEDS WORK${NC}"
    echo "Production Readiness: <60%"
fi

echo ""
echo "=========================================="
echo "HONEST METRICS"
echo "=========================================="
echo ""
echo "Python Files: $PYTHON_FILES"
echo "Lines of Code: $PYTHON_LINES"
echo "Test Coverage: ${COVERAGE:-Unknown}"
echo "ICD-10 Codes: ${ICD10_COUNT:-Unknown}"
echo "CPT Codes: ${CPT_COUNT:-Unknown}"
echo "Integration Tests: ${INTEGRATION_TESTS:-0}"
echo "Security Issues: ${HIGH_ISSUES:-Unknown}"
echo ""
echo "For detailed reports:"
echo "  - Test Coverage: htmlcov/index.html"
echo "  - Security Scan: bandit_report.txt"
echo ""

exit 0

