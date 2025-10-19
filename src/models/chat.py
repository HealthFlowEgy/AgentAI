"""
Chat and Conversation Database Models
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.models.base import Base


class Conversation(Base):
    """Conversation model for tracking chat sessions"""
    
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    status = Column(String(50), default="active", index=True)  # active, archived, deleted
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Metadata
    message_count = Column(Integer, default=0)
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_conversations_user_status', 'user_id', 'status'),
        Index('idx_conversations_updated_at', 'updated_at'),
    )
    
    def __repr__(self):
        return f"<Conversation {self.id}: {self.title or 'Untitled'}>"


class ChatMessage(Base):
    """Chat message model"""
    
    __tablename__ = "chat_messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Message content
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    message_type = Column(String(50), default="text")  # text, voice, file, action
    
    # Agent information (for assistant messages)
    agent_name = Column(String(100), nullable=True)
    agent_type = Column(String(50), nullable=True)
    
    # Metadata
    metadata = Column(JSON, nullable=True)  # attachments, actions, data, etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    # Indexes
    __table_args__ = (
        Index('idx_chat_messages_conversation', 'conversation_id', 'created_at'),
        Index('idx_chat_messages_user', 'user_id', 'created_at'),
        Index('idx_chat_messages_role', 'role'),
    )
    
    def __repr__(self):
        return f"<ChatMessage {self.id}: {self.role} in {self.conversation_id}>"
