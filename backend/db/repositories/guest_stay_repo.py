from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid
from ..models import GuestStay

class GuestStayRepository:
    """Repository for GuestStay model."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def find_active(self, wa_number: str, hotel_id: str) -> Optional[GuestStay]:
        stmt = select(GuestStay).where(
            GuestStay.wa_number == wa_number,
            GuestStay.hotel_id == uuid.UUID(hotel_id),
            GuestStay.status == "checked_in"
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
        
    async def create(self, data: dict) -> GuestStay:
        stay = GuestStay(**data)
        self.session.add(stay)
        await self.session.commit()
        await self.session.refresh(stay)
        return stay
        
    async def update_status(self, stay_id: str, status: str) -> GuestStay:
        stmt = select(GuestStay).where(GuestStay.id == uuid.UUID(stay_id))
        result = await self.session.execute(stmt)
        stay = result.scalar_one()
        stay.status = status
        await self.session.commit()
        await self.session.refresh(stay)
        return stay
