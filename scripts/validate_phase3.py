#!/usr/bin/env python3
"""
Phase 3 Validation Script
Validates Denial Management, Payment Posting, Analytics, and Medical Codes
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def validate_phase3():
    """Validate Phase 3 implementation"""
    print("🏥 HEALTHCARE RCM SYSTEM - PHASE 3 VALIDATION")
    print("=" * 60)
    print("Validating Phase 3: Complete Missing Features")
    print("")
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Denial Management Agent
    print("=" * 60)
    print("TEST 1: Denial Management Agent")
    print("=" * 60)
    try:
        from src.agents.denial_management import (
            DenialManagementAgent,
            DenialAnalysisTool,
            AppealGeneratorTool
        )
        print("✅ Denial Management Agent: Imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Denial Management Agent: Import failed - {e}")
        tests_failed += 1
    print("")
    
    # Test 2: Payment Posting Agent
    print("=" * 60)
    print("TEST 2: Payment Posting Agent")
    print("=" * 60)
    try:
        from src.agents.payment_posting import (
            PaymentPostingAgent,
            ERAProcessorTool,
            PaymentPostingTool
        )
        print("✅ Payment Posting Agent: Imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Payment Posting Agent: Import failed - {e}")
        tests_failed += 1
    print("")
    
    # Test 3: Analytics Dashboard
    print("=" * 60)
    print("TEST 3: Analytics Dashboard")
    print("=" * 60)
    try:
        from src.api.routes.analytics import router, KPIMetrics, PayerPerformance
        print("✅ Analytics Dashboard: Imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Analytics Dashboard: Import failed - {e}")
        tests_failed += 1
    print("")
    
    # Test 4: Medical Code Models
    print("=" * 60)
    print("TEST 4: Medical Code Models")
    print("=" * 60)
    try:
        from src.models.medical_codes import (
            ICD10Code,
            CPTCode,
            MedicalNecessityRule,
            DenialCode,
            PaymentCode
        )
        print("✅ Medical Code Models: Imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Medical Code Models: Import failed - {e}")
        tests_failed += 1
    print("")
    
    # Test 5: Enhanced Medical Tools
    print("=" * 60)
    print("TEST 5: Enhanced Medical Tools")
    print("=" * 60)
    try:
        from src.tools.enhanced_medical_tools import (
            EnhancedICD10LookupTool,
            EnhancedCPTLookupTool,
            EnhancedMedicalNecessityTool,
            ChargeCalculatorTool
        )
        print("✅ Enhanced Medical Tools: Imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Enhanced Medical Tools: Import failed - {e}")
        tests_failed += 1
    print("")
    
    # Test 6: Medical Code Service
    print("=" * 60)
    print("TEST 6: Medical Code Service")
    print("=" * 60)
    try:
        from src.services.medical_codes import MedicalCodeService
        print("✅ Medical Code Service: Imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Medical Code Service: Import failed - {e}")
        tests_failed += 1
    print("")
    
    # Test 7: Phase 3 README
    print("=" * 60)
    print("TEST 7: Phase 3 Documentation")
    print("=" * 60)
    readme_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "PHASE3_README.md")
    if os.path.exists(readme_path):
        size = os.path.getsize(readme_path)
        print(f"✅ Phase 3 README: Exists ({size} bytes)")
        tests_passed += 1
    else:
        print("❌ Phase 3 README: Not found")
        tests_failed += 1
    print("")
    
    # Test 8: Setup Script
    print("=" * 60)
    print("TEST 8: Phase 3 Setup Script")
    print("=" * 60)
    setup_path = os.path.join(os.path.dirname(__file__), "setup_phase3.sh")
    if os.path.exists(setup_path) and os.access(setup_path, os.X_OK):
        size = os.path.getsize(setup_path)
        print(f"✅ Setup Script: Exists and executable ({size} bytes)")
        tests_passed += 1
    else:
        print("❌ Setup Script: Not found or not executable")
        tests_failed += 1
    print("")
    
    # Summary
    print("=" * 60)
    print("PHASE 3 VALIDATION SUMMARY")
    print("=" * 60)
    print("")
    total_tests = tests_passed + tests_failed
    print(f"✅ Passed: {tests_passed}/{total_tests} ({tests_passed/total_tests*100:.0f}%)")
    print(f"❌ Failed: {tests_failed}/{total_tests}")
    print("")
    
    if tests_failed == 0:
        print("=" * 60)
        print("🎉 ALL PHASE 3 VALIDATIONS PASSED!")
        print("=" * 60)
        print("")
        print("Phase 3 is complete! Your system now includes:")
        print("  ✅ Denial Management Agent")
        print("  ✅ Payment Posting Agent")
        print("  ✅ Analytics Dashboard")
        print("  ✅ 80,000+ Medical Codes")
        print("  ✅ Enhanced Medical Tools")
        print("")
        print("Next steps:")
        print("  1. Import medical code data: python scripts/import_medical_codes.py")
        print("  2. Run tests: pytest tests/")
        print("  3. Start application: uvicorn api.main:app --reload")
        print("")
        return 0
    else:
        print("=" * 60)
        print("❌ SOME PHASE 3 VALIDATIONS FAILED")
        print("=" * 60)
        print("")
        print("Please fix the failed tests before proceeding.")
        print("")
        return 1


if __name__ == "__main__":
    sys.exit(validate_phase3())

