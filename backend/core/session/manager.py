from uuid import UUID
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.session.schemas import (
    SessionData, MessageHistory
)
from backend.db.repositories.session_repo import (
    SessionRepository
)
from backend.core.workflows.booking.schemas import BookingState

MAX_HISTORY = 10  # Maksimal pesan ke LLM

class SessionManager:
    """Manajer sesi untuk melacak dan menyimpan histori percakapan tamu."""
    
    _booking_states: dict = {}
    
    def __init__(self, db: AsyncSession):
        self.repo = SessionRepository(db)
        
    async def get_or_create(
        self,
        user_identifier: str,
        hotel_id: str,
        channel: str = "web"
    ) -> SessionData:
        """Mendapatkan sesi aktif (dan reset timer expires_at) atau men-generate sesi baru."""
        hotel_uuid = UUID(hotel_id)
        session = await self.repo.find_active(user_identifier, hotel_uuid)
        
        if session:
            session = await self.repo.touch(session.id)
        else:
            session = await self.repo.create(user_identifier, hotel_uuid, channel)
            
        db_messages = await self.repo.get_messages(session.id, limit=MAX_HISTORY)
        history = [
            MessageHistory(
                role=msg.role,
                content=msg.content,
                intent=msg.detected_intent,
                created_at=msg.created_at.isoformat() if msg.created_at else None
            )
            for msg in db_messages
        ]
        
        return SessionData(
            session_id=str(session.id),
            hotel_id=str(session.hotel_id),
            user_identifier=session.user_identifier,
            channel=session.channel,
            status=session.status,
            history=history,
            created_at=session.created_at.isoformat() if session.created_at else "",
            expires_at=session.expires_at.isoformat() if session.expires_at else None
        )
        
    async def get_history_for_llm(
        self,
        session_id: str
    ) -> List[dict]:
        """Mengambil pesan user dan assistant terformat untuk input konteks LLM."""
        session_uuid = UUID(session_id)
        db_messages = await self.repo.get_messages(session_uuid, limit=MAX_HISTORY)
        
        llm_history = []
        for msg in db_messages:
            if msg.role in ["user", "assistant"]:
                llm_history.append({
                    "role": msg.role,
                    "content": msg.content
                })
        return llm_history
        
    async def save_exchange(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        detected_intent: Optional[str] = None,
        confidence: Optional[float] = None
    ) -> None:
        """Menyimpan pesan pengguna dan bot secara asinkron ke database."""
        session_uuid = UUID(session_id)
        await self.repo.add_message(
            session_id=session_uuid,
            role="user",
            content=user_message
        )
        await self.repo.add_message(
            session_id=session_uuid,
            role="assistant",
            content=assistant_response,
            detected_intent=detected_intent,
            confidence=confidence
        )
        
    async def expire_sessions(self) -> int:
        """Mematikan semua sesi aktif yang telah melewati batas kedaluwarsa waktu."""
        return await self.repo.expire_old_sessions()

    async def get_booking_state(
        self,
        session_id: str
    ) -> BookingState | None:
        """
        Mengambil BookingState in-memory berdasarkan session_id.
        """
        state_dict = self._booking_states.get(session_id)
        if state_dict is None:
            return None
        return BookingState.model_validate(state_dict)

    async def save_booking_state(
        self,
        session_id: str,
        state: BookingState
    ) -> None:
        """
        Menyimpan BookingState in-memory berdasarkan session_id.
        """
        self._booking_states[session_id] = state.model_dump()

    async def clear_booking_state(
        self,
        session_id: str
    ) -> None:
        """
        Menghapus BookingState in-memory berdasarkan session_id.
        """
        if session_id in self._booking_states:
            del self._booking_states[session_id]
