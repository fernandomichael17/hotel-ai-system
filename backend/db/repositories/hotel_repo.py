from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional
import uuid
from ..models import Hotel

class HotelRepository:
    """Repository for Hotel model."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def find_by_id(self, hotel_id: str) -> Optional[Hotel]:
        stmt = select(Hotel).where(Hotel.id == uuid.UUID(hotel_id))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
        
    async def find_by_wa_number(self, wa_number: str) -> Optional[Hotel]:
        stmt = select(Hotel).where(Hotel.wa_number == wa_number)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
        
    async def find_by_slug(self, slug: str) -> Optional[Hotel]:
        stmt = select(Hotel).where(Hotel.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
        
    async def create(self, data: dict) -> Hotel:
        hotel = Hotel(**data)
        self.session.add(hotel)
        await self.session.commit()
        await self.session.refresh(hotel)
        return hotel
