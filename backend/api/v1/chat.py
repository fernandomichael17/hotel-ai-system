import time
import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.core.channel.resolver import ChannelResolver
from backend.core.channel.context import ConversationContext
from backend.core.session.manager import SessionManager
from backend.core.session.context_enricher import ContextEnricher
from backend.core.classifier.intent_classifier import IntentClassifier
from backend.integrations.llm.client import get_llm_client
from backend.core.response.formatter import ResponseFormatter
from backend.core.response.fallback_handler import FallbackHandler
from backend.core.response.templates import SYSTEM_ERROR

_intent_classifier_instance = None

def get_intent_classifier(llm_client) -> IntentClassifier:
    """Helper singleton untuk mendapatkan instansi tunggal IntentClassifier."""
    global _intent_classifier_instance
    if _intent_classifier_instance is None:
        _intent_classifier_instance = IntentClassifier(llm_client=llm_client)
    return _intent_classifier_instance

# Workflows
from backend.core.workflows.faq.handler import FAQHandler
from backend.core.workflows.booking.handler import BookingHandler
from backend.core.workflows.complaint.handler import ComplaintHandler
from backend.core.workflows.refund.handler import RefundHandler
from backend.core.workflows.reschedule.handler import RescheduleHandler
from backend.core.workflows.booking.schemas import BookingStep

INFO_KEYWORDS = {
    "harga", "tarif", "berapa", "apa saja",
    "tipe", "jenis", "ada apa", "tersedia apa",
    "fasilitas kamar", "perbedaan", "bedanya",
    "info", "informasi"
}

BOOKING_ACTION_KEYWORDS = {
    "mau booking", "mau pesan", "ingin booking",
    "ingin pesan", "mau reservasi",
    "ingin reservasi", "book sekarang",
    "pesan sekarang"
}

def should_reroute_to_faq(
    intent: str,
    message: str,
    has_active_workflow: bool
) -> bool:
    if has_active_workflow:
        return False
    if intent not in [
        "booking_inquiry", "booking_request"
    ]:
        return False

    msg_lower = message.lower()

    # Kalau ada kata aksi booking yang jelas
    # → jangan reroute
    if any(
        kw in msg_lower
        for kw in BOOKING_ACTION_KEYWORDS
    ):
        return False

    # Kalau ada kata info → reroute ke FAQ
    if any(
        kw in msg_lower
        for kw in INFO_KEYWORDS
    ):
        return True

    # Kalau booking_request tapi tidak ada
    # tanggal dan ada kata tanya
    question_words = {
        "apa", "berapa", "bagaimana",
        "gimana", "ada", "tersedia",
        "boleh", "bisa"
    }
    has_question = any(
        qw in msg_lower
        for qw in question_words
    )
    no_date_hint = not any(
        date_hint in msg_lower
        for date_hint in [
            "tanggal", "hari", "bulan",
            "besok", "lusa", "minggu",
            "weekend", "malam", "januari",
            "februari", "maret", "april",
            "mei", "juni", "juli", "agustus",
            "september", "oktober",
            "november", "desember"
        ]
    )

    return has_question and no_date_hint

async def handle_greeting(
    ctx: ConversationContext,
    llm_client
) -> str:
    """
    Generate sapaan yang hangat dan
    informatif sesuai bahasa user.
    """
    system = (
        "Kamu adalah asisten hotel yang ramah. "
        "Balas sapaan tamu dengan hangat dalam "
        "bahasa yang sama dengan tamu. "
        "Setelah menyapa, jelaskan singkat "
        "apa saja yang bisa dibantu: "
        "informasi hotel, booking kamar, "
        "menyampaikan keluhan, atau "
        "request layanan kamar."
    )
    prompt = (
        f"Instruksi:\n{system}\n\n"
        f"Pesan tamu: \"{ctx.message.content}\"\n"
        "Jawaban ramah:"
    )
    response = await asyncio.to_thread(llm_client.generate, prompt)
    return response

router = APIRouter()
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    message: str
    user_identifier: str
    channel: str = "web"
    hotel_slug: str | None = None
    waha_session: str | None = None

class ChatResponse(BaseModel):
    response: str
    intent: str
    confidence: float
    session_id: str
    is_enriched: bool

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint utama chatbot untuk memproses, mengklasifikasi intent, dan merouting percakapan tamu.
    """
    start_time = time.time()
    formatter = ResponseFormatter()
    fallback = FallbackHandler()
    
    session_id_str = ""
    is_enriched_flag = False
    
    try:
        # 1. Resolve hotel
        resolver = ChannelResolver(db)
        hotel_ctx = await resolver.resolve(
            waha_session=request.waha_session,
            hotel_slug=request.hotel_slug
        )
        
        if not hotel_ctx:
            logger.warning(f"Hotel not found for slug: {request.hotel_slug} or session: {request.waha_session}")
            return ChatResponse(
                response="Hotel tidak ditemukan.",
                intent="unknown",
                confidence=0.0,
                session_id="",
                is_enriched=False
            )
        
        # 2. Get/create session
        session_mgr = SessionManager(db)
        session = await session_mgr.get_or_create(
            user_identifier=request.user_identifier,
            hotel_id=hotel_ctx.hotel_id,
            channel=request.channel
        )
        session_id_str = session.session_id
        
        # 3. Enrich context
        enricher = ContextEnricher(db)
        guest_ctx = await enricher.enrich(
            user_identifier=request.user_identifier,
            hotel_id=hotel_ctx.hotel_id
        )
        
        # 4. Get history
        history = await session_mgr.get_history_for_llm(session.session_id)
        
        # Cek apakah ada workflow aktif di in-memory cache
        booking_state = await session_mgr.get_booking_state(session.session_id)
        has_active_workflow = (
            booking_state is not None
            and booking_state.step not in [
                BookingStep.COMPLETED,
                BookingStep.CANCELLED
            ]
        )
        
        # 5. Build context
        from backend.core.channel.schemas import IncomingMessage
        incoming = IncomingMessage(
            user_identifier=request.user_identifier,
            content=request.message,
            channel=request.channel,
            hotel_slug=request.hotel_slug,
            waha_session=request.waha_session
        )
        
        ctx = ConversationContext(
            message=incoming,
            hotel=hotel_ctx,
            guest=guest_ctx,
            session_id=session.session_id,
            history=history
        )
        is_enriched_flag = ctx.is_enriched
        
        # 6. Check escalation
        if fallback.is_escalation_request(request.message):
            response_text = fallback.get_escalation_response()
            await session_mgr.save_exchange(
                session_id=session.session_id,
                user_message=request.message,
                assistant_response=response_text,
                detected_intent="escalate",
                confidence=1.0
            )
            
            latency = time.time() - start_time
            logger.info(
                f"Hotel: {hotel_ctx.slug} | Intent: escalate | Confidence: 1.00 | Latency: {latency:.4f}s"
            )
            
            return ChatResponse(
                response=formatter.format(response_text, request.channel),
                intent="escalate",
                confidence=1.0,
                session_id=session.session_id,
                is_enriched=is_enriched_flag
            )
        
        # 7. Check menu selection
        menu_intent = fallback.handle_menu_selection(
            message=request.message,
            has_active_workflow=has_active_workflow
        )
        
        # 8. Classify intent
        llm = get_llm_client()
        classifier = get_intent_classifier(llm)
        if menu_intent:
            intent = menu_intent
            confidence = 1.0
        else:
            result = classifier.classify(request.message)
            intent = result.intent.value
            confidence = result.confidence
            
        # Override ke booking_request kalau ada
        # workflow aktif — termasuk greeting yang
        # mungkin adalah jawaban nama tamu
        BOOKING_OVERRIDE_INTENTS = {
            "unknown",
            "booking_inquiry",
            "booking_request",
            "greeting",
            "reschedule",
            "faq"
        }

        if has_active_workflow and intent in BOOKING_OVERRIDE_INTENTS:
            intent = "booking_request"
            confidence = 1.0
            
        # Reroute booking_inquiry / booking_request ke FAQ jika memenuhi kriteria
        if should_reroute_to_faq(intent, request.message, has_active_workflow):
            intent = "faq"
        
        # 9. Check fallback
        if fallback.should_fallback(confidence):
            response_text = fallback.get_fallback_response()
            await session_mgr.save_exchange(
                session_id=session.session_id,
                user_message=request.message,
                assistant_response=response_text,
                detected_intent="unknown",
                confidence=confidence
            )
            
            latency = time.time() - start_time
            logger.info(
                f"Hotel: {hotel_ctx.slug} | Intent: unknown (fallback) | Confidence: {confidence:.2f} | Latency: {latency:.4f}s"
            )
            
            return ChatResponse(
                response=formatter.format(response_text, request.channel),
                intent="unknown",
                confidence=confidence,
                session_id=session.session_id,
                is_enriched=is_enriched_flag
            )
        
        # 10. Route ke workflow
        handler_map = {
            "faq":              FAQHandler(db),
            "booking_inquiry":  BookingHandler(db),
            "booking_request":  BookingHandler(db),
            "cancellation":     BookingHandler(db),  # Reroute pembatalan ke BookingHandler
            "complaint":        ComplaintHandler(db),
            "refund":           RefundHandler(db),
            "refund_inquiry":   RefundHandler(db),
            "reschedule":       RescheduleHandler(db),
            "amenities":        ComplaintHandler(db),  # Sementara dialihkan ke complaint
        }
        
        handler = handler_map.get(intent)
        
        if intent == "greeting" and not has_active_workflow:
            llm = get_llm_client()
            response_text = await handle_greeting(ctx, llm)
        elif handler:
            response_text = await handler.handle(ctx)
        else:
            response_text = fallback.get_fallback_response()
            intent = "unknown"
        
        # 11. Format
        formatted = formatter.format(response_text, request.channel, intent)
        
        # 12. Save
        await session_mgr.save_exchange(
            session_id=session.session_id,
            user_message=request.message,
            assistant_response=formatted,
            detected_intent=intent,
            confidence=confidence
        )
        
        latency = time.time() - start_time
        logger.info(
            f"Hotel: {hotel_ctx.slug} | Intent: {intent} | Confidence: {confidence:.2f} | Latency: {latency:.4f}s"
        )
        
        # 13. Return
        return ChatResponse(
            response=formatted,
            intent=intent,
            confidence=confidence,
            session_id=session.session_id,
            is_enriched=is_enriched_flag
        )
        
    except Exception as e:
        logger.error(f"Error pada pemrosesan chat endpoint: {str(e)}", exc_info=True)
        # Sesuai Aturan Penting #4: kalau ada error return SYSTEM_ERROR template
        error_msg = SYSTEM_ERROR.format(phone="(021) 1234-5678")
        return ChatResponse(
            response=formatter.format(error_msg, request.channel),
            intent="error",
            confidence=0.0,
            session_id=session_id_str,
            is_enriched=is_enriched_flag
        )
