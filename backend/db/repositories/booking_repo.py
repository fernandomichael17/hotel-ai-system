from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid
from ..models import BookingDraft

class BookingRepository:
    """Repository for BookingDraft model."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def create(self, data: dict) -> BookingDraft:
        booking = BookingDraft(**data)
        self.session.add(booking)
        await self.session.commit()
        await self.session.refresh(booking)
        return booking
        
    async def find_by_session(self, session_id: str) -> List[BookingDraft]:
        stmt = select(BookingDraft).where(BookingDraft.session_id == uuid.UUID(session_id))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
        
    async def update_status(self, booking_id: str, status: str) -> BookingDraft:
        stmt = select(BookingDraft).where(BookingDraft.id == uuid.UUID(booking_id))
        result = await self.session.execute(stmt)
        booking = result.scalar_one()
        booking.status = status
        await self.session.commit()
        await self.session.refresh(booking)
        return booking
