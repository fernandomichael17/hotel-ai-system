from uuid import UUID
from datetime import datetime, date, timedelta
from typing import Optional, List
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import Session, ConversationMessage
from backend.config import settings

class SessionRepository:
    """Repository untuk mengelola sesi percakapan percakapan dan pesan tamu."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def find_by_id(self, id: UUID) -> Optional[Session]:
        """Mencari sesi berdasarkan UUID."""
        result = await self.db.execute(
            select(Session).where(Session.id == id)
        )
        return result.scalar_one_or_none()
        
    async def find_active(self, user_identifier: str, hotel_id: UUID) -> Optional[Session]:
        """Mencari sesi aktif yang belum kadaluwarsa untuk tamu tertentu."""
        now = datetime.utcnow()
        result = await self.db.execute(
            select(Session).where(
                Session.user_identifier == user_identifier,
                Session.hotel_id == hotel_id,
                Session.status == "active",
                (Session.expires_at == None) | (Session.expires_at > now)
            ).order_by(Session.created_at.desc()).limit(1).with_for_update()
        )
        return result.scalar_one_or_none()
        
    async def create(self, user_identifier: str, hotel_id: UUID, channel: str = "whatsapp") -> Session:
        """Membuat sesi baru dengan masa kedaluwarsa 2 jam sejak dibuat."""
        expires_at = datetime.utcnow() + timedelta(hours=2)
        session = Session(
            user_identifier=user_identifier,
            hotel_id=hotel_id,
            channel=channel,
            status="active",
            expires_at=expires_at
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session
        
    async def update_status(self, session_id: UUID, status: str) -> Optional[Session]:
        """Mengupdate status sesi percakapan tamu."""
        session = await self.find_by_id(session_id)
        if session:
            session.status = status
            session.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(session)
        return session
        
    async def touch(self, session_id: UUID) -> Optional[Session]:
        """Memperpanjang masa kedaluwarsa sesi aktif tamu selama 2 jam ke depan."""
        session = await self.find_by_id(session_id)
        if session:
            session.updated_at = datetime.utcnow()
            session.expires_at = datetime.utcnow() + timedelta(hours=2)
            await self.db.commit()
            await self.db.refresh(session)
        return session
        
    async def expire_old_sessions(self) -> int:
        """Mengubah semua sesi aktif yang telah melewati batas waktu menjadi 'expired'."""
        now = datetime.utcnow()
        stmt = update(Session).where(
            Session.status == "active",
            Session.expires_at < now
        ).values(status="expired")
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount
        
    async def add_message(self, session_id: UUID, role: str, content: str, 
                          detected_intent: Optional[str] = None, confidence: Optional[float] = None) -> ConversationMessage:
        """Menyimpan pesan percakapan baru (dari tamu maupun bot)."""
        message = ConversationMessage(
            session_id=session_id,
            role=role,
            content=content,
            detected_intent=detected_intent,
            confidence=confidence
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message
        
    async def get_messages(self, session_id: UUID, limit: int = 10) -> List[ConversationMessage]:
        """Mendapatkan daftar pesan terakhir dalam sesi secara urutan kronologis (ASC)."""
        result = await self.db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())[::-1]

def get_session_repo(db: AsyncSession) -> SessionRepository:
    """Helper Dependency Injection untuk SessionRepository di FastAPI."""
    return SessionRepository(db)
