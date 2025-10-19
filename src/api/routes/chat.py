"""
Chat API with WebSocket and REST endpoints
Provides real-time chat interface for multi-agent RCM system
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import asyncio
import logging
import uuid

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.chat_orchestrator import ChatOrchestrator
from src.services.database import get_db_session
from src.core.auth import get_current_user, get_current_user_ws
from src.models.user import User
from src.models.chat import ChatMessage, Conversation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

# Initialize orchestrator
chat_orchestrator = ChatOrchestrator()


# ============================================================================
# CONNECTION MANAGER
# ============================================================================

class ConnectionManager:
    """Manage WebSocket connections for real-time chat"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_metadata: Dict[str, Dict[str, Any]] = {}
        self.message_queues: Dict[str, asyncio.Queue] = {}
    
    async def connect(self, user_id: str, websocket: WebSocket):
        """Connect user to WebSocket"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.user_metadata[user_id] = {
            'connected_at': datetime.utcnow().isoformat(),
            'message_count': 0,
            'last_activity': datetime.utcnow().isoformat()
        }
        self.message_queues[user_id] = asyncio.Queue()
        logger.info(f"✅ User {user_id} connected to chat WebSocket")
    
    def disconnect(self, user_id: str):
        """Disconnect user from WebSocket"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.user_metadata:
            del self.user_metadata[user_id]
        if user_id in self.message_queues:
            del self.message_queues[user_id]
        logger.info(f"❌ User {user_id} disconnected from chat")
    
    async def send_message(self, user_id: str, message: Dict[str, Any]):
        """Send message to specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
                self.user_metadata[user_id]['message_count'] += 1
                self.user_metadata[user_id]['last_activity'] = datetime.utcnow().isoformat()
            except Exception as e:
                logger.error(f"❌ Failed to send message to {user_id}: {e}")
                self.disconnect(user_id)
    
    async def send_typing_indicator(
        self,
        user_id: str,
        agent_name: str,
        is_typing: bool = True
    ):
        """Send typing indicator"""
        await self.send_message(user_id, {
            'type': 'typing',
            'agent_name': agent_name,
            'is_typing': is_typing,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def is_connected(self, user_id: str) -> bool:
        """Check if user is connected"""
        return user_id in self.active_connections
    
    def get_active_users(self) -> List[str]:
        """Get list of active user IDs"""
        return list(self.active_connections.keys())
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)


manager = ConnectionManager()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ChatMessageRequest(BaseModel):
    """Chat message from user"""
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: Optional[str] = None
    message_type: str = Field(default="text", pattern="^(text|voice|file)$")
    attachments: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatMessageResponse(BaseModel):
    """Chat message response"""
    message_id: str
    conversation_id: str
    type: str
    content: str
    agent_name: Optional[str] = None
    agent_type: Optional[str] = None
    timestamp: str
    actions: Optional[List[Dict[str, str]]] = None
    data: Optional[Dict[str, Any]] = None


class ConversationResponse(BaseModel):
    """Conversation response"""
    conversation_id: str
    user_id: str
    title: Optional[str] = None
    created_at: str
    updated_at: str
    message_count: int
    status: str


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    WebSocket endpoint for real-time chat
    
    Message Types:
    - user_message: Message from user
    - agent_message: Message from agent
    - typing: Typing indicator
    - system: System notification
    - error: Error message
    - workflow_update: Workflow status update
    """
    await manager.connect(user_id, websocket)
    
    try:
        # Send welcome message
        await manager.send_message(user_id, {
            'type': 'agent_message',
            'message_id': str(uuid.uuid4()),
            'agent_name': 'HealthFlow Assistant',
            'agent_type': 'system',
            'agent_avatar': '🏥',
            'message': (
                '👋 **Welcome to HealthFlow RCM!**\n\n'
                'I\'m your AI assistant for complete revenue cycle management. '
                'I can help you with:\n\n'
                '• 📝 **Patient Registration** - Register new patients and verify demographics\n'
                '• 💳 **Insurance Verification** - Check coverage and eligibility in real-time\n'
                '• 🔐 **Prior Authorization** - Submit and track authorization requests\n'
                '• 🏥 **Medical Coding** - Find ICD-10 and CPT codes with AI assistance\n'
                '• 📋 **Claim Submission** - Submit claims to HCX platform\n'
                '• 🔍 **Claim Status** - Track claim progress and status\n'
                '• ⚠️ **Denial Management** - Analyze denials and generate appeals\n'
                '• 💰 **Payment Posting** - Post payments and reconcile accounts\n'
                '• 📊 **Analytics & Reports** - View dashboards and generate reports\n\n'
                '**You can:**\n'
                '✅ Type your message\n'
                '🎤 Use voice input (click microphone icon)\n'
                '📎 Upload documents (ID cards, bills, EOBs)\n\n'
                '**Try saying:**\n'
                '• "Register patient Ahmed Mohamed"\n'
                '• "Check insurance eligibility"\n'
                '• "Find ICD-10 code for diabetes"\n'
                '• "Submit claim for patient"\n\n'
                'What would you like to do today?'
            ),
            'actions': [
                {'label': '📝 Register Patient', 'action': 'register_patient', 'icon': '📝'},
                {'label': '💳 Verify Insurance', 'action': 'verify_insurance', 'icon': '💳'},
                {'label': '🏥 Find Medical Code', 'action': 'search_medical_code', 'icon': '🏥'},
                {'label': '📋 Create Claim', 'action': 'create_claim', 'icon': '📋'},
                {'label': '📊 View Dashboard', 'action': 'view_dashboard', 'icon': '📊'},
            ],
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Main message loop
        while True:
            # Receive message from user
            data = await websocket.receive_json()
            
            message_text = data.get('message', '')
            conversation_id = data.get('conversation_id', user_id)
            message_type = data.get('type', 'text')
            attachments = data.get('attachments', [])
            
            logger.info(f"📨 Received message from {user_id}: {message_text[:50]}...")
            
            # Echo user message back
            await manager.send_message(user_id, {
                'type': 'user_message',
                'message_id': str(uuid.uuid4()),
                'message': message_text,
                'attachments': attachments,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Show typing indicator
            await manager.send_typing_indicator(user_id, 'Processing your request...')
            
            try:
                # Process message through orchestrator
                responses = await chat_orchestrator.process_message(
                    user_id=user_id,
                    message=message_text,
                    conversation_id=conversation_id,
                    message_type=message_type,
                    attachments=attachments,
                    db_session=db
                )
                
                # Send agent responses
                for response in responses:
                    await manager.send_message(user_id, {
                        'type': 'agent_message',
                        'message_id': str(uuid.uuid4()),
                        'agent_name': response.agent_name,
                        'agent_type': response.agent_type,
                        'agent_avatar': response.agent_avatar,
                        'message': response.message,
                        'data': response.data,
                        'actions': response.actions,
                        'workflow_id': response.workflow_id,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
                    # Small delay between messages for better UX
                    await asyncio.sleep(0.3)
                
            except Exception as e:
                logger.error(f"❌ Error processing message: {e}", exc_info=True)
                await manager.send_message(user_id, {
                    'type': 'error',
                    'message': 'I encountered an error processing your request. Please try again or rephrase your question.',
                    'error_details': str(e) if logger.level <= logging.DEBUG else None,
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            finally:
                # Stop typing indicator
                await manager.send_typing_indicator(user_id, '', False)
    
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        logger.info(f"🔌 WebSocket disconnected: {user_id}")
    
    except Exception as e:
        logger.error(f"❌ WebSocket error for {user_id}: {e}", exc_info=True)
        try:
            await manager.send_message(user_id, {
                'type': 'error',
                'message': 'Connection error occurred. Please refresh the page.',
                'timestamp': datetime.utcnow().isoformat()
            })
        except:
            pass
        manager.disconnect(user_id)


# ============================================================================
# REST ENDPOINTS
# ============================================================================

@router.post("/send", response_model=Dict[str, Any])
async def send_message(
    message: ChatMessageRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Send message via REST API (fallback for WebSocket)
    
    This endpoint is useful for:
    - Testing without WebSocket
    - Mobile apps with limited WebSocket support
    - Scheduled/automated messages
    """
    conversation_id = message.conversation_id or user.id
    
    try:
        # Process message
        responses = await chat_orchestrator.process_message(
            user_id=user.id,
            message=message.message,
            conversation_id=conversation_id,
            message_type=message.message_type,
            attachments=message.attachments,
            db_session=db
        )
        
        # If user is connected via WebSocket, send there too
        if manager.is_connected(user.id):
            for response in responses:
                await manager.send_message(user.id, {
                    'type': 'agent_message',
                    'agent_name': response.agent_name,
                    'message': response.message,
                    'data': response.data,
                    'actions': response.actions,
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        return {
            'success': True,
            'conversation_id': conversation_id,
            'responses': [
                {
                    'agent_name': r.agent_name,
                    'agent_type': r.agent_type,
                    'message': r.message,
                    'data': r.data,
                    'actions': r.actions
                }
                for r in responses
            ],
            'timestamp': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to process message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get user's conversation history"""
    conversations = await chat_orchestrator.get_user_conversations(
        user_id=user.id,
        limit=limit,
        offset=offset,
        db_session=db
    )
    
    return conversations


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get messages from a specific conversation"""
    messages = await chat_orchestrator.get_conversation_messages(
        conversation_id=conversation_id,
        user_id=user.id,
        limit=limit,
        offset=offset,
        db_session=db
    )
    
    return {
        'conversation_id': conversation_id,
        'messages': messages,
        'count': len(messages),
        'has_more': len(messages) == limit
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a conversation and all its messages"""
    success = await chat_orchestrator.delete_conversation(
        conversation_id=conversation_id,
        user_id=user.id,
        db_session=db
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {
        'success': True,
        'message': 'Conversation deleted successfully'
    }


@router.post("/conversations/{conversation_id}/clear")
async def clear_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Clear all messages from a conversation"""
    success = await chat_orchestrator.clear_conversation(
        conversation_id=conversation_id,
        user_id=user.id,
        db_session=db
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {
        'success': True,
        'message': 'Conversation cleared successfully'
    }


@router.get("/active-users")
async def get_active_users(
    user: User = Depends(get_current_user)
):
    """Get active WebSocket users (admin only)"""
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return {
        'active_users': manager.get_active_users(),
        'count': manager.get_connection_count(),
        'metadata': manager.user_metadata,
        'timestamp': datetime.utcnow().isoformat()
    }


@router.post("/broadcast")
async def broadcast_message(
    message: str,
    user: User = Depends(get_current_user)
):
    """Broadcast message to all connected users (admin only)"""
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    broadcast_data = {
        'type': 'system',
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # Send to all connected users
    for user_id in manager.get_active_users():
        await manager.send_message(user_id, broadcast_data)
    
    return {
        'success': True,
        'recipients': manager.get_connection_count(),
        'message': 'Broadcast sent successfully'
    }


@router.get("/health")
async def chat_health():
    """Check chat service health"""
    return {
        'status': 'healthy',
        'websocket_connections': manager.get_connection_count(),
        'active_users': len(manager.get_active_users()),
        'timestamp': datetime.utcnow().isoformat()
    }
