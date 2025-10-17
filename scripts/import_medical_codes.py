#!/usr/bin/env python3
"""
Medical Code Import Script
Imports ICD-10, CPT, and medical necessity rules from CSV files
"""
import sys
import csv
import argparse
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from sqlalchemy.orm import Session
    from src.services.database import get_db, engine
    from src.models.medical_codes import ICD10Code, CPTCode, MedicalNecessityRule, DenialCode, PaymentCode
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    Session = None  # Define placeholder


def import_icd10_codes(csv_file: str, db) -> int:
    """Import ICD-10 codes from CSV"""
    print(f"Importing ICD-10 codes from {csv_file}...")
    
    count = 0
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            code = ICD10Code(
                code=row['code'],
                description=row['description'],
                category=row.get('category'),
                subcategory=row.get('subcategory'),
                billable=row.get('billable', 'true').lower() == 'true',
                chapter=row.get('chapter'),
                block=row.get('block')
            )
            
            db.merge(code)  # Use merge to handle duplicates
            count += 1
            
            if count % 1000 == 0:
                db.commit()
                print(f"  Imported {count} codes...")
    
    db.commit()
    print(f"✅ Imported {count} ICD-10 codes")
    return count


def import_cpt_codes(csv_file: str, db) -> int:
    """Import CPT codes from CSV"""
    print(f"Importing CPT codes from {csv_file}...")
    
    count = 0
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            code = CPTCode(
                code=row['code'],
                description=row['description'],
                category=row.get('category'),
                subcategory=row.get('subcategory'),
                base_rvu=float(row['base_rvu']) if row.get('base_rvu') else None,
                facility_fee=float(row['facility_fee']) if row.get('facility_fee') else None,
                non_facility_fee=float(row['non_facility_fee']) if row.get('non_facility_fee') else None,
                active=row.get('active', 'true').lower() == 'true'
            )
            
            db.merge(code)
            count += 1
            
            if count % 1000 == 0:
                db.commit()
                print(f"  Imported {count} codes...")
    
    db.commit()
    print(f"✅ Imported {count} CPT codes")
    return count


def import_medical_necessity_rules(csv_file: str, db) -> int:
    """Import medical necessity rules from CSV"""
    print(f"Importing medical necessity rules from {csv_file}...")
    
    count = 0
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Parse ICD-10 codes (comma-separated)
            icd10_codes = [code.strip() for code in row['icd10_codes'].split(',')]
            
            rule = MedicalNecessityRule(
                cpt_code=row['cpt_code'],
                icd10_codes=icd10_codes,
                payer_id=row.get('payer_id') if row.get('payer_id') else None,
                rule_description=row.get('rule_description'),
                frequency_limit=int(row['frequency_limit']) if row.get('frequency_limit') else None,
                frequency_period_days=int(row['frequency_period_days']) if row.get('frequency_period_days') else None,
                min_age=int(row['min_age']) if row.get('min_age') else None,
                max_age=int(row['max_age']) if row.get('max_age') else None,
                gender_restriction=row.get('gender_restriction') if row.get('gender_restriction') else None,
                active=row.get('active', 'true').lower() == 'true'
            )
            
            db.add(rule)
            count += 1
            
            if count % 100 == 0:
                db.commit()
                print(f"  Imported {count} rules...")
    
    db.commit()
    print(f"✅ Imported {count} medical necessity rules")
    return count


def create_sample_data():
    """Create sample CSV files for testing"""
    print("Creating sample data files...")
    
    # Create data directory
    data_dir = Path(__file__).parent.parent / 'data' / 'medical_codes'
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Sample ICD-10 codes
    icd10_file = data_dir / 'sample_icd10_codes.csv'
    with open(icd10_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['code', 'description', 'category', 'billable', 'chapter'])
        writer.writeheader()
        writer.writerows([
            {'code': 'E11', 'description': 'Type 2 diabetes mellitus', 'category': 'Endocrine', 'billable': 'false', 'chapter': 'Endocrine, nutritional and metabolic diseases'},
            {'code': 'E11.9', 'description': 'Type 2 diabetes mellitus without complications', 'category': 'Endocrine', 'billable': 'true', 'chapter': 'Endocrine, nutritional and metabolic diseases'},
            {'code': 'I21', 'description': 'Acute myocardial infarction', 'category': 'Circulatory', 'billable': 'false', 'chapter': 'Diseases of the circulatory system'},
            {'code': 'I21.9', 'description': 'Acute myocardial infarction, unspecified', 'category': 'Circulatory', 'billable': 'true', 'chapter': 'Diseases of the circulatory system'},
            {'code': 'J44', 'description': 'Chronic obstructive pulmonary disease', 'category': 'Respiratory', 'billable': 'false', 'chapter': 'Diseases of the respiratory system'},
            {'code': 'J44.0', 'description': 'COPD with acute lower respiratory infection', 'category': 'Respiratory', 'billable': 'true', 'chapter': 'Diseases of the respiratory system'},
        ])
    print(f"✅ Created {icd10_file}")
    
    # Sample CPT codes
    cpt_file = data_dir / 'sample_cpt_codes.csv'
    with open(cpt_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['code', 'description', 'category', 'base_rvu', 'facility_fee', 'non_facility_fee'])
        writer.writeheader()
        writer.writerows([
            {'code': '99213', 'description': 'Office visit, established patient, 20-29 minutes', 'category': 'E&M', 'base_rvu': '1.5', 'facility_fee': '75.00', 'non_facility_fee': '110.00'},
            {'code': '99214', 'description': 'Office visit, established patient, 30-39 minutes', 'category': 'E&M', 'base_rvu': '2.5', 'facility_fee': '110.00', 'non_facility_fee': '165.00'},
            {'code': '80053', 'description': 'Comprehensive metabolic panel', 'category': 'Laboratory', 'base_rvu': '0.5', 'facility_fee': '25.00', 'non_facility_fee': '25.00'},
            {'code': '93000', 'description': 'Electrocardiogram, complete', 'category': 'Cardiology', 'base_rvu': '0.3', 'facility_fee': '15.00', 'non_facility_fee': '15.00'},
        ])
    print(f"✅ Created {cpt_file}")
    
    # Sample medical necessity rules
    rules_file = data_dir / 'sample_medical_necessity_rules.csv'
    with open(rules_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['cpt_code', 'icd10_codes', 'payer_id', 'rule_description', 'frequency_limit', 'frequency_period_days'])
        writer.writeheader()
        writer.writerows([
            {'cpt_code': '99213', 'icd10_codes': 'E11.9,I21.9,J44.0', 'payer_id': '', 'rule_description': 'Office visit medically necessary for chronic conditions', 'frequency_limit': '', 'frequency_period_days': ''},
            {'cpt_code': '80053', 'icd10_codes': 'E11.9', 'payer_id': '', 'rule_description': 'Metabolic panel required for diabetes monitoring', 'frequency_limit': '4', 'frequency_period_days': '365'},
            {'cpt_code': '93000', 'icd10_codes': 'I21.9', 'payer_id': '', 'rule_description': 'ECG medically necessary for MI', 'frequency_limit': '', 'frequency_period_days': ''},
        ])
    print(f"✅ Created {rules_file}")
    
    print("")
    print("Sample data files created successfully!")
    print(f"Location: {data_dir}")
    print("")
    print("To import sample data:")
    print(f"  python scripts/import_medical_codes.py import-icd10 {icd10_file}")
    print(f"  python scripts/import_medical_codes.py import-cpt {cpt_file}")
    print(f"  python scripts/import_medical_codes.py import-rules {rules_file}")


def download_instructions():
    """Print instructions for downloading full medical code databases"""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                 MEDICAL CODE DATABASE DOWNLOAD INSTRUCTIONS                 ║
╚════════════════════════════════════════════════════════════════════════════╝

To obtain full medical code databases for production use:

📚 ICD-10 CODES (70,000+ codes)
─────────────────────────────────
Source: CDC / WHO
URL: https://www.cdc.gov/nchs/icd/icd-10-cm.htm
Format: Excel or CSV
Cost: Free (public domain)

Steps:
1. Download ICD-10-CM code files from CDC
2. Convert to CSV format with columns: code, description, category, billable
3. Import using: python scripts/import_medical_codes.py import-icd10 <file>

📚 CPT CODES (10,000+ codes)
────────────────────────────
Source: American Medical Association (AMA)
URL: https://www.ama-assn.org/practice-management/cpt
Format: Proprietary (requires license)
Cost: $300-500 USD annually

⚠️  CPT codes are copyrighted by AMA and require a license for commercial use.

Steps:
1. Purchase CPT code license from AMA
2. Download CPT code files
3. Convert to CSV format with columns: code, description, category, base_rvu, facility_fee
4. Import using: python scripts/import_medical_codes.py import-cpt <file>

📚 MEDICAL NECESSITY RULES
──────────────────────────
Source: Insurance payers (Allianz, MetLife, AXA, HIO)
Format: Custom
Cost: Varies

Steps:
1. Obtain medical policy documents from each payer
2. Extract ICD-10 to CPT code relationships
3. Create CSV with columns: cpt_code, icd10_codes, payer_id, rule_description
4. Import using: python scripts/import_medical_codes.py import-rules <file>

📚 ALTERNATIVE: SAMPLE DATA FOR TESTING
────────────────────────────────────────
For development and testing, use sample data:

python scripts/import_medical_codes.py create-samples

This creates ~10 sample codes for each type.

╔════════════════════════════════════════════════════════════════════════════╗
║                              IMPORTANT NOTES                                ║
╚════════════════════════════════════════════════════════════════════════════╝

⚠️  LEGAL COMPLIANCE:
   - ICD-10 codes are public domain (free to use)
   - CPT codes require AMA license for commercial use
   - Medical necessity rules are payer-specific

⚠️  DATABASE SIZE:
   - ICD-10: ~70,000 codes (~50 MB)
   - CPT: ~10,000 codes (~10 MB)
   - Full database: ~60 MB total

⚠️  IMPORT TIME:
   - ICD-10: ~5-10 minutes
   - CPT: ~2-5 minutes
   - Rules: ~1-2 minutes

⚠️  PRODUCTION REQUIREMENT:
   - Full medical code database is REQUIRED for production use
   - Sample data is only for development/testing
   - System will not function correctly with sample data only

For questions or assistance, contact your system administrator.
""")


def main():
    parser = argparse.ArgumentParser(description='Import medical codes into database')
    parser.add_argument('action', choices=['import-icd10', 'import-cpt', 'import-rules', 'create-samples', 'download-info'],
                       help='Action to perform')
    parser.add_argument('file', nargs='?', help='CSV file to import')
    
    args = parser.parse_args()
    
    if args.action == 'download-info':
        download_instructions()
        return
    
    if args.action == 'create-samples':
        create_sample_data()
        return
    
    if not args.file:
        print("Error: CSV file required for import actions")
        parser.print_help()
        sys.exit(1)
    
    if not DEPENDENCIES_AVAILABLE:
        print("Error: Required dependencies not installed")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)
    
    # Get database session
    with next(get_db()) as db:
        if args.action == 'import-icd10':
            count = import_icd10_codes(args.file, db)
        elif args.action == 'import-cpt':
            count = import_cpt_codes(args.file, db)
        elif args.action == 'import-rules':
            count = import_medical_necessity_rules(args.file, db)
        
        print(f"\n✅ Import complete: {count} records")


if __name__ == '__main__':
    main()

