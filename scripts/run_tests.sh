#!/bin/bash
#
# Test Runner Script for Healthcare RCM System
# Week 3-4 Implementation
#

set -e

echo "========================================="
echo "Healthcare RCM System - Test Runner"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest is not installed${NC}"
    echo "Install with: pip install pytest pytest-cov pytest-asyncio"
    exit 1
fi

# Function to run tests
run_tests() {
    local test_type=$1
    local test_path=$2
    local marker=$3
    
    echo -e "${YELLOW}Running $test_type tests...${NC}"
    echo ""
    
    if [ -n "$marker" ]; then
        pytest $test_path -m $marker -v
    else
        pytest $test_path -v
    fi
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✓ $test_type tests passed${NC}"
    else
        echo -e "${RED}✗ $test_type tests failed${NC}"
        return $exit_code
    fi
    
    echo ""
}

# Parse command line arguments
TEST_TYPE=${1:-all}

case $TEST_TYPE in
    unit)
        echo "Running unit tests only..."
        run_tests "Unit" "tests/unit" "unit"
        ;;
    
    integration)
        echo "Running integration tests only..."
        run_tests "Integration" "tests/integration" "integration"
        ;;
    
    api)
        echo "Running API tests only..."
        run_tests "API" "tests/api" "api"
        ;;
    
    fast)
        echo "Running fast tests only (excluding slow tests)..."
        pytest tests/ -m "not slow" -v
        ;;
    
    coverage)
        echo "Running tests with coverage report..."
        pytest tests/ --cov=src --cov-report=html --cov-report=term-missing --cov-fail-under=70 -v
        echo ""
        echo -e "${GREEN}Coverage report generated in htmlcov/index.html${NC}"
        ;;
    
    all)
        echo "Running all tests..."
        echo ""
        
        # Run unit tests
        run_tests "Unit" "tests/unit" "unit"
        
        # Run API tests
        run_tests "API" "tests/api" "api"
        
        # Run integration tests
        run_tests "Integration" "tests/integration" "integration"
        
        echo -e "${GREEN}=========================================${NC}"
        echo -e "${GREEN}All test suites completed!${NC}"
        echo -e "${GREEN}=========================================${NC}"
        ;;
    
    *)
        echo "Usage: $0 {unit|integration|api|fast|coverage|all}"
        echo ""
        echo "Options:"
        echo "  unit        - Run unit tests only"
        echo "  integration - Run integration tests only"
        echo "  api         - Run API tests only"
        echo "  fast        - Run fast tests (exclude slow tests)"
        echo "  coverage    - Run all tests with coverage report"
        echo "  all         - Run all test suites (default)"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Test execution complete!${NC}"

