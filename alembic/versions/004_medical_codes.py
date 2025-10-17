"""Add comprehensive medical codes tables

Revision ID: 004
Revises: 003
Create Date: 2025-10-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


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

