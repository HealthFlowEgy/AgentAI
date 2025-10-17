#!/usr/bin/env python3
"""
Complete medical codes import system with async processing
Supports ICD-10, CPT, and HCPCS codes from CSV files
Week 1-2 Implementation
"""
import sys
import csv
import asyncio
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check for dependencies
try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    import click
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    logger.error(f"Missing dependencies: {e}")
    logger.error("Install with: pip install sqlalchemy[asyncio] asyncpg click")


class MedicalCodesImporter:
    """Import medical codes from various sources with async processing"""
    
    def __init__(self, database_url: str):
        if not DEPENDENCIES_AVAILABLE:
            raise RuntimeError("Required dependencies not installed")
        
        self.database_url = database_url
        self.engine = create_async_engine(database_url, echo=False, pool_size=20)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        self.batch_size = 1000
        
    async def import_icd10_codes(self, csv_path: Path) -> int:
        """
        Import ICD-10 codes from CSV
        
        Expected CSV format:
        code,description,category,subcategory,billable
        A00.0,Cholera due to Vibrio cholerae 01,Infectious,Intestinal,1
        """
        logger.info(f"Importing ICD-10 codes from {csv_path}")
        
        codes_imported = 0
        batch = []
        
        async with self.async_session() as session:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    code_data = {
                        'code': row['code'].strip().upper(),
                        'description': row['description'].strip(),
                        'category': row.get('category', '').strip() or None,
                        'subcategory': row.get('subcategory', '').strip() or None,
                        'is_billable': row.get('billable', '1') == '1',
                        'metadata': json.dumps({
                            'import_date': datetime.utcnow().isoformat(),
                            'source': 'CMS'
                        })
                    }
                    
                    batch.append(code_data)
                    
                    if len(batch) >= self.batch_size:
                        await self._insert_batch(session, 'icd10_codes', batch)
                        codes_imported += len(batch)
                        logger.info(f"Imported {codes_imported} ICD-10 codes...")
                        batch = []
                
                # Insert remaining codes
                if batch:
                    await self._insert_batch(session, 'icd10_codes', batch)
                    codes_imported += len(batch)
                
                await session.commit()
        
        logger.info(f"✅ Imported {codes_imported} ICD-10 codes")
        return codes_imported
    
    async def import_cpt_codes(self, csv_path: Path) -> int:
        """
        Import CPT codes from CSV
        
        Expected CSV format:
        code,description,category,modifier_allowed,base_rate,rvu
        99213,Office visit established patient,Evaluation,1,150.00,1.5
        """
        logger.info(f"Importing CPT codes from {csv_path}")
        
        codes_imported = 0
        batch = []
        
        async with self.async_session() as session:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    code_data = {
                        'code': row['code'].strip(),
                        'description': row['description'].strip(),
                        'category': row.get('category', '').strip() or None,
                        'modifier_allowed': row.get('modifier_allowed', '1') == '1',
                        'base_rate': float(row.get('base_rate', 0)) if row.get('base_rate') else None,
                        'rvu': float(row.get('rvu', 0)) if row.get('rvu') else None,
                        'metadata': json.dumps({
                            'import_date': datetime.utcnow().isoformat(),
                            'source': 'AMA'
                        })
                    }
                    
                    batch.append(code_data)
                    
                    if len(batch) >= self.batch_size:
                        await self._insert_batch(session, 'cpt_codes', batch)
                        codes_imported += len(batch)
                        logger.info(f"Imported {codes_imported} CPT codes...")
                        batch = []
                
                if batch:
                    await self._insert_batch(session, 'cpt_codes', batch)
                    codes_imported += len(batch)
                
                await session.commit()
        
        logger.info(f"✅ Imported {codes_imported} CPT codes")
        return codes_imported
    
    async def import_hcpcs_codes(self, csv_path: Path) -> int:
        """
        Import HCPCS codes from CSV
        
        Expected CSV format:
        code,description,level,category
        A0426,Ambulance service advanced life support,II,Transportation
        """
        logger.info(f"Importing HCPCS codes from {csv_path}")
        
        codes_imported = 0
        batch = []
        
        async with self.async_session() as session:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    code_data = {
                        'code': row['code'].strip().upper(),
                        'description': row['description'].strip(),
                        'level': row.get('level', 'II').strip(),
                        'category': row.get('category', '').strip() or None,
                        'metadata': json.dumps({
                            'import_date': datetime.utcnow().isoformat(),
                            'source': 'CMS'
                        })
                    }
                    
                    batch.append(code_data)
                    
                    if len(batch) >= self.batch_size:
                        await self._insert_batch(session, 'hcpcs_codes', batch)
                        codes_imported += len(batch)
                        logger.info(f"Imported {codes_imported} HCPCS codes...")
                        batch = []
                
                if batch:
                    await self._insert_batch(session, 'hcpcs_codes', batch)
                    codes_imported += len(batch)
                
                await session.commit()
        
        logger.info(f"✅ Imported {codes_imported} HCPCS codes")
        return codes_imported
    
    async def import_medical_necessity_rules(self, csv_path: Path) -> int:
        """
        Import medical necessity rules
        
        Expected CSV format:
        cpt_code,icd10_codes,insurance_type,prior_auth_required,age_min,age_max
        99213,"J00,J01,J02",Medicare,0,18,65
        """
        logger.info(f"Importing medical necessity rules from {csv_path}")
        
        rules_imported = 0
        batch = []
        
        async with self.async_session() as session:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Parse ICD-10 codes (comma-separated in quotes)
                    icd10_codes_str = row['icd10_codes'].strip('"')
                    icd10_codes = [code.strip() for code in icd10_codes_str.split(',')]
                    
                    rule_data = {
                        'cpt_code': row['cpt_code'].strip(),
                        'icd10_codes': '{' + ','.join(icd10_codes) + '}',  # PostgreSQL array format
                        'insurance_type': row.get('insurance_type', '').strip() or None,
                        'prior_auth_required': row.get('prior_auth_required', '0') == '1',
                        'age_min': int(row['age_min']) if row.get('age_min') else None,
                        'age_max': int(row['age_max']) if row.get('age_max') else None,
                        'gender': row.get('gender', '').strip() or None,
                        'frequency_limit': int(row['frequency_limit']) if row.get('frequency_limit') else None,
                        'frequency_period': row.get('frequency_period', '').strip() or None,
                        'metadata': json.dumps({
                            'import_date': datetime.utcnow().isoformat()
                        })
                    }
                    
                    batch.append(rule_data)
                    
                    if len(batch) >= self.batch_size:
                        await self._insert_batch(session, 'medical_necessity_rules', batch)
                        rules_imported += len(batch)
                        logger.info(f"Imported {rules_imported} rules...")
                        batch = []
                
                if batch:
                    await self._insert_batch(session, 'medical_necessity_rules', batch)
                    rules_imported += len(batch)
                
                await session.commit()
        
        logger.info(f"✅ Imported {rules_imported} medical necessity rules")
        return rules_imported
    
    async def _insert_batch(self, session: AsyncSession, table: str, batch: List[Dict]):
        """Insert a batch of records using raw SQL for performance"""
        if not batch:
            return
        
        # Build column list
        columns = list(batch[0].keys())
        columns_str = ', '.join(columns)
        
        # Build values for each row
        values_list = []
        for row in batch:
            values = []
            for col in columns:
                val = row[col]
                if val is None:
                    values.append('NULL')
                elif isinstance(val, bool):
                    values.append('TRUE' if val else 'FALSE')
                elif isinstance(val, (int, float)):
                    values.append(str(val))
                else:
                    # Escape single quotes
                    escaped = str(val).replace("'", "''")
                    values.append(f"'{escaped}'")
            values_list.append(f"({', '.join(values)})")
        
        values_str = ',\n'.join(values_list)
        
        # Execute insert
        query = f"""
            INSERT INTO {table} ({columns_str})
            VALUES {values_str}
            ON CONFLICT DO NOTHING
        """
        
        await session.execute(text(query))
    
    async def verify_import(self) -> Dict[str, Any]:
        """Verify imported codes and return statistics"""
        async with self.async_session() as session:
            stats = {}
            
            # ICD-10 count
            result = await session.execute(text("SELECT COUNT(*) FROM icd10_codes"))
            stats['icd10_count'] = result.scalar()
            
            # CPT count
            result = await session.execute(text("SELECT COUNT(*) FROM cpt_codes"))
            stats['cpt_count'] = result.scalar()
            
            # HCPCS count
            result = await session.execute(text("SELECT COUNT(*) FROM hcpcs_codes"))
            stats['hcpcs_count'] = result.scalar()
            
            # Medical necessity rules count
            result = await session.execute(text("SELECT COUNT(*) FROM medical_necessity_rules"))
            stats['rules_count'] = result.scalar()
            
            stats['total_codes'] = stats['icd10_count'] + stats['cpt_count'] + stats['hcpcs_count']
            
            return stats
    
    async def close(self):
        """Close database connections"""
        await self.engine.dispose()


def create_sample_data():
    """Create sample CSV files for testing"""
    logger.info("Creating sample data files...")
    
    # Create data directory
    data_dir = Path(__file__).parent.parent / 'data' / 'medical_codes'
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Sample ICD-10 codes (expanded)
    icd10_file = data_dir / 'sample_icd10_codes.csv'
    with open(icd10_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['code', 'description', 'category', 'subcategory', 'billable'])
        writer.writeheader()
        writer.writerows([
            {'code': 'A00.0', 'description': 'Cholera due to Vibrio cholerae 01, biovar cholerae', 'category': 'Infectious', 'subcategory': 'Intestinal', 'billable': '1'},
            {'code': 'A00.1', 'description': 'Cholera due to Vibrio cholerae 01, biovar eltor', 'category': 'Infectious', 'subcategory': 'Intestinal', 'billable': '1'},
            {'code': 'E11.9', 'description': 'Type 2 diabetes mellitus without complications', 'category': 'Endocrine', 'subcategory': 'Diabetes', 'billable': '1'},
            {'code': 'I21.9', 'description': 'Acute myocardial infarction, unspecified', 'category': 'Circulatory', 'subcategory': 'Ischemic heart', 'billable': '1'},
            {'code': 'J44.0', 'description': 'COPD with acute lower respiratory infection', 'category': 'Respiratory', 'subcategory': 'COPD', 'billable': '1'},
            {'code': 'N18.3', 'description': 'Chronic kidney disease, stage 3', 'category': 'Genitourinary', 'subcategory': 'Renal', 'billable': '1'},
        ])
    logger.info(f"✅ Created {icd10_file}")
    
    # Sample CPT codes
    cpt_file = data_dir / 'sample_cpt_codes.csv'
    with open(cpt_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['code', 'description', 'category', 'modifier_allowed', 'base_rate', 'rvu'])
        writer.writeheader()
        writer.writerows([
            {'code': '99213', 'description': 'Office visit, established patient, 20-29 minutes', 'category': 'E&M', 'modifier_allowed': '1', 'base_rate': '150.00', 'rvu': '1.5'},
            {'code': '99214', 'description': 'Office visit, established patient, 30-39 minutes', 'category': 'E&M', 'modifier_allowed': '1', 'base_rate': '220.00', 'rvu': '2.5'},
            {'code': '80053', 'description': 'Comprehensive metabolic panel', 'category': 'Laboratory', 'modifier_allowed': '1', 'base_rate': '45.00', 'rvu': '0.5'},
            {'code': '93000', 'description': 'Electrocardiogram, complete', 'category': 'Cardiology', 'modifier_allowed': '1', 'base_rate': '35.00', 'rvu': '0.3'},
        ])
    logger.info(f"✅ Created {cpt_file}")
    
    # Sample medical necessity rules
    rules_file = data_dir / 'sample_medical_necessity_rules.csv'
    with open(rules_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['cpt_code', 'icd10_codes', 'insurance_type', 'prior_auth_required', 'age_min', 'age_max'])
        writer.writeheader()
        writer.writerows([
            {'cpt_code': '99213', 'icd10_codes': '"E11.9,I21.9,J44.0"', 'insurance_type': '', 'prior_auth_required': '0', 'age_min': '', 'age_max': ''},
            {'cpt_code': '80053', 'icd10_codes': '"E11.9,N18.3"', 'insurance_type': '', 'prior_auth_required': '0', 'age_min': '', 'age_max': ''},
            {'cpt_code': '93000', 'icd10_codes': '"I21.9"', 'insurance_type': '', 'prior_auth_required': '0', 'age_min': '', 'age_max': ''},
        ])
    logger.info(f"✅ Created {rules_file}")
    
    logger.info(f"\nSample data files created in: {data_dir}")
    logger.info(f"\nTo import sample data:")
    logger.info(f"  python scripts/import_medical_codes_async.py import-all --sample")
    
    return data_dir


# CLI Commands
if DEPENDENCIES_AVAILABLE:
    @click.group()
    def cli():
        """Medical codes import CLI"""
        pass

    @cli.command()
    @click.option('--icd10-csv', type=click.Path(exists=True), help='ICD-10 CSV file path')
    @click.option('--cpt-csv', type=click.Path(exists=True), help='CPT CSV file path')
    @click.option('--hcpcs-csv', type=click.Path(exists=True), help='HCPCS CSV file path')
    @click.option('--rules-csv', type=click.Path(exists=True), help='Medical necessity rules CSV')
    @click.option('--sample', is_flag=True, help='Use sample data')
    @click.option('--database-url', envvar='DATABASE_URL', help='Database URL')
    def import_all(icd10_csv, cpt_csv, hcpcs_csv, rules_csv, sample, database_url):
        """Import all medical codes from CSV files"""
        async def run_import():
            if not database_url:
                logger.error("DATABASE_URL not set. Use --database-url or set DATABASE_URL environment variable")
                sys.exit(1)
            
            importer = MedicalCodesImporter(database_url)
            
            try:
                if sample:
                    data_dir = create_sample_data()
                    icd10_csv = data_dir / 'sample_icd10_codes.csv'
                    cpt_csv = data_dir / 'sample_cpt_codes.csv'
                    rules_csv = data_dir / 'sample_medical_necessity_rules.csv'
                
                total_imported = 0
                
                if icd10_csv:
                    count = await importer.import_icd10_codes(Path(icd10_csv))
                    total_imported += count
                
                if cpt_csv:
                    count = await importer.import_cpt_codes(Path(cpt_csv))
                    total_imported += count
                
                if hcpcs_csv:
                    count = await importer.import_hcpcs_codes(Path(hcpcs_csv))
                    total_imported += count
                
                if rules_csv:
                    await importer.import_medical_necessity_rules(Path(rules_csv))
                
                # Verify import
                stats = await importer.verify_import()
                
                logger.info("\n" + "="*60)
                logger.info("Import Summary:")
                logger.info(f"  ICD-10 Codes: {stats['icd10_count']:,}")
                logger.info(f"  CPT Codes: {stats['cpt_count']:,}")
                logger.info(f"  HCPCS Codes: {stats['hcpcs_count']:,}")
                logger.info(f"  Total Codes: {stats['total_codes']:,}")
                logger.info(f"  Medical Necessity Rules: {stats['rules_count']:,}")
                logger.info("="*60)
                
                if stats['total_codes'] >= 70000:
                    logger.info("✅ SUCCESS: 70,000+ codes imported!")
                elif stats['total_codes'] > 0:
                    logger.warning(f"⚠️  Warning: Only {stats['total_codes']:,} codes imported (target: 70,000+)")
                    logger.info("To import full database, obtain ICD-10 and CPT code files and run:")
                    logger.info("  python scripts/import_medical_codes_async.py import-all --icd10-csv <file> --cpt-csv <file>")
            
            finally:
                await importer.close()
        
        asyncio.run(run_import())

    @cli.command()
    @click.option('--database-url', envvar='DATABASE_URL', help='Database URL')
    def verify(database_url):
        """Verify imported medical codes"""
        async def run_verify():
            if not database_url:
                logger.error("DATABASE_URL not set")
                sys.exit(1)
            
            importer = MedicalCodesImporter(database_url)
            
            try:
                stats = await importer.verify_import()
                
                print("\n" + "="*60)
                print("Medical Codes Statistics:")
                print(f"  ICD-10 Codes: {stats['icd10_count']:,}")
                print(f"  CPT Codes: {stats['cpt_count']:,}")
                print(f"  HCPCS Codes: {stats['hcpcs_count']:,}")
                print(f"  Total Codes: {stats['total_codes']:,}")
                print(f"  Medical Necessity Rules: {stats['rules_count']:,}")
                print("="*60)
                
                if stats['total_codes'] >= 70000:
                    print("✅ PASS: 70,000+ codes available")
                    sys.exit(0)
                elif stats['total_codes'] > 0:
                    print(f"⚠️  WARNING: Only {stats['total_codes']:,} codes (target: 70,000+)")
                    sys.exit(0)
                else:
                    print("❌ FAIL: No codes imported")
                    sys.exit(1)
            
            finally:
                await importer.close()
        
        asyncio.run(run_verify())

    @cli.command()
    def create_samples():
        """Create sample CSV files for testing"""
        create_sample_data()

    if __name__ == '__main__':
        cli()
else:
    if __name__ == '__main__':
        print("Error: Required dependencies not installed")
        print("Install with: pip install sqlalchemy[asyncio] asyncpg click")
        sys.exit(1)

