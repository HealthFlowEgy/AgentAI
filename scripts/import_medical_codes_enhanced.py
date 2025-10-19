"""
Enhanced Medical Codes Import Script
Imports ICD-10, CPT, HCPCS, Denial Codes, and Payment Codes

Usage:
    python import_medical_codes_enhanced.py --all
    python import_medical_codes_enhanced.py --icd10 path/to/icd10.csv
    python import_medical_codes_enhanced.py --cpt path/to/cpt.csv
"""

import asyncio
import csv
import logging
from pathlib import Path
from typing import List, Dict, Optional
import argparse
from datetime import datetime
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func
import httpx
from tqdm import tqdm

from src.models.medical_codes import (
    ICD10Code,
    CPTCode,
    HCPCSCode,
    DenialCode,
    PaymentCode,
    MedicalNecessityRule
)
from src.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MedicalCodesImporter:
    """Import medical codes from various sources"""
    
    def __init__(self, database_url: str):
        """Initialize importer with database connection"""
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=20,
            max_overflow=0
        )
        self.SessionLocal = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def download_icd10_codes(self, output_path: Path) -> None:
        """Download ICD-10 codes from CDC"""
        logger.info("Downloading ICD-10 codes from CDC...")
        
        # CDC ICD-10 CM codes URL (2024 version)
        url = "https://www.cms.gov/files/zip/2024-code-descriptions-tabular-order.zip"
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Save zip file
                zip_path = output_path / "icd10_2024.zip"
                zip_path.write_bytes(response.content)
                
                # Extract zip
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(output_path)
                
                logger.info(f"✅ Downloaded and extracted ICD-10 codes to {output_path}")
                
        except Exception as e:
            logger.error(f"❌ Failed to download ICD-10 codes: {e}")
            raise
    
    async def import_icd10_codes(self, csv_path: Path) -> int:
        """
        Import ICD-10 codes from CSV
        
        CSV Format:
        code,description,category,subcategory,billable,valid_for_coding
        A00.0,Cholera due to Vibrio cholerae 01 biovar cholerae,Infectious,Intestinal,1,1
        """
        logger.info(f"Importing ICD-10 codes from {csv_path}...")
        
        codes = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in tqdm(reader, desc="Reading ICD-10 codes"):
                codes.append(ICD10Code(
                    code=row['code'].strip(),
                    description=row['description'].strip(),
                    category=row.get('category', '').strip(),
                    subcategory=row.get('subcategory', '').strip(),
                    billable=row.get('billable', '1') == '1',
                    valid_for_coding=row.get('valid_for_coding', '1') == '1',
                    effective_date=datetime.now().date()
                ))
        
        # Batch insert
        async with self.SessionLocal() as session:
            batch_size = 1000
            for i in tqdm(range(0, len(codes), batch_size), desc="Importing ICD-10"):
                batch = codes[i:i + batch_size]
                session.add_all(batch)
                await session.commit()
        
        logger.info(f"✅ Imported {len(codes)} ICD-10 codes")
        return len(codes)
    
    async def import_cpt_codes(self, csv_path: Path) -> int:
        """
        Import CPT codes from CSV
        
        CSV Format:
        code,description,category,rvu,facility_rvu,non_facility_rvu
        99213,Office visit established patient,E/M,1.92,1.92,1.92
        """
        logger.info(f"Importing CPT codes from {csv_path}...")
        
        codes = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in tqdm(reader, desc="Reading CPT codes"):
                codes.append(CPTCode(
                    code=row['code'].strip(),
                    description=row['description'].strip(),
                    category=row.get('category', '').strip(),
                    rvu=float(row.get('rvu', 0)),
                    facility_rvu=float(row.get('facility_rvu', 0)),
                    non_facility_rvu=float(row.get('non_facility_rvu', 0)),
                    effective_date=datetime.now().date()
                ))
        
        # Batch insert
        async with self.SessionLocal() as session:
            batch_size = 1000
            for i in tqdm(range(0, len(codes), batch_size), desc="Importing CPT"):
                batch = codes[i:i + batch_size]
                session.add_all(batch)
                await session.commit()
        
        logger.info(f"✅ Imported {len(codes)} CPT codes")
        return len(codes)
    
    async def import_hcpcs_codes(self, csv_path: Path) -> int:
        """Import HCPCS codes (free alternative to CPT)"""
        logger.info(f"Importing HCPCS codes from {csv_path}...")
        
        codes = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in tqdm(reader, desc="Reading HCPCS codes"):
                codes.append(HCPCSCode(
                    code=row['code'].strip(),
                    description=row['description'].strip(),
                    category=row.get('category', '').strip(),
                    effective_date=datetime.now().date()
                ))
        
        async with self.SessionLocal() as session:
            batch_size = 1000
            for i in tqdm(range(0, len(codes), batch_size), desc="Importing HCPCS"):
                batch = codes[i:i + batch_size]
                session.add_all(batch)
                await session.commit()
        
        logger.info(f"✅ Imported {len(codes)} HCPCS codes")
        return len(codes)
    
    async def import_denial_codes(self) -> int:
        """Import standard denial codes"""
        logger.info("Importing denial codes...")
        
        denial_codes = [
            {
                'code': 'CO-16',
                'description': 'Claim/service lacks information or has submission/billing error(s)',
                'category': 'Billing Error',
                'resolution': 'Review claim for missing information and resubmit'
            },
            {
                'code': 'CO-18',
                'description': 'Exact duplicate claim/service',
                'category': 'Duplicate',
                'resolution': 'Verify if duplicate, if not provide proof of separate service'
            },
            {
                'code': 'CO-22',
                'description': 'This care may be covered by another payer',
                'category': 'Coordination of Benefits',
                'resolution': 'Verify primary payer and coordinate benefits'
            },
            {
                'code': 'CO-27',
                'description': 'Expenses incurred after coverage terminated',
                'category': 'Eligibility',
                'resolution': 'Verify coverage dates and appeal if service was within coverage period'
            },
            {
                'code': 'CO-29',
                'description': 'The time limit for filing has expired',
                'category': 'Timely Filing',
                'resolution': 'Provide documentation of timely filing or extenuating circumstances'
            },
            {
                'code': 'CO-50',
                'description': 'Non-covered services',
                'category': 'Medical Necessity',
                'resolution': 'Provide medical necessity documentation or appeal'
            },
            {
                'code': 'CO-96',
                'description': 'Non-covered charges',
                'category': 'Non-Covered Service',
                'resolution': 'Review contract for covered services'
            },
            {
                'code': 'CO-97',
                'description': 'Payment adjusted because the benefit for this service is included in another service',
                'category': 'Bundling',
                'resolution': 'Review bundling rules and appeal if services are separately billable'
            },
            {
                'code': 'CO-151',
                'description': 'Payment adjusted because the payer deems the information submitted does not support this many/frequency of services',
                'category': 'Medical Necessity',
                'resolution': 'Provide additional documentation supporting frequency'
            },
            {
                'code': 'CO-197',
                'description': 'Precertification/authorization/notification absent',
                'category': 'Authorization',
                'resolution': 'Obtain retroactive authorization if possible'
            },
            {
                'code': 'PR-1',
                'description': 'Deductible amount',
                'category': 'Patient Responsibility',
                'resolution': 'Bill patient for deductible amount'
            },
            {
                'code': 'PR-2',
                'description': 'Coinsurance amount',
                'category': 'Patient Responsibility',
                'resolution': 'Bill patient for coinsurance amount'
            },
            {
                'code': 'PR-3',
                'description': 'Co-payment amount',
                'category': 'Patient Responsibility',
                'resolution': 'Collect copay from patient'
            },
        ]
        
        codes = [DenialCode(**dc) for dc in denial_codes]
        
        async with self.SessionLocal() as session:
            session.add_all(codes)
            await session.commit()
        
        logger.info(f"✅ Imported {len(codes)} denial codes")
        return len(codes)
    
    async def import_payment_codes(self) -> int:
        """Import CARC/RARC payment adjustment codes"""
        logger.info("Importing payment adjustment codes...")
        
        payment_codes = [
            {
                'code': 'CARC-1',
                'description': 'Deductible Amount',
                'category': 'Patient Responsibility',
                'adjustment_type': 'deductible'
            },
            {
                'code': 'CARC-2',
                'description': 'Coinsurance Amount',
                'category': 'Patient Responsibility',
                'adjustment_type': 'coinsurance'
            },
            {
                'code': 'CARC-3',
                'description': 'Co-payment Amount',
                'category': 'Patient Responsibility',
                'adjustment_type': 'copay'
            },
            {
                'code': 'CARC-45',
                'description': 'Charge exceeds fee schedule/maximum allowable',
                'category': 'Contractual Adjustment',
                'adjustment_type': 'contractual'
            },
            {
                'code': 'CARC-96',
                'description': 'Non-covered charge(s)',
                'category': 'Non-Covered',
                'adjustment_type': 'non_covered'
            },
        ]
        
        codes = [PaymentCode(**pc) for pc in payment_codes]
        
        async with self.SessionLocal() as session:
            session.add_all(codes)
            await session.commit()
        
        logger.info(f"✅ Imported {len(codes)} payment codes")
        return len(codes)
    
    async def create_medical_necessity_rules(self) -> int:
        """Create sample medical necessity rules (ICD-10 to CPT mapping)"""
        logger.info("Creating medical necessity rules...")
        
        rules = [
            {
                'icd10_code': 'E11.9',  # Type 2 diabetes
                'cpt_codes': ['99213', '99214', '82947', '82950'],  # Office visits, glucose tests
                'description': 'Type 2 diabetes management',
                'effective_date': datetime.now().date()
            },
            {
                'icd10_code': 'I10',  # Essential hypertension
                'cpt_codes': ['99213', '99214', '93000'],  # Office visits, ECG
                'description': 'Hypertension management',
                'effective_date': datetime.now().date()
            },
            {
                'icd10_code': 'J45.909',  # Unspecified asthma
                'cpt_codes': ['99213', '99214', '94010', '94060'],  # Office visits, pulmonary function tests
                'description': 'Asthma management',
                'effective_date': datetime.now().date()
            },
        ]
        
        rule_objects = [MedicalNecessityRule(**rule) for rule in rules]
        
        async with self.SessionLocal() as session:
            session.add_all(rule_objects)
            await session.commit()
        
        logger.info(f"✅ Created {len(rules)} medical necessity rules")
        return len(rules)
    
    async def verify_import(self) -> Dict[str, int]:
        """Verify imported data counts"""
        logger.info("Verifying imported data...")
        
        async with self.SessionLocal() as session:
            counts = {}
            
            # Count ICD-10 codes
            result = await session.execute(select(func.count(ICD10Code.id)))
            counts['icd10'] = result.scalar()
            
            # Count CPT codes
            result = await session.execute(select(func.count(CPTCode.id)))
            counts['cpt'] = result.scalar()
            
            # Count HCPCS codes
            result = await session.execute(select(func.count(HCPCSCode.id)))
            counts['hcpcs'] = result.scalar()
            
            # Count denial codes
            result = await session.execute(select(func.count(DenialCode.id)))
            counts['denial'] = result.scalar()
            
            # Count payment codes
            result = await session.execute(select(func.count(PaymentCode.id)))
            counts['payment'] = result.scalar()
            
            # Count medical necessity rules
            result = await session.execute(select(func.count(MedicalNecessityRule.id)))
            counts['rules'] = result.scalar()
        
        logger.info("📊 Import Verification:")
        logger.info(f"  ICD-10 Codes: {counts['icd10']:,}")
        logger.info(f"  CPT Codes: {counts['cpt']:,}")
        logger.info(f"  HCPCS Codes: {counts['hcpcs']:,}")
        logger.info(f"  Denial Codes: {counts['denial']}")
        logger.info(f"  Payment Codes: {counts['payment']}")
        logger.info(f"  Medical Necessity Rules: {counts['rules']}")
        
        return counts
    
    async def test_search_performance(self) -> None:
        """Test search performance"""
        logger.info("Testing search performance...")
        
        test_queries = ['diabetes', 'hypertension', 'office visit', 'glucose']
        
        async with self.SessionLocal() as session:
            for query in test_queries:
                start = datetime.now()
                
                # Test ICD-10 search
                stmt = select(ICD10Code).where(
                    ICD10Code.description.ilike(f'%{query}%')
                ).limit(10)
                result = await session.execute(stmt)
                codes = result.scalars().all()
                
                elapsed = (datetime.now() - start).total_seconds() * 1000
                
                logger.info(f"  Query '{query}': {len(codes)} results in {elapsed:.2f}ms")
                
                if elapsed > 100:
                    logger.warning(f"    ⚠️ Search took longer than 100ms target")
                else:
                    logger.info(f"    ✅ Search performance acceptable")


async def main():
    """Main import function"""
    parser = argparse.ArgumentParser(description='Import medical codes')
    parser.add_argument('--all', action='store_true', help='Import all codes')
    parser.add_argument('--icd10', type=str, help='Path to ICD-10 CSV')
    parser.add_argument('--cpt', type=str, help='Path to CPT CSV')
    parser.add_argument('--hcpcs', type=str, help='Path to HCPCS CSV')
    parser.add_argument('--download-icd10', action='store_true', help='Download ICD-10 codes from CDC')
    parser.add_argument('--verify', action='store_true', help='Verify imported data')
    parser.add_argument('--test-performance', action='store_true', help='Test search performance')
    
    args = parser.parse_args()
    
    # Get database URL from settings
    database_url = settings.database_url.replace('postgresql://', 'postgresql+asyncpg://')
    
    importer = MedicalCodesImporter(database_url)
    
    try:
        if args.download_icd10:
            data_dir = Path(__file__).parent.parent / 'data'
            data_dir.mkdir(exist_ok=True)
            await importer.download_icd10_codes(data_dir)
        
        if args.icd10:
            await importer.import_icd10_codes(Path(args.icd10))
        
        if args.cpt:
            await importer.import_cpt_codes(Path(args.cpt))
        
        if args.hcpcs:
            await importer.import_hcpcs_codes(Path(args.hcpcs))
        
        if args.all:
            # Import standard codes
            await importer.import_denial_codes()
            await importer.import_payment_codes()
            await importer.create_medical_necessity_rules()
        
        if args.verify or args.all:
            counts = await importer.verify_import()
            
            # Check if targets met
            if counts['icd10'] < 70000:
                logger.warning(f"⚠️ ICD-10 count ({counts['icd10']}) below target (70,000)")
            if counts['cpt'] < 10000 and counts['hcpcs'] < 10000:
                logger.warning(f"⚠️ CPT/HCPCS count below target (10,000)")
        
        if args.test_performance:
            await importer.test_search_performance()
        
        logger.info("✅ Import complete!")
        
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        raise
    finally:
        await importer.engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
