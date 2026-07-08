from uuid import UUID
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import Hotel
from backend.config import settings

class HotelRepository:
    """Repository untuk mengelola data master Hotel."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def find_by_id(self, id: UUID) -> Optional[Hotel]:
        """Mencari hotel berdasarkan UUID."""
        result = await self.db.execute(
            select(Hotel).where(Hotel.id == id)
        )
        return result.scalar_one_or_none()
        
    async def find_by_slug(self, slug: str) -> Optional[Hotel]:
        """Mencari hotel aktif berdasarkan slug."""
        result = await self.db.execute(
            select(Hotel).where(Hotel.slug == slug, Hotel.is_active == True)
        )
        return result.scalar_one_or_none()
        
    async def find_by_wa_number(self, wa_number: str) -> Optional[Hotel]:
        """Mencari hotel aktif berdasarkan nomor WhatsApp."""
        result = await self.db.execute(
            select(Hotel).where(Hotel.wa_number == wa_number, Hotel.is_active == True)
        )
        return result.scalar_one_or_none()
        
    async def find_by_waha_session(self, session_name: str) -> Optional[Hotel]:
        """Mencari hotel aktif berdasarkan nama session WAHA."""
        result = await self.db.execute(
            select(Hotel).where(Hotel.waha_session == session_name, Hotel.is_active == True)
        )
        return result.scalar_one_or_none()
        
    async def find_all_active(self) -> List[Hotel]:
        """Mendapatkan seluruh hotel aktif, diurutkan berdasarkan nama secara alfabetis (ASC)."""
        result = await self.db.execute(
            select(Hotel).where(Hotel.is_active == True).order_by(Hotel.name.asc())
        )
        return list(result.scalars().all())
        
    async def create(self, name: str, slug: str, wa_number: Optional[str] = None, waha_session: Optional[str] = None) -> Hotel:
        """Membuat master data hotel baru."""
        hotel = Hotel(
            name=name,
            slug=slug,
            wa_number=wa_number,
            waha_session=waha_session
        )
        self.db.add(hotel)
        await self.db.commit()
        await self.db.refresh(hotel)
        return hotel
        
    async def update_wa_number(self, hotel_id: UUID, wa_number: str, waha_session: str) -> Optional[Hotel]:
        """Mengupdate nomor WA dan session WAHA milik hotel tertentu."""
        hotel = await self.find_by_id(hotel_id)
        if hotel:
            hotel.wa_number = wa_number
            hotel.waha_session = waha_session
            await self.db.commit()
            await self.db.refresh(hotel)
        return hotel

def get_hotel_repo(db: AsyncSession) -> HotelRepository:
    """Helper Dependency Injection untuk HotelRepository di FastAPI."""
    return HotelRepository(db)
