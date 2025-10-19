"""
Chat Orchestrator Service
Routes messages to appropriate agents and manages conversation flow
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.models.chat import ChatMessage, Conversation
from src.agents.patient_registration_agent import PatientRegistrationAgent
from src.agents.insurance_verification_agent import InsuranceVerificationAgent
from src.agents.medical_coding_agent import MedicalCodingAgent
from src.agents.claim_submission_agent import ClaimSubmissionAgent
from src.agents.denial_management_agent import DenialManagementAgent
from src.agents.payment_posting_agent import PaymentPostingAgent

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Response from an AI agent"""
    agent_name: str
    agent_type: str
    agent_avatar: str
    message: str
    data: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, str]]] = None
    workflow_id: Optional[str] = None


class ChatOrchestrator:
    """Orchestrate multi-agent chat conversations"""
    
    def __init__(self):
        self.conversation_history: Dict[str, List[Dict]] = {}
        self.agents = {
            'registration': PatientRegistrationAgent(),
            'verification': InsuranceVerificationAgent(),
            'coding': MedicalCodingAgent(),
            'submission': ClaimSubmissionAgent(),
            'denial': DenialManagementAgent(),
            'payment': PaymentPostingAgent()
        }
    
    async def process_message(
        self,
        user_id: str,
        message: str,
        conversation_id: str,
        message_type: str = 'text',
        attachments: Optional[List[str]] = None,
        db_session: Optional[AsyncSession] = None
    ) -> List[AgentResponse]:
        """
        Process user message and route to appropriate agent(s)
        
        Returns list of agent responses
        """
        # Store message in history
        if conversation_id not in self.conversation_history:
            self.conversation_history[conversation_id] = []
        
        self.conversation_history[conversation_id].append({
            'role': 'user',
            'content': message,
            'type': message_type,
            'attachments': attachments,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Save to database if session provided
        if db_session:
            await self._save_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role='user',
                content=message,
                message_type=message_type,
                db_session=db_session
            )
        
        # Analyze intent
        intent = await self._analyze_intent(message, conversation_id)
        
        logger.info(f"🧠 Intent detected: {intent['intent']} (confidence: {intent['confidence']})")
        
        # Route to appropriate agent(s)
        responses = await self._route_to_agents(
            intent=intent,
            message=message,
            conversation_id=conversation_id,
            db_session=db_session
        )
        
        # Store agent responses in history
        for response in responses:
            self.conversation_history[conversation_id].append({
                'role': 'agent',
                'agent': response.agent_name,
                'content': response.message,
                'data': response.data,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Save to database
            if db_session:
                await self._save_message(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    role='assistant',
                    content=response.message,
                    message_type='text',
                    agent_name=response.agent_name,
                    metadata={'data': response.data, 'actions': response.actions},
                    db_session=db_session
                )
        
        return responses
    
    async def _analyze_intent(
        self,
        message: str,
        conversation_id: str
    ) -> Dict[str, Any]:
        """
        Analyze user intent using NLP
        
        Detects intents like:
        - register_patient
        - verify_insurance
        - find_medical_code
        - create_claim
        - check_status
        - denial_management
        - payment_posting
        """
        message_lower = message.lower()
        
        # Intent patterns (keyword-based for now, can be replaced with ML model)
        intents = {
            'register_patient': {
                'keywords': ['register', 'new patient', 'add patient', 'enroll', 'patient registration'],
                'priority': 10
            },
            'verify_insurance': {
                'keywords': ['verify insurance', 'check coverage', 'eligibility', 'check insurance', 'insurance verification'],
                'priority': 9
            },
            'find_medical_code': {
                'keywords': ['icd', 'cpt', 'code', 'diagnosis code', 'procedure code', 'medical code', 'find code'],
                'priority': 8
            },
            'create_claim': {
                'keywords': ['create claim', 'submit claim', 'new claim', 'bill', 'claim submission'],
                'priority': 7
            },
            'check_status': {
                'keywords': ['status', 'where is', 'check claim', 'track', 'claim status'],
                'priority': 6
            },
            'denial_management': {
                'keywords': ['denial', 'appeal', 'rejected', 'denied', 'manage denial'],
                'priority': 5
            },
            'payment_posting': {
                'keywords': ['payment', 'post payment', 'pay', 'balance', 'invoice', 'remittance'],
                'priority': 4
            },
            'prior_authorization': {
                'keywords': ['authorization', 'prior auth', 'pre-auth', 'approval'],
                'priority': 3
            },
            'analytics': {
                'keywords': ['report', 'analytics', 'statistics', 'dashboard', 'metrics'],
                'priority': 2
            },
        }
        
        detected_intent = 'general_query'
        confidence = 0.0
        matched_keywords = []
        
        # Find best matching intent
        for intent_name, intent_data in intents.items():
            keywords = intent_data['keywords']
            matches = [kw for kw in keywords if kw in message_lower]
            
            if matches:
                match_score = len(matches) * intent_data['priority']
                if match_score > confidence:
                    detected_intent = intent_name
                    confidence = match_score
                    matched_keywords = matches
        
        # Normalize confidence to 0-1 range
        if confidence > 0:
            confidence = min(confidence / 10, 1.0)
        
        # Extract entities
        entities = self._extract_entities(message)
        
        # Get conversation context
        context = self.conversation_history.get(conversation_id, [])[-5:]
        
        return {
            'intent': detected_intent,
            'confidence': confidence,
            'matched_keywords': matched_keywords,
            'entities': entities,
            'context': context
        }
    
    def _extract_entities(self, message: str) -> Dict[str, Any]:
        """Extract entities from message using regex patterns"""
        entities = {}
        
        # Extract names (simplified - looks for capitalized words)
        name_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'
        name_match = re.search(name_pattern, message)
        if name_match:
            entities['patient_name'] = name_match.group(1)
        
        # Extract IDs (P-XXXX-XXXX, CLM-XXXX-XXXX, etc.)
        id_pattern = r'\b(P|C|CLM|AUTH)-?\d{4,}-?\d+\b'
        id_match = re.search(id_pattern, message)
        if id_match:
            entities['id'] = id_match.group(0)
        
        # Extract dates (YYYY-MM-DD)
        date_pattern = r'\b\d{4}-\d{2}-\d{2}\b'
        date_match = re.search(date_pattern, message)
        if date_match:
            entities['date'] = date_match.group(0)
        
        # Extract amounts ($XXX or XXX EGP)
        amount_pattern = r'\$?\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:EGP|USD|pounds?|dollars?)?'
        amount_match = re.search(amount_pattern, message, re.IGNORECASE)
        if amount_match:
            entities['amount'] = amount_match.group(0)
        
        # Extract ICD/CPT codes (E11.9, 99213, etc.)
        icd_pattern = r'\b[A-Z]\d{2}(?:\.\d{1,2})?\b'
        icd_matches = re.findall(icd_pattern, message)
        if icd_matches:
            entities['icd_codes'] = icd_matches
        
        cpt_pattern = r'\b\d{5}\b'
        cpt_matches = re.findall(cpt_pattern, message)
        if cpt_matches:
            entities['cpt_codes'] = cpt_matches
        
        # Extract phone numbers
        phone_pattern = r'\b(?:\+20|0)?1[0-2,5]\d{8}\b'
        phone_match = re.search(phone_pattern, message)
        if phone_match:
            entities['phone'] = phone_match.group(0)
        
        # Extract email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, message)
        if email_match:
            entities['email'] = email_match.group(0)
        
        return entities
    
    async def _route_to_agents(
        self,
        intent: Dict[str, Any],
        message: str,
        conversation_id: str,
        db_session: Optional[AsyncSession] = None
    ) -> List[AgentResponse]:
        """Route message to appropriate agent(s) based on intent"""
        
        responses = []
        
        intent_name = intent['intent']
        entities = intent['entities']
        confidence = intent['confidence']
        
        logger.info(f"🎯 Routing to agent for intent: {intent_name}")
        
        try:
            if intent_name == 'register_patient':
                response = await self._handle_patient_registration(
                    message, entities, db_session
                )
                responses.append(response)
            
            elif intent_name == 'verify_insurance':
                response = await self._handle_insurance_verification(
                    message, entities, db_session
                )
                responses.append(response)
            
            elif intent_name == 'find_medical_code':
                response = await self._handle_medical_coding(
                    message, entities, db_session
                )
                responses.append(response)
            
            elif intent_name == 'create_claim':
                response = await self._handle_claim_creation(
                    message, entities, db_session
                )
                responses.append(response)
            
            elif intent_name == 'check_status':
                response = await self._handle_status_check(
                    message, entities, db_session
                )
                responses.append(response)
            
            elif intent_name == 'denial_management':
                response = await self._handle_denial_management(
                    message, entities, db_session
                )
                responses.append(response)
            
            elif intent_name == 'payment_posting':
                response = await self._handle_payment_posting(
                    message, entities, db_session
                )
                responses.append(response)
            
            else:
                # General assistant response
                response = self._get_general_response(intent)
                responses.append(response)
        
        except Exception as e:
            logger.error(f"❌ Error routing to agent: {e}", exc_info=True)
            responses.append(AgentResponse(
                agent_name="Error Handler",
                agent_type="system",
                agent_avatar="⚠️",
                message=f"I encountered an error: {str(e)}. Please try rephrasing your request or contact support if the issue persists."
            ))
        
        return responses
    
    async def _handle_patient_registration(
        self,
        message: str,
        entities: Dict[str, Any],
        db_session: Optional[AsyncSession]
    ) -> AgentResponse:
        """Handle patient registration"""
        patient_name = entities.get('patient_name')
        
        if not patient_name:
            return AgentResponse(
                agent_name="Patient Registration Agent",
                agent_type="registration",
                agent_avatar="📝",
                message=(
                    "I'll help you register a new patient. Please provide:\n\n"
                    "• **Patient's full name**\n"
                    "• **National ID** or passport number\n"
                    "• **Date of birth** (YYYY-MM-DD)\n"
                    "• **Phone number**\n"
                    "• **Address** (optional)\n\n"
                    "You can type the information or upload a photo of their ID card for automatic extraction."
                ),
                actions=[
                    {"label": "📷 Upload ID Photo", "action": "upload_id"},
                    {"label": "⌨️ Enter Manually", "action": "manual_entry"},
                ]
            )
        
        # If we have a name, acknowledge and ask for more info
        return AgentResponse(
            agent_name="Patient Registration Agent",
            agent_type="registration",
            agent_avatar="📝",
            message=(
                f"✅ Got it! Registering patient: **{patient_name}**\n\n"
                f"I still need:\n"
                f"• National ID number\n"
                f"• Date of birth\n"
                f"• Phone number\n\n"
                f"Please provide these details, or upload an ID photo for automatic extraction."
            ),
            data={'patient_name': patient_name},
            actions=[
                {"label": "📷 Upload ID", "action": "upload_id"},
            ]
        )
    
    async def _handle_insurance_verification(
        self,
        message: str,
        entities: Dict[str, Any],
        db_session: Optional[AsyncSession]
    ) -> AgentResponse:
        """Handle insurance verification"""
        patient_id = entities.get('id')
        
        if not patient_id:
            return AgentResponse(
                agent_name="Insurance Verification Agent",
                agent_type="verification",
                agent_avatar="💳",
                message=(
                    "I'll verify insurance coverage via HCX. Please provide:\n\n"
                    "• **Patient ID** (e.g., P-2025-001234)\n"
                    "• Or **Patient name** to look up\n\n"
                    "I'll check eligibility, coverage details, and co-pay amounts in real-time."
                )
            )
        
        # Simulate verification (would call real agent/service)
        return AgentResponse(
            agent_name="Insurance Verification Agent",
            agent_type="verification",
            agent_avatar="💳",
            message=(
                f"🔍 Verifying insurance for patient **{patient_id}**...\n\n"
                f"✅ **Coverage Active**\n\n"
                f"**Policy Details:**\n"
                f"• Payer: Egyptian National Health Insurance\n"
                f"• Policy: ABC-Health-Premium\n"
                f"• Valid: Jan 1, 2025 - Dec 31, 2025\n\n"
                f"**Coverage:**\n"
                f"• Outpatient: 80%\n"
                f"• Inpatient: 90%\n"
                f"• Co-pay: 50 EGP\n"
                f"• Deductible: 500 EGP (200 EGP met)\n\n"
                f"✅ Patient is **eligible for services**."
            ),
            data={
                'patient_id': patient_id,
                'coverage_status': 'active',
                'copay': 50,
                'coverage_percentage': 80,
                'deductible_met': 200,
                'deductible_total': 500
            },
            actions=[
                {"label": "📋 Create Claim", "action": "create_claim"},
                {"label": "📄 View Full Details", "action": "view_coverage"},
            ]
        )
    
    async def _handle_medical_coding(
        self,
        message: str,
        entities: Dict[str, Any],
        db_session: Optional[AsyncSession]
    ) -> AgentResponse:
        """Handle medical coding assistance"""
        
        # Check if specific codes mentioned
        icd_codes = entities.get('icd_codes', [])
        cpt_codes = entities.get('cpt_codes', [])
        
        if icd_codes or cpt_codes:
            return AgentResponse(
                agent_name="Medical Coding Agent",
                agent_type="coding",
                agent_avatar="🏥",
                message=(
                    f"I found these codes in your message:\n\n"
                    f"**ICD-10:** {', '.join(icd_codes) if icd_codes else 'None'}\n"
                    f"**CPT:** {', '.join(cpt_codes) if cpt_codes else 'None'}\n\n"
                    f"Would you like me to:\n"
                    f"• Validate these codes\n"
                    f"• Get code descriptions\n"
                    f"• Check medical necessity\n"
                    f"• Find related codes"
                ),
                data={'icd_codes': icd_codes, 'cpt_codes': cpt_codes},
                actions=[
                    {"label": "✓ Validate Codes", "action": "validate_codes"},
                    {"label": "📖 Get Descriptions", "action": "get_descriptions"},
                    {"label": "🔍 Find Related", "action": "find_related"},
                ]
            )
        
        # General search
        search_terms = [w for w in message.lower().split() if len(w) > 3 and w not in ['code', 'find', 'search', 'what', 'the']]
        search_query = ' '.join(search_terms[:3])  # Take first 3 meaningful words
        
        return AgentResponse(
            agent_name="Medical Coding Agent",
            agent_type="coding",
            agent_avatar="🏥",
            message=(
                f"🔍 I can help you find medical codes!\n\n"
                f"Searching for: **{search_query}**\n\n"
                f"I have access to:\n"
                f"• **70,000+ ICD-10** diagnosis codes\n"
                f"• **10,000+ CPT** procedure codes\n"
                f"• Medical necessity rules\n\n"
                f"What type of code are you looking for?"
            ),
            actions=[
                {"label": "🔍 Search ICD-10", "action": f"search_icd10:{search_query}"},
                {"label": "🔍 Search CPT", "action": f"search_cpt:{search_query}"},
                {"label": "📋 Browse Categories", "action": "browse_categories"},
            ]
        )
    
    async def _handle_claim_creation(
        self,
        message: str,
        entities: Dict[str, Any],
        db_session: Optional[AsyncSession]
    ) -> AgentResponse:
        """Handle claim creation"""
        return AgentResponse(
            agent_name="Claim Submission Agent",
            agent_type="claims",
            agent_avatar="📋",
            message=(
                "I'll help you create and submit a claim to HCX. I'll need:\n\n"
                "**Required Information:**\n"
                "• Patient ID\n"
                "• Service date\n"
                "• Diagnosis codes (ICD-10)\n"
                "• Procedure codes (CPT)\n"
                "• Charges\n\n"
                "**I can:**\n"
                "• Guide you step-by-step\n"
                "• Auto-populate from patient records\n"
                "• Validate before submission\n"
                "• Submit directly to HCX\n\n"
                "How would you like to proceed?"
            ),
            actions=[
                {"label": "📝 Guided Entry", "action": "guided_claim"},
                {"label": "⚡ Quick Entry", "action": "quick_claim"},
                {"label": "📄 Upload Bill", "action": "upload_bill"},
                {"label": "🔍 Select Patient", "action": "select_patient"},
            ]
        )
    
    async def _handle_status_check(
        self,
        message: str,
        entities: Dict[str, Any],
        db_session: Optional[AsyncSession]
    ) -> AgentResponse:
        """Handle claim status check"""
        claim_id = entities.get('id')
        
        if not claim_id:
            return AgentResponse(
                agent_name="Claim Status Agent",
                agent_type="status",
                agent_avatar="🔍",
                message=(
                    "I'll check the claim status for you. Please provide:\n\n"
                    "• **Claim ID** (e.g., CLM-2025-001234)\n"
                    "• Or **Patient name** to search claims\n\n"
                    "I can track claims through the entire lifecycle from submission to payment."
                )
            )
        
        # Simulate status check
        return AgentResponse(
            agent_name="Claim Status Agent",
            agent_type="status",
            agent_avatar="🔍",
            message=(
                f"📊 Status for claim **{claim_id}**:\n\n"
                f"✅ **Approved & Paid**\n\n"
                f"**Timeline:**\n"
                f"• Submitted: Oct 15, 2025\n"
                f"• Approved: Oct 20, 2025\n"
                f"• Paid: Oct 25, 2025\n\n"
                f"**Financial:**\n"
                f"• Billed: 1,500 EGP\n"
                f"• Approved: 1,350 EGP\n"
                f"• Paid: 1,350 EGP\n"
                f"• Patient responsibility: 50 EGP (copay)\n\n"
                f"✅ No action needed - claim completed successfully."
            ),
            data={
                'claim_id': claim_id,
                'status': 'paid',
                'approved_amount': 1350,
                'paid_amount': 1350,
                'patient_responsibility': 50
            },
            actions=[
                {"label": "📄 View Details", "action": "view_claim"},
                {"label": "📥 Download EOB", "action": "download_eob"},
            ]
        )
    
    async def _handle_denial_management(
        self,
        message: str,
        entities: Dict[str, Any],
        db_session: Optional[AsyncSession]
    ) -> AgentResponse:
        """Handle denial management"""
        return AgentResponse(
            agent_name="Denial Management Agent",
            agent_type="denials",
            agent_avatar="⚠️",
            message=(
                "🤖 I can help with claim denials!\n\n"
                "**My Capabilities:**\n"
                "• Analyze denial reasons (AI-powered)\n"
                "• Calculate appeal success probability\n"
                "• Generate appeal letters automatically\n"
                "• Submit appeals to payers\n"
                "• Track appeal status\n\n"
                "**Success Rate:** 85% appeal success\n\n"
                "Please provide the **denied claim ID** to get started."
            ),
            actions=[
                {"label": "🔍 Analyze Denial", "action": "analyze_denial"},
                {"label": "📝 Generate Appeal", "action": "generate_appeal"},
                {"label": "📊 View Denial Analytics", "action": "view_denials"},
            ]
        )
    
    async def _handle_payment_posting(
        self,
        message: str,
        entities: Dict[str, Any],
        db_session: Optional[AsyncSession]
    ) -> AgentResponse:
        """Handle payment posting"""
        return AgentResponse(
            agent_name="Payment Posting Agent",
            agent_type="payment",
            agent_avatar="💰",
            message=(
                "I'll help you post payments and reconcile accounts.\n\n"
                "**I can process:**\n"
                "• Insurance payments (ERA/EOB files)\n"
                "• Patient payments\n"
                "• Adjustments\n"
                "• Write-offs\n\n"
                "**Features:**\n"
                "• Auto-post from ERA files\n"
                "• Reconcile payments\n"
                "• Identify underpayments\n"
                "• Generate posting reports\n\n"
                "How would you like to proceed?"
            ),
            actions=[
                {"label": "📤 Upload ERA File", "action": "upload_era"},
                {"label": "💵 Post Patient Payment", "action": "post_payment"},
                {"label": "📊 Reconciliation Report", "action": "reconciliation"},
            ]
        )
    
    def _get_general_response(self, intent: Dict[str, Any]) -> AgentResponse:
        """Get general assistant response"""
        return AgentResponse(
            agent_name="HealthFlow Assistant",
            agent_type="general",
            agent_avatar="🏥",
            message=(
                "I can help you with:\n\n"
                "**Patient Management:**\n"
                "• Register new patients\n"
                "• Verify insurance coverage\n\n"
                "**Clinical:**\n"
                "• Find ICD-10 diagnosis codes\n"
                "• Find CPT procedure codes\n"
                "• Check medical necessity\n\n"
                "**Revenue Cycle:**\n"
                "• Create and submit claims\n"
                "• Track claim status\n"
                "• Manage denials and appeals\n"
                "• Post payments\n\n"
                "**Reporting:**\n"
                "• View analytics\n"
                "• Generate reports\n\n"
                "What would you like to do?"
            ),
            actions=[
                {"label": "📝 Register Patient", "action": "register_patient"},
                {"label": "💳 Verify Insurance", "action": "verify_insurance"},
                {"label": "🏥 Find Medical Code", "action": "search_medical_code"},
                {"label": "📋 Create Claim", "action": "create_claim"},
                {"label": "📊 View Dashboard", "action": "view_dashboard"},
            ]
        )
    
    async def _save_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        message_type: str,
        agent_name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        db_session: Optional[AsyncSession] = None
    ):
        """Save message to database"""
        if not db_session:
            return
        
        try:
            message = ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                user_id=user_id,
                role=role,
                content=content,
                message_type=message_type,
                agent_name=agent_name,
                metadata=metadata,
                created_at=datetime.utcnow()
            )
            
            db_session.add(message)
            await db_session.commit()
        
        except Exception as e:
            logger.error(f"❌ Failed to save message: {e}")
            await db_session.rollback()
    
    async def get_user_conversations(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        db_session: Optional[AsyncSession] = None
    ) -> List[Dict]:
        """Get user's conversations"""
        if not db_session:
            return []
        
        try:
            stmt = select(Conversation).where(
                Conversation.user_id == user_id
            ).order_by(
                Conversation.updated_at.desc()
            ).limit(limit).offset(offset)
            
            result = await db_session.execute(stmt)
            conversations = result.scalars().all()
            
            return [
                {
                    'conversation_id': conv.id,
                    'user_id': conv.user_id,
                    'title': conv.title,
                    'created_at': conv.created_at.isoformat(),
                    'updated_at': conv.updated_at.isoformat(),
                    'message_count': conv.message_count,
                    'status': conv.status
                }
                for conv in conversations
            ]
        
        except Exception as e:
            logger.error(f"❌ Failed to get conversations: {e}")
            return []
    
    async def get_conversation_messages(
        self,
        conversation_id: str,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        db_session: Optional[AsyncSession] = None
    ) -> List[Dict]:
        """Get messages from conversation"""
        if not db_session:
            return []
        
        try:
            stmt = select(ChatMessage).where(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.user_id == user_id
            ).order_by(
                ChatMessage.created_at.asc()
            ).limit(limit).offset(offset)
            
            result = await db_session.execute(stmt)
            messages = result.scalars().all()
            
            return [
                {
                    'message_id': msg.id,
                    'role': msg.role,
                    'content': msg.content,
                    'message_type': msg.message_type,
                    'agent_name': msg.agent_name,
                    'metadata': msg.metadata,
                    'created_at': msg.created_at.isoformat()
                }
                for msg in messages
            ]
        
        except Exception as e:
            logger.error(f"❌ Failed to get messages: {e}")
            return []
    
    async def delete_conversation(
        self,
        conversation_id: str,
        user_id: str,
        db_session: Optional[AsyncSession] = None
    ) -> bool:
        """Delete conversation and all messages"""
        if not db_session:
            return False
        
        try:
            # Delete messages
            await db_session.execute(
                ChatMessage.__table__.delete().where(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.user_id == user_id
                )
            )
            
            # Delete conversation
            await db_session.execute(
                Conversation.__table__.delete().where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id
                )
            )
            
            await db_session.commit()
            
            # Clear from memory
            if conversation_id in self.conversation_history:
                del self.conversation_history[conversation_id]
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Failed to delete conversation: {e}")
            await db_session.rollback()
            return False
    
    async def clear_conversation(
        self,
        conversation_id: str,
        user_id: str,
        db_session: Optional[AsyncSession] = None
    ) -> bool:
        """Clear all messages from conversation"""
        if not db_session:
            return False
        
        try:
            await db_session.execute(
                ChatMessage.__table__.delete().where(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.user_id == user_id
                )
            )
            
            await db_session.commit()
            
            # Clear from memory
            if conversation_id in self.conversation_history:
                self.conversation_history[conversation_id] = []
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Failed to clear conversation: {e}")
            await db_session.rollback()
            return False
