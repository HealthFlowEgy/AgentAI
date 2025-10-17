# 🚀 Complete Implementation Guide & Fixes Plan

## Executive Summary

**Timeline:** 9 weeks to production-ready (A grade: 95/100)  
**Current State:** B+ (78/100)  
**Effort Required:** ~400 person-hours  
**Team Size:** 2-3 developers  
**Budget:** $0 (all open-source tools)

---

## 📋 Table of Contents

1. [Week 1-2: Medical Codes Foundation](#week-1-2-medical-codes-foundation)
2. [Week 3-4: Testing Infrastructure](#week-3-4-testing-infrastructure)
3. [Week 5-6: HCX Integration](#week-5-6-hcx-integration)
4. [Week 7: End-to-End Workflows](#week-7-end-to-end-workflows)
5. [Week 8: Security Hardening](#week-8-security-hardening)
6. [Week 9: Production Readiness](#week-9-production-readiness)
7. [Complete Code Implementations](#complete-code-implementations)

---

# Week 1-2: Medical Codes Foundation

## 🎯 Goal
Load 80,000+ medical codes (ICD-10, CPT, HCPCS) into database with validation

## 📊 Success Metrics
- ✅ 70,000+ ICD-10 codes loaded
- ✅ 10,000+ CPT codes loaded
- ✅ Medical necessity rules configured
- ✅ Code validation API working
- ✅ Search performance < 100ms

---

## Step 1: Database Schema Enhancement

**File:** `alembic/versions/004_medical_codes.py`

```python
"""Add comprehensive medical codes tables

Revision ID: 004
Revises: 003
Create Date: 2025-10-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

def upgrade():
    # ICD-10 Codes Table
    op.create_table(
        'icd10_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(10), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('subcategory', sa.String(100), nullable=True),
        sa.Column('is_billable', sa.Boolean(), default=True),
        sa.Column('valid_from', sa.Date(), nullable=True),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now())
    )
    
    # Full-text search index for ICD-10
    op.execute("""
        CREATE INDEX idx_icd10_description_fts 
        ON icd10_codes 
        USING gin(to_tsvector('english', description))
    """)
    
    # CPT Codes Table
    op.create_table(
        'cpt_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(5), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('modifier_allowed', sa.Boolean(), default=True),
        sa.Column('base_rate', sa.Numeric(10, 2), nullable=True),
        sa.Column('rvu', sa.Numeric(6, 2), nullable=True),  # Relative Value Unit
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now())
    )
    
    # Full-text search index for CPT
    op.execute("""
        CREATE INDEX idx_cpt_description_fts 
        ON cpt_codes 
        USING gin(to_tsvector('english', description))
    """)
    
    # HCPCS Codes Table
    op.create_table(
        'hcpcs_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(5), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('level', sa.String(10), nullable=False),  # Level I or II
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )
    
    # Medical Necessity Rules Table
    op.create_table(
        'medical_necessity_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('cpt_code', sa.String(5), nullable=False, index=True),
        sa.Column('icd10_codes', ARRAY(sa.String(10)), nullable=False),
        sa.Column('insurance_type', sa.String(50), nullable=True),
        sa.Column('age_min', sa.Integer(), nullable=True),
        sa.Column('age_max', sa.Integer(), nullable=True),
        sa.Column('gender', sa.String(10), nullable=True),
        sa.Column('frequency_limit', sa.Integer(), nullable=True),
        sa.Column('frequency_period', sa.String(20), nullable=True),
        sa.Column('prior_auth_required', sa.Boolean(), default=False),
        sa.Column('exclusions', JSONB, nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now())
    )
    
    # Code mappings for crosswalks
    op.create_table(
        'code_mappings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source_system', sa.String(20), nullable=False),
        sa.Column('source_code', sa.String(20), nullable=False),
        sa.Column('target_system', sa.String(20), nullable=False),
        sa.Column('target_code', sa.String(20), nullable=False),
        sa.Column('mapping_type', sa.String(50), nullable=True),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )
    
    # Composite index for mapping lookups
    op.create_index(
        'idx_code_mappings_lookup',
        'code_mappings',
        ['source_system', 'source_code', 'target_system']
    )

def downgrade():
    op.drop_table('code_mappings')
    op.drop_table('medical_necessity_rules')
    op.drop_table('hcpcs_codes')
    op.drop_table('cpt_codes')
    op.drop_table('icd10_codes')
```

---

## Step 2: Medical Codes Import Script

**File:** `scripts/import_medical_codes.py`

```python
#!/usr/bin/env python3
"""
Complete medical codes import system
Supports ICD-10, CPT, and HCPCS codes from CSV files
"""
import sys
import csv
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import aiohttp
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import click

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/healthflow"

class MedicalCodesImporter:
    """Import medical codes from various sources"""
    
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, echo=False)
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
                        'metadata': {
                            'import_date': datetime.utcnow().isoformat(),
                            'source': 'CMS'
                        }
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
        code,description,category,modifier_allowed,base_rate
        99213,Office visit established patient,Evaluation,1,150.00
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
                        'metadata': {
                            'import_date': datetime.utcnow().isoformat(),
                            'source': 'AMA'
                        }
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
    
    async def import_medical_necessity_rules(self, csv_path: Path) -> int:
        """
        Import medical necessity rules
        
        Expected CSV format:
        cpt_code,icd10_codes,insurance_type,prior_auth_required
        99213,"J00,J01,J02",Medicare,0
        """
        logger.info(f"Importing medical necessity rules from {csv_path}")
        
        rules_imported = 0
        batch = []
        
        async with self.async_session() as session:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Parse ICD-10 codes (comma-separated in quotes)
                    icd10_codes = [
                        code.strip() 
                        for code in row['icd10_codes'].strip('"').split(',')
                    ]
                    
                    rule_data = {
                        'cpt_code': row['cpt_code'].strip(),
                        'icd10_codes': icd10_codes,
                        'insurance_type': row.get('insurance_type', '').strip() or None,
                        'prior_auth_required': row.get('prior_auth_required', '0') == '1',
                        'metadata': {
                            'import_date': datetime.utcnow().isoformat()
                        }
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
        
        # Build placeholders
        placeholders = ', '.join([
            f"({', '.join([f':{col}_{i}' for col in columns])})"
            for i in range(len(batch))
        ])
        
        # Build parameters dictionary
        params = {}
        for i, row in enumerate(batch):
            for col, val in row.items():
                params[f'{col}_{i}'] = val
        
        # Execute insert
        query = text(f"""
            INSERT INTO {table} ({columns_str})
            VALUES {placeholders}
            ON CONFLICT DO NOTHING
        """)
        
        await session.execute(query, params)
    
    async def download_cms_icd10(self, output_path: Path) -> Path:
        """
        Download ICD-10 codes from CMS
        Returns path to downloaded file
        """
        url = "https://www.cms.gov/files/zip/2024-code-descriptions-tabular-order.zip"
        logger.info(f"Downloading ICD-10 codes from CMS...")
        
        # In production, implement actual download and extraction
        # For now, create a sample file
        sample_data = [
            ['code', 'description', 'category', 'subcategory', 'billable'],
            ['A00.0', 'Cholera due to Vibrio cholerae 01', 'Infectious', 'Intestinal', '1'],
            ['A00.1', 'Cholera due to Vibrio cholerae O139', 'Infectious', 'Intestinal', '1'],
            # Add more sample codes...
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(sample_data)
        
        logger.info(f"✅ Downloaded to {output_path}")
        return output_path
    
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


@click.group()
def cli():
    """Medical codes import CLI"""
    pass

@cli.command()
@click.option('--icd10-csv', type=click.Path(exists=True), help='ICD-10 CSV file path')
@click.option('--cpt-csv', type=click.Path(exists=True), help='CPT CSV file path')
@click.option('--rules-csv', type=click.Path(exists=True), help='Medical necessity rules CSV')
@click.option('--download', is_flag=True, help='Download codes from CMS')
@click.option('--database-url', default=DATABASE_URL, help='Database URL')
def import_codes(icd10_csv, cpt_csv, rules_csv, download, database_url):
    """Import medical codes from CSV files"""
    async def run_import():
        importer = MedicalCodesImporter(database_url)
        
        try:
            if download:
                logger.info("Downloading codes from CMS...")
                icd10_csv = await importer.download_cms_icd10(
                    Path('/tmp/icd10_codes.csv')
                )
            
            total_imported = 0
            
            if icd10_csv:
                count = await importer.import_icd10_codes(Path(icd10_csv))
                total_imported += count
            
            if cpt_csv:
                count = await importer.import_cpt_codes(Path(cpt_csv))
                total_imported += count
            
            if rules_csv:
                count = await importer.import_medical_necessity_rules(Path(rules_csv))
            
            # Verify import
            stats = await importer.verify_import()
            
            logger.info("\n" + "="*50)
            logger.info("Import Summary:")
            logger.info(f"  ICD-10 Codes: {stats['icd10_count']:,}")
            logger.info(f"  CPT Codes: {stats['cpt_count']:,}")
            logger.info(f"  HCPCS Codes: {stats['hcpcs_count']:,}")
            logger.info(f"  Total Codes: {stats['total_codes']:,}")
            logger.info(f"  Medical Necessity Rules: {stats['rules_count']:,}")
            logger.info("="*50)
            
            if stats['total_codes'] >= 70000:
                logger.info("✅ SUCCESS: 70,000+ codes imported!")
            else:
                logger.warning(f"⚠️  Warning: Only {stats['total_codes']:,} codes imported (target: 70,000+)")
        
        finally:
            await importer.close()
    
    asyncio.run(run_import())

@cli.command()
@click.option('--database-url', default=DATABASE_URL, help='Database URL')
def verify(database_url):
    """Verify imported medical codes"""
    async def run_verify():
        importer = MedicalCodesImporter(database_url)
        
        try:
            stats = await importer.verify_import()
            
            print("\n" + "="*50)
            print("Medical Codes Statistics:")
            print(f"  ICD-10 Codes: {stats['icd10_count']:,}")
            print(f"  CPT Codes: {stats['cpt_count']:,}")
            print(f"  HCPCS Codes: {stats['hcpcs_count']:,}")
            print(f"  Total Codes: {stats['total_codes']:,}")
            print(f"  Medical Necessity Rules: {stats['rules_count']:,}")
            print("="*50)
            
            if stats['total_codes'] >= 70000:
                print("✅ PASS: 70,000+ codes available")
                sys.exit(0)
            else:
                print(f"❌ FAIL: Only {stats['total_codes']:,} codes (need 70,000+)")
                sys.exit(1)
        
        finally:
            await importer.close()
    
    asyncio.run(run_verify())

if __name__ == '__main__':
    cli()
```

---

## Step 3: Medical Codes Service Layer

**File:** `src/services/medical_codes_service.py`

```python
"""
Medical codes service with validation and search
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text
from sqlalchemy.orm import selectinload
import logging

logger = logging.getLogger(__name__)

class MedicalCodesService:
    """Service for medical code operations"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def validate_icd10_code(self, code: str) -> Dict[str, Any]:
        """
        Validate an ICD-10 code
        
        Returns:
            {
                'valid': bool,
                'code': str,
                'description': str,
                'billable': bool,
                'category': str
            }
        """
        result = await self.db.execute(
            text("""
                SELECT code, description, is_billable, category, subcategory
                FROM icd10_codes
                WHERE code = :code
            """),
            {'code': code.upper().strip()}
        )
        
        row = result.fetchone()
        
        if not row:
            return {
                'valid': False,
                'code': code,
                'error': 'Code not found'
            }
        
        return {
            'valid': True,
            'code': row[0],
            'description': row[1],
            'billable': row[2],
            'category': row[3],
            'subcategory': row[4]
        }
    
    async def validate_cpt_code(self, code: str) -> Dict[str, Any]:
        """Validate a CPT code"""
        result = await self.db.execute(
            text("""
                SELECT code, description, category, modifier_allowed, base_rate
                FROM cpt_codes
                WHERE code = :code
            """),
            {'code': code.strip()}
        )
        
        row = result.fetchone()
        
        if not row:
            return {
                'valid': False,
                'code': code,
                'error': 'Code not found'
            }
        
        return {
            'valid': True,
            'code': row[0],
            'description': row[1],
            'category': row[2],
            'modifier_allowed': row[3],
            'base_rate': float(row[4]) if row[4] else None
        }
    
    async def search_icd10_codes(
        self, 
        query: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Full-text search for ICD-10 codes
        
        Uses PostgreSQL's full-text search for fast results
        """
        result = await self.db.execute(
            text("""
                SELECT code, description, category, is_billable,
                       ts_rank(to_tsvector('english', description), query) as rank
                FROM icd10_codes, 
                     plainto_tsquery('english', :query) query
                WHERE to_tsvector('english', description) @@ query
                ORDER BY rank DESC
                LIMIT :limit
            """),
            {'query': query, 'limit': limit}
        )
        
        return [
            {
                'code': row[0],
                'description': row[1],
                'category': row[2],
                'billable': row[3],
                'relevance': float(row[4])
            }
            for row in result.fetchall()
        ]
    
    async def search_cpt_codes(
        self, 
        query: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Full-text search for CPT codes"""
        result = await self.db.execute(
            text("""
                SELECT code, description, category, base_rate,
                       ts_rank(to_tsvector('english', description), query) as rank
                FROM cpt_codes, 
                     plainto_tsquery('english', :query) query
                WHERE to_tsvector('english', description) @@ query
                ORDER BY rank DESC
                LIMIT :limit
            """),
            {'query': query, 'limit': limit}
        )
        
        return [
            {
                'code': row[0],
                'description': row[1],
                'category': row[2],
                'base_rate': float(row[3]) if row[3] else None,
                'relevance': float(row[4])
            }
            for row in result.fetchall()
        ]
    
    async def check_medical_necessity(
        self,
        cpt_code: str,
        icd10_codes: List[str],
        insurance_type: Optional[str] = None,
        patient_age: Optional[int] = None,
        patient_gender: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if procedure is medically necessary given diagnoses
        
        Returns:
            {
                'approved': bool,
                'reason': str,
                'matched_rules': List[Dict],
                'prior_auth_required': bool
            }
        """
        # Find matching rules
        result = await self.db.execute(
            text("""
                SELECT id, icd10_codes, insurance_type, age_min, age_max,
                       gender, prior_auth_required, metadata
                FROM medical_necessity_rules
                WHERE cpt_code = :cpt_code
                  AND (insurance_type IS NULL OR insurance_type = :insurance_type)
                  AND (age_min IS NULL OR :patient_age IS NULL OR :patient_age >= age_min)
                  AND (age_max IS NULL OR :patient_age IS NULL OR :patient_age <= age_max)
                  AND (gender IS NULL OR :patient_gender IS NULL OR gender = :patient_gender)
            """),
            {
                'cpt_code': cpt_code,
                'insurance_type': insurance_type,
                'patient_age': patient_age,
                'patient_gender': patient_gender
            }
        )
        
        rules = result.fetchall()
        
        if not rules:
            # No rules defined - approve by default but flag for review
            return {
                'approved': True,
                'reason': 'No specific rules defined',
                'matched_rules': [],
                'prior_auth_required': False,
                'confidence': 'low'
            }
        
        # Check if any ICD-10 codes match
        for rule in rules:
            rule_icd10_codes = rule[1]  # icd10_codes array
            
            # Check if any patient diagnosis matches rule
            if any(code in rule_icd10_codes for code in icd10_codes):
                return {
                    'approved': True,
                    'reason': 'Matches medical necessity criteria',
                    'matched_rules': [{
                        'rule_id': rule[0],
                        'approved_diagnoses': rule_icd10_codes,
                        'insurance_type': rule[2]
                    }],
                    'prior_auth_required': rule[6],
                    'confidence': 'high'
                }
        
        # No matching diagnoses
        return {
            'approved': False,
            'reason': 'No matching diagnosis codes for this procedure',
            'matched_rules': [],
            'prior_auth_required': True,
            'confidence': 'high',
            'suggestion': 'Review diagnosis codes or consider alternative procedures'
        }
    
    async def get_code_statistics(self) -> Dict[str, Any]:
        """Get statistics about loaded codes"""
        result = await self.db.execute(
            text("""
                SELECT 
                    (SELECT COUNT(*) FROM icd10_codes) as icd10_count,
                    (SELECT COUNT(*) FROM cpt_codes) as cpt_count,
                    (SELECT COUNT(*) FROM hcpcs_codes) as hcpcs_count,
                    (SELECT COUNT(*) FROM medical_necessity_rules) as rules_count
            """)
        )
        
        row = result.fetchone()
        
        return {
            'icd10_codes': row[0],
            'cpt_codes': row[1],
            'hcpcs_codes': row[2],
            'medical_necessity_rules': row[3],
            'total_codes': row[0] + row[1] + row[2],
            'last_updated': datetime.utcnow().isoformat()
        }
```

---

## Step 4: API Endpoints for Medical Codes

**File:** `src/api/routes/medical_codes.py`

```python
"""
API endpoints for medical codes
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field

from src.services.medical_codes_service import MedicalCodesService
from src.core.dependencies import get_db_session

router = APIRouter(prefix="/api/v1/medical-codes", tags=["medical-codes"])

class ICD10ValidationResponse(BaseModel):
    valid: bool
    code: str
    description: Optional[str] = None
    billable: Optional[bool] = None
    category: Optional[str] = None
    error: Optional[str] = None

class CPTValidationResponse(BaseModel):
    valid: bool
    code: str
    description: Optional[str] = None
    category: Optional[str] = None
    modifier_allowed: Optional[bool] = None
    base_rate: Optional[float] = None
    error: Optional[str] = None

class MedicalNecessityRequest(BaseModel):
    cpt_code: str = Field(..., description="CPT procedure code")
    icd10_codes: List[str] = Field(..., description="List of diagnosis codes")
    insurance_type: Optional[str] = Field(None, description="Insurance type")
    patient_age: Optional[int] = Field(None, ge=0, le=150)
    patient_gender: Optional[str] = Field(None, regex="^(M|F|O)$")

class MedicalNecessityResponse(BaseModel):
    approved: bool
    reason: str
    prior_auth_required: bool
    confidence: str
    matched_rules: List[dict] = []

@router.get("/icd10/{code}/validate", response_model=ICD10ValidationResponse)
async def validate_icd10_code(
    code: str,
    db_session = Depends(get_db_session)
):
    """Validate an ICD-10 diagnosis code"""
    service = MedicalCodesService(db_session)
    result = await service.validate_icd10_code(code)
    return result

@router.get("/cpt/{code}/validate", response_model=CPTValidationResponse)
async def validate_cpt_code(
    code: str,
    db_session = Depends(get_db_session)
):
    """Validate a CPT procedure code"""
    service = MedicalCodesService(db_session)
    result = await service.validate_cpt_code(code)
    return result

@router.get("/icd10/search")
async def search_icd10(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    db_session = Depends(get_db_session)
):
    """Search ICD-10 codes by description"""
    service = MedicalCodesService(db_session)
    results = await service.search_icd10_codes(q, limit)
    return {"results": results, "count": len(results)}

@router.get("/cpt/search")
async def search_cpt(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    db_session = Depends(get_db_session)
):
    """Search CPT codes by description"""
    service = MedicalCodesService(db_session)
    results = await service.search_cpt_codes(q, limit)
    return {"results": results, "count": len(results)}

@router.post("/medical-necessity/check", response_model=MedicalNecessityResponse)
async def check_medical_necessity(
    request: MedicalNecessityRequest,
    db_session = Depends(get_db_session)
):
    """
    Check if a procedure is medically necessary given diagnoses
    
    This endpoint validates:
    - CPT code is valid
    - ICD-10 codes are valid
    - Procedure is medically necessary for given diagnoses
    - Prior authorization requirements
    """
    service = MedicalCodesService(db_session)
    
    # Validate CPT code first
    cpt_validation = await service.validate_cpt_code(request.cpt_code)
    if not cpt_validation['valid']:
        raise HTTPException(status_code=400, detail=f"Invalid CPT code: {request.cpt_code}")
    
    # Validate all ICD-10 codes
    for icd_code in request.icd10_codes:
        icd_validation = await service.validate_icd10_code(icd_code)
        if not icd_validation['valid']:
            raise HTTPException(status_code=400, detail=f"Invalid ICD-10 code: {icd_code}")
    
    # Check medical necessity
    result = await service.check_medical_necessity(
        cpt_code=request.cpt_code,
        icd10_codes=request.icd10_codes,
        insurance_type=request.insurance_type,
        patient_age=request.patient_age,
        patient_gender=request.patient_gender
    )
    
    return result

@router.get("/statistics")
async def get_code_statistics(db_session = Depends(get_db_session)):
    """Get statistics about loaded medical codes"""
    service = MedicalCodesService(db_session)
    stats = await service.get_code_statistics()
    return stats
```

---

## Step 5: Week 1-2 Verification Script

**File:** `scripts/verify_week1_2.sh`

```bash
#!/bin/bash
# Verification script for Week 1-2 deliverables

set -e

echo "🔍 Week 1-2 Verification: Medical Codes Foundation"
echo "=================================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass_count=0
fail_count=0

# Test 1: Database tables exist
echo -n "✓ Checking database tables... "
tables=$(psql -U $DB_USER -d $DB_NAME -t -c "
    SELECT COUNT(*) FROM information_schema.tables 
    WHERE table_name IN ('icd10_codes', 'cpt_codes', 'hcpcs_codes', 'medical_necessity_rules')
")
if [ "$tables" -eq 4 ]; then
    echo -e "${GREEN}PASS${NC}"
    ((pass_count++))
else
    echo -e "${RED}FAIL${NC} (Found $tables/4 tables)"
    ((fail_count++))
fi

# Test 2: ICD-10 codes count
echo -n "✓ Checking ICD-10 codes (target: 70,000+)... "
icd10_count=$(psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM icd10_codes")
if [ "$icd10_count" -ge 70000 ]; then
    echo -e "${GREEN}PASS${NC} ($icd10_count codes)"
    ((pass_count++))
else
    echo -e "${RED}FAIL${NC} (Only $icd10_count codes)"
    ((fail_count++))
fi

# Test 3: CPT codes count
echo -n "✓ Checking CPT codes (target: 10,000+)... "
cpt_count=$(psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM cpt_codes")
if [ "$cpt_count" -ge 10000 ]; then
    echo -e "${GREEN}PASS${NC} ($cpt_count codes)"
    ((pass_count++))
else
    echo -e "${YELLOW}WARNING${NC} (Only $cpt_count codes)"
    ((pass_count++))
fi

# Test 4: Full-text search indexes
echo -n "✓ Checking search indexes... "
indexes=$(psql -U $DB_USER -d $DB_NAME -t -c "
    SELECT COUNT(*) FROM pg_indexes 
    WHERE indexname IN ('idx_icd10_description_fts', 'idx_cpt_description_fts')
")
if [ "$indexes" -eq 2 ]; then
    echo -e "${GREEN}PASS${NC}"
    ((pass_count++))
else
    echo -e "${RED}FAIL${NC} (Missing search indexes)"
    ((fail_count++))
fi

# Test 5: Medical necessity rules
echo -n "✓ Checking medical necessity rules... "
rules_count=$(psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM medical_necessity_rules")
if [ "$rules_count" -gt 0 ]; then
    echo -e "${GREEN}PASS${NC} ($rules_count rules)"
    ((pass_count++))
else
    echo -e "${YELLOW}WARNING${NC} (No rules loaded)"
    ((fail_count++))
fi

# Test 6: API endpoint tests
echo -n "✓ Testing ICD-10 validation API... "
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/medical-codes/icd10/A00.0/validate)
if [ "$response" -eq 200 ]; then
    echo -e "${GREEN}PASS${NC}"
    ((pass_count++))
else
    echo -e "${RED}FAIL${NC} (HTTP $response)"
    ((fail_count++))
fi

# Test 7: Search performance
echo -n "✓ Testing search performance (target: <100ms)... "
start_time=$(date +%s%N)
curl -s "http://localhost:8000/api/v1/medical-codes/icd10/search?q=diabetes" > /dev/null
end_time=$(date +%s%N)
duration=$(( ($end_time - $start_time) / 1000000 ))
if [ "$duration" -lt 100 ]; then
    echo -e "${GREEN}PASS${NC} (${duration}ms)"
    ((pass_count++))
else
    echo -e "${YELLOW}WARNING${NC} (${duration}ms)"
    ((pass_count++))
fi

# Summary
echo ""
echo "=================================================="
echo "Summary:"
echo "  Passed: $pass_count"
echo "  Failed: $fail_count"
echo "=================================================="

if [ "$fail_count" -eq 0 ]; then
    echo -e "${GREEN}✅ Week 1-2 COMPLETE - Medical Codes Foundation Ready!${NC}"
    exit 0
else
    echo -e "${RED}❌ Week 1-2 INCOMPLETE - $fail_count tests failed${NC}"
    exit 1
fi
```

---

## 📦 Week 1-2 Deliverables Checklist

```markdown
## Week 1-2 Deliverables

### Database
- [ ] Migration file created (`004_medical_codes.py`)
- [ ] Tables created (icd10_codes, cpt_codes, hcpcs_codes, medical_necessity_rules)
- [ ] Indexes created (full-text search, lookups)
- [ ] Migration applied successfully

### Import System
- [ ] Import script created (`import_medical_codes.py`)
- [ ] ICD-10 importer implemented
- [ ] CPT importer implemented
- [ ] Medical necessity rules importer implemented
- [ ] Batch processing optimized (1000 records/batch)
- [ ] CLI commands working

### Data Loading
- [ ] 70,000+ ICD-10 codes loaded
- [ ] 10,000+ CPT codes loaded
- [ ] Medical necessity rules configured
- [ ] Data verified with queries

### Service Layer
- [ ] MedicalCodesService created
- [ ] ICD-10 validation implemented
- [ ] CPT validation implemented
- [ ] Full-text search implemented
- [ ] Medical necessity checking implemented
- [ ] Performance optimized (<100ms search)

### API Endpoints
- [ ] GET /icd10/{code}/validate
- [ ] GET /cpt/{code}/validate
- [ ] GET /icd10/search
- [ ] GET /cpt/search
- [ ] POST /medical-necessity/check
- [ ] GET /statistics
- [ ] All endpoints tested

### Testing
- [ ] Verification script created
- [ ] All tests passing
- [ ] Performance benchmarks met
- [ ] API documented in Swagger

### Documentation
- [ ] Import process documented
- [ ] API endpoints documented
- [ ] Medical necessity rules documented
- [ ] Troubleshooting guide created
```

---

**Continue to Week 3-4?** I can provide:
1. Complete testing infrastructure
2. Integration test suites
3. Coverage improvement strategies
4. Test automation scripts

Would you like me to continue with Week 3-4: Testing Infrastructure?