from uuid import UUID
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import GuestStay
from backend.config import settings

class GuestStayRepository:
    """Repository paling kritis untuk enriched session untuk melacak data checked_in tamu."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def find_by_id(self, id: UUID) -> Optional[GuestStay]:
        """Mencari data inap berdasarkan UUID."""
        result = await self.db.execute(
            select(GuestStay).where(GuestStay.id == id)
        )
        return result.scalar_one_or_none()
        
    async def find_active_by_wa(self, wa_number: str, hotel_id: UUID) -> Optional[GuestStay]:
        """Mencari data inap checked-in tamu berdasarkan nomor WhatsApp."""
        result = await self.db.execute(
            select(GuestStay).where(
                GuestStay.wa_number == wa_number,
                GuestStay.hotel_id == hotel_id,
                GuestStay.status == "checked_in"
            ).limit(1)
        )
        return result.scalar_one_or_none()
        
    async def find_by_room(self, room_number: str, hotel_id: UUID) -> Optional[GuestStay]:
        """Mencari data inap checked-in tamu berdasarkan nomor kamar."""
        result = await self.db.execute(
            select(GuestStay).where(
                GuestStay.room_number == room_number,
                GuestStay.hotel_id == hotel_id,
                GuestStay.status == "checked_in"
            ).limit(1)
        )
        return result.scalar_one_or_none()
        
    async def find_by_name_and_room(self, guest_name: str, room_number: str, hotel_id: UUID) -> Optional[GuestStay]:
        """Mencari data inap tamu aktif berdasarkan kecocokan nama (case-insensitive) dan nomor kamar."""
        result = await self.db.execute(
            select(GuestStay).where(
                func.lower(GuestStay.guest_name).like(func.lower(f"%{guest_name}%")),
                GuestStay.room_number == room_number,
                GuestStay.hotel_id == hotel_id,
                GuestStay.status == "checked_in"
            ).limit(1)
        )
        return result.scalar_one_or_none()
        
    async def create(self, hotel_id: UUID, wa_number: str, guest_name: str, room_number: str, 
                     check_in_date: date, check_out_date: date, booking_source: str = "manual_fo", 
                     hms_booking_id: Optional[str] = None) -> GuestStay:
        """Membuat data inap tamu baru."""
        stay = GuestStay(
            hotel_id=hotel_id,
            wa_number=wa_number,
            guest_name=guest_name,
            room_number=room_number,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            booking_source=booking_source,
            hms_booking_id=hms_booking_id,
            status="checked_in"
        )
        self.db.add(stay)
        await self.db.commit()
        await self.db.refresh(stay)
        return stay
        
    async def checkout(self, stay_id: UUID) -> Optional[GuestStay]:
        """Mengubah status tamu inap menjadi checked_out."""
        stay = await self.find_by_id(stay_id)
        if stay:
            stay.status = "checked_out"
            stay.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(stay)
        return stay
        
    async def checkout_by_wa(self, wa_number: str, hotel_id: UUID) -> int:
        """Melakukan checkout tamu menggunakan nomor WhatsApp."""
        stmt = update(GuestStay).where(
            GuestStay.wa_number == wa_number,
            GuestStay.hotel_id == hotel_id,
            GuestStay.status == "checked_in"
        ).values(
            status="checked_out",
            updated_at=datetime.utcnow()
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

def get_guest_stay_repo(db: AsyncSession) -> GuestStayRepository:
    """Helper Dependency Injection untuk GuestStayRepository di FastAPI."""
    return GuestStayRepository(db)
