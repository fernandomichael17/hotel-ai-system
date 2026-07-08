from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from ...core.channel.resolver import ChannelResolver
from ...core.session.manager import SessionManager
from ...core.session.context_enricher import ContextEnricher
from ...core.classifier.intent_classifier import IntentClassifier
from ...core.classifier.schemas import IntentType
from ...core.response.fallback_handler import FallbackHandler
from ...core.response.formatter import ResponseFormatter
from ...integrations.llm.embedder import TextEmbedder
from ...integrations.llm.client import LLMClient
from ...rag.retriever import RAGRetriever
from ...core.workflows.faq.handler import FAQHandler

# Initialize dependencies (in production these might be injected)
channel_resolver = ChannelResolver()
session_manager = SessionManager()
context_enricher = ContextEnricher()
llm_client = LLMClient()
intent_classifier = IntentClassifier(llm_client=llm_client)
fallback_handler = FallbackHandler()
response_formatter = ResponseFormatter()

# RAG & Workflow handlers
text_embedder = TextEmbedder()
rag_retriever = RAGRetriever(embedder=text_embedder)
faq_handler = FAQHandler(llm_client=llm_client, retriever=rag_retriever, session_manager=session_manager)

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    user_identifier: str
    channel: str
    hotel_slug: Optional[str] = None
    wa_number_to: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    intent: str
    confidence: float
    session_id: str

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    # 1. Resolve hotel context
    hotel_context = await channel_resolver.resolve(req.wa_number_to, req.hotel_slug)
    if not hotel_context:
        raise HTTPException(status_code=404, detail="Hotel not found")
        
    # 2. Get/create session
    session = await session_manager.get_or_create(req.user_identifier, str(hotel_context.hotel_id), req.channel)
    session_id = str(session.id)
    
    # 3. Enrich guest context
    guest_context = await context_enricher.enrich(req.user_identifier, str(hotel_context.hotel_id))
    
    # 4. Get history
    history = await session_manager.get_history(session_id)
    
    # 5. Classify intent
    classification = await intent_classifier.classify(req.message) # Assuming async or adjust if sync
    
    # 6. Check fallback
    if fallback_handler.should_fallback(classification.confidence):
        response_text = fallback_handler.get_fallback_response(req.message, req.channel)
        intent_str = IntentType.UNKNOWN.value
    else:
        intent_str = classification.intent.value
        
        # 7. Route ke workflow handler
        if intent_str == IntentType.FAQ.value:
            # Requires LLMClient, RAGRetriever - handled via dependencies in real app
            response_text = await faq_handler.handle(req.message, hotel_context, guest_context, session_id)
        elif intent_str in [IntentType.BOOKING_INQUIRY.value, IntentType.BOOKING_REQUEST.value]:
            response_text = "[Booking Handler] Sedang dalam pengembangan - coming Task 5"
        elif intent_str == IntentType.COMPLAINT.value:
            response_text = "[Complaint Handler] Sedang dalam pengembangan - coming Task 7"
        elif intent_str == IntentType.REFUND.value:
            response_text = "[Refund Handler] Sedang dalam pengembangan - coming Task 9"
        elif intent_str == IntentType.RESCHEDULE.value:
            response_text = "[Reschedule Handler] Sedang dalam pengembangan - coming soon"
        else:
            response_text = "Maaf, saya tidak memahami permintaan Anda."
            
    # 8. Format response
    formatted_response = response_formatter.format(response_text, req.channel, intent_str)
    
    # 9. Save message ke session
    await session_manager.add_message(
        session_id=session_id,
        role="user",
        content=req.message,
        intent=intent_str,
        confidence=classification.confidence
    )
    await session_manager.add_message(
        session_id=session_id,
        role="assistant",
        content=formatted_response
    )
    
    # 10. Return response
    return ChatResponse(
        response=formatted_response,
        intent=intent_str,
        confidence=classification.confidence,
        session_id=session_id
    )
