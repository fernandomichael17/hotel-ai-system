from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import uuid
from ..models import Session, ConversationMessage

class SessionRepository:
    """Repository for Session model."""
    
    def __init__(self, db_session: AsyncSession):
        self.session = db_session
        
    async def find_active(self, user_identifier: str, hotel_id: str) -> Optional[Session]:
        stmt = select(Session).where(
            Session.user_identifier == user_identifier,
            Session.hotel_id == uuid.UUID(hotel_id),
            Session.status == "active"
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
        
    async def create(self, data: dict) -> Session:
        db_session = Session(**data)
        self.session.add(db_session)
        await self.session.commit()
        await self.session.refresh(db_session)
        return db_session
        
    async def update_status(self, session_id: str, status: str) -> Session:
        stmt = select(Session).where(Session.id == uuid.UUID(session_id))
        result = await self.session.execute(stmt)
        db_session = result.scalar_one()
        db_session.status = status
        await self.session.commit()
        await self.session.refresh(db_session)
        return db_session
        
    async def add_message(self, data: dict) -> ConversationMessage:
        msg = ConversationMessage(**data)
        self.session.add(msg)
        await self.session.commit()
        await self.session.refresh(msg)
        return msg
        
    async def get_messages(self, session_id: str, limit: int = 10) -> List[ConversationMessage]:
        stmt = select(ConversationMessage).where(
            ConversationMessage.session_id == uuid.UUID(session_id)
        ).order_by(ConversationMessage.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        # Reverse to get chronological order
        return list(result.scalars().all())[::-1]
