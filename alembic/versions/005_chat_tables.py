"""Add chat and conversation tables

Revision ID: 005_chat_tables
Revises: 004_medical_codes
Create Date: 2025-10-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_chat_tables'
down_revision = '004_medical_codes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create conversations table
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('message_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('metadata', postgresql.JSON, nullable=True),
    )
    
    # Create indexes for conversations
    op.create_index('idx_conversations_user_status', 'conversations', ['user_id', 'status'])
    op.create_index('idx_conversations_updated_at', 'conversations', ['updated_at'])
    
    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('message_type', sa.String(50), nullable=False, server_default='text'),
        sa.Column('agent_name', sa.String(100), nullable=True),
        sa.Column('agent_type', sa.String(50), nullable=True),
        sa.Column('metadata', postgresql.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    
    # Create indexes for chat_messages
    op.create_index('idx_chat_messages_conversation', 'chat_messages', ['conversation_id', 'created_at'])
    op.create_index('idx_chat_messages_user', 'chat_messages', ['user_id', 'created_at'])
    op.create_index('idx_chat_messages_role', 'chat_messages', ['role'])
    
    print("✅ Created chat tables and indexes")


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_chat_messages_role')
    op.drop_index('idx_chat_messages_user')
    op.drop_index('idx_chat_messages_conversation')
    op.drop_index('idx_conversations_updated_at')
    op.drop_index('idx_conversations_user_status')
    
    # Drop tables
    op.drop_table('chat_messages')
    op.drop_table('conversations')
    
    print("✅ Dropped chat tables and indexes")
