#!/usr/bin/env python3
"""
Phase 1 Validation Script
Validates that all Phase 1 critical fixes are properly implemented
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class Phase1Validator:
    """Validates Phase 1 implementation"""
    
    def __init__(self):
        self.passed = []
        self.failed = []
    
    def test_config_security(self):
        """Test 1: Configuration security validation"""
        print("\n" + "="*60)
        print("TEST 1: Configuration Security")
        print("="*60)
        
        try:
            # Try to import with placeholder values (should fail)
            os.environ['JWT_SECRET'] = 'your-secret-key'
            os.environ['ENCRYPTION_KEY'] = 'your-encryption-key'
            
            try:
                from config import settings
                self.record_failure("Config Security", "Should reject placeholder secrets")
            except ValueError as e:
                if "placeholder" in str(e).lower():
                    self.record_success("Config Security", "Correctly rejects placeholder secrets")
                else:
                    self.record_failure("Config Security", f"Wrong error: {e}")
        except Exception as e:
            self.record_failure("Config Security", str(e))
    
    def test_config_minimum_length(self):
        """Test 2: Minimum secret length validation"""
        print("\n" + "="*60)
        print("TEST 2: Minimum Secret Length")
        print("="*60)
        
        try:
            os.environ['JWT_SECRET'] = 'short'
            os.environ['ENCRYPTION_KEY'] = 'also_short'
            
            try:
                from config import settings
                self.record_failure("Secret Length", "Should reject short secrets")
            except ValueError as e:
                if "32 characters" in str(e):
                    self.record_success("Secret Length", "Correctly enforces 32+ character minimum")
                else:
                    self.record_failure("Secret Length", f"Wrong error: {e}")
        except Exception as e:
            self.record_failure("Secret Length", str(e))
    
    def test_valid_config(self):
        """Test 3: Valid configuration loads successfully"""
        print("\n" + "="*60)
        print("TEST 3: Valid Configuration")
        print("="*60)
        
        try:
            # Set valid environment variables
            os.environ['ENVIRONMENT'] = 'test'
            os.environ['JWT_SECRET'] = 'a' * 32
            os.environ['ENCRYPTION_KEY'] = 'b' * 32
            os.environ['HCX_API_URL'] = 'http://test'
            os.environ['HCX_GATEWAY_URL'] = 'http://test'
            os.environ['HCX_USERNAME'] = 'test'
            os.environ['HCX_PASSWORD'] = 'test'
            os.environ['DB_PASSWORD'] = 'test'
            os.environ['OPENAI_API_KEY'] = 'sk-test'
            
            # Force reload of settings module
            if 'config.settings' in sys.modules:
                del sys.modules['config.settings']
            if 'config' in sys.modules:
                del sys.modules['config']
            
            from config import settings
            
            if settings.JWT_SECRET == 'a' * 32:
                self.record_success("Valid Config", "Configuration loads with valid secrets")
            else:
                self.record_failure("Valid Config", "Settings not loaded correctly")
                
        except Exception as e:
            self.record_failure("Valid Config", str(e))
    
    def test_hcx_tools_import(self):
        """Test 4: HCX tools can be imported"""
        print("\n" + "="*60)
        print("TEST 4: HCX Tools Import")
        print("="*60)
        
        try:
            from src.tools.hcx_tools import (
                TokenManager,
                HCXEligibilityTool,
                HCXPreAuthTool,
                HCXClaimSubmitTool,
                HCXClaimStatusTool
            )
            self.record_success("HCX Tools Import", "All HCX tools imported successfully")
        except ImportError as e:
            self.record_failure("HCX Tools Import", str(e))
        except Exception as e:
            self.record_failure("HCX Tools Import", str(e))
    
    def test_fhir_resources(self):
        """Test 5: FHIR resources library is available"""
        print("\n" + "="*60)
        print("TEST 5: FHIR Resources Library")
        print("="*60)
        
        try:
            from fhir.resources.coverageeligibilityrequest import CoverageEligibilityRequest
            from fhir.resources.claim import Claim
            from fhir.resources.coding import Coding
            
            self.record_success("FHIR Resources", "FHIR library imported successfully")
        except ImportError as e:
            self.record_failure("FHIR Resources", f"FHIR library not installed: {e}")
        except Exception as e:
            self.record_failure("FHIR Resources", str(e))
    
    def test_async_support(self):
        """Test 6: Async support in HCX tools"""
        print("\n" + "="*60)
        print("TEST 6: Async Support")
        print("="*60)
        
        try:
            import inspect
            from src.tools.hcx_tools import HCXEligibilityTool
            
            tool = HCXEligibilityTool(hcx_url="http://test", token_manager=None)
            
            if inspect.iscoroutinefunction(tool._run):
                self.record_success("Async Support", "HCX tools use async/await")
            else:
                self.record_failure("Async Support", "_run method is not async")
        except Exception as e:
            self.record_failure("Async Support", str(e))
    
    def test_retry_logic(self):
        """Test 7: Retry logic is implemented"""
        print("\n" + "="*60)
        print("TEST 7: Retry Logic")
        print("="*60)
        
        try:
            import inspect
            from src.tools.hcx_tools import HCXEligibilityTool
            
            # Check if tenacity retry decorator is applied
            tool = HCXEligibilityTool(hcx_url="http://test", token_manager=None)
            
            # Check if _run has retry wrapper
            if hasattr(tool._run, 'retry'):
                self.record_success("Retry Logic", "Retry logic implemented with tenacity")
            else:
                # Alternative check: look for retry in source
                source = inspect.getsource(HCXEligibilityTool._run)
                if '@retry' in source or 'tenacity' in source:
                    self.record_success("Retry Logic", "Retry decorator found in source")
                else:
                    self.record_failure("Retry Logic", "No retry logic detected")
        except Exception as e:
            self.record_failure("Retry Logic", str(e))
    
    def test_tests_exist(self):
        """Test 8: Test files exist"""
        print("\n" + "="*60)
        print("TEST 8: Test Suite Exists")
        print("="*60)
        
        test_file = project_root / "tests" / "unit" / "test_hcx_tools.py"
        
        if test_file.exists():
            # Check file size
            size = test_file.stat().st_size
            if size > 1000:  # At least 1KB
                self.record_success("Test Suite", f"Test file exists ({size} bytes)")
            else:
                self.record_failure("Test Suite", "Test file too small")
        else:
            self.record_failure("Test Suite", "test_hcx_tools.py not found")
    
    def record_success(self, test: str, reason: str):
        self.passed.append((test, reason))
        print(f"✅ {test}: {reason}")
    
    def record_failure(self, test: str, reason: str):
        self.failed.append((test, reason))
        print(f"❌ {test}: {reason}")
    
    def print_summary(self):
        """Print validation summary"""
        print("\n" + "="*60)
        print("PHASE 1 VALIDATION SUMMARY")
        print("="*60)
        
        total = len(self.passed) + len(self.failed)
        passed_pct = (len(self.passed) / total * 100) if total > 0 else 0
        
        print(f"\n✅ Passed: {len(self.passed)}/{total} ({passed_pct:.0f}%)")
        print(f"❌ Failed: {len(self.failed)}/{total}")
        
        if self.failed:
            print("\n❌ Failed Tests:")
            for test, reason in self.failed:
                print(f"   - {test}: {reason}")
        
        print("\n" + "="*60)
        
        if len(self.failed) == 0:
            print("🎉 ALL PHASE 1 VALIDATIONS PASSED!")
            print("="*60)
            return 0
        else:
            print("⚠️  SOME VALIDATIONS FAILED")
            print("="*60)
            return 1


def main():
    """Run all validation tests"""
    print("\n" + "="*60)
    print("🏥 HEALTHCARE RCM SYSTEM - PHASE 1 VALIDATION")
    print("="*60)
    print("Validating critical fixes implementation...")
    
    validator = Phase1Validator()
    
    # Run all tests
    validator.test_config_security()
    validator.test_config_minimum_length()
    validator.test_valid_config()
    validator.test_hcx_tools_import()
    validator.test_fhir_resources()
    validator.test_async_support()
    validator.test_retry_logic()
    validator.test_tests_exist()
    
    # Print summary
    exit_code = validator.print_summary()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

