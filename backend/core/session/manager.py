from datetime import datetime, timedelta, UTC
from typing import List, Optional
import uuid
from ...db.database import AsyncSessionLocal
from ...db.repositories.session_repo import SessionRepository
from ...db.models import Session, ConversationMessage

class SessionManager:
    """Manager for user conversation sessions."""
    
    async def get_or_create(self, user_identifier: str, hotel_id: str, channel: str) -> Session:
        async with AsyncSessionLocal() as db_session:
            repo = SessionRepository(db_session)
            session = await repo.find_active(user_identifier, hotel_id)
            
            if session:
                return session
                
            new_session = await repo.create({
                "hotel_id": uuid.UUID(hotel_id),
                "user_identifier": user_identifier,
                "channel": channel,
                "status": "active"
            })
            return new_session

    async def get_history(self, session_id: str, max_messages: int = 10) -> List[ConversationMessage]:
        async with AsyncSessionLocal() as db_session:
            repo = SessionRepository(db_session)
            return await repo.get_messages(session_id, limit=max_messages)

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        intent: Optional[str] = None,
        confidence: Optional[float] = None
    ) -> ConversationMessage:
        async with AsyncSessionLocal() as db_session:
            repo = SessionRepository(db_session)
            msg = await repo.add_message({
                "session_id": uuid.UUID(session_id),
                "role": role,
                "content": content,
                "detected_intent": intent,
                "confidence": confidence
            })
            
            # Update session updated_at
            # (Handled by model's onupdate)
            return msg

    async def expire_old_sessions(self):
        """Update status -> 'expired' untuk session yang updated_at > 2 jam"""
        # Placeholder implementation
        pass
