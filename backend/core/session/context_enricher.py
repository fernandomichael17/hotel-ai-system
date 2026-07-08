from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional
from backend.core.channel.schemas import GuestContext
from backend.db.repositories.guest_stay_repo import (
    GuestStayRepository
)

class ContextEnricher:
    """Enricher konteks percakapan untuk mendeteksi apakah tamu sedang aktif menginap (check-in)."""
    
    def __init__(self, db: AsyncSession):
        self.repo = GuestStayRepository(db)
        
    async def enrich(
        self,
        user_identifier: str,
        hotel_id: str
    ) -> Optional[GuestContext]:
        """Melacak status stay aktif tamu berdasarkan nomor WhatsApp pengirim."""
        hotel_uuid = UUID(hotel_id)
        stay = await self.repo.find_active_by_wa(
            wa_number=user_identifier,
            hotel_id=hotel_uuid
        )
        
        if not stay:
            return None
            
        return GuestContext(
            guest_name=stay.guest_name,
            room_number=stay.room_number,
            check_in=str(stay.check_in_date) if stay.check_in_date else None,
            check_out=str(stay.check_out_date) if stay.check_out_date else None,
            is_checked_in=True,
            hms_booking_id=stay.hms_booking_id
        )
        
    async def enrich_by_room(
        self,
        room_number: str,
        hotel_id: str
    ) -> Optional[GuestContext]:
        """Melacak status stay aktif tamu berdasarkan nomor kamar (skenario fallback)."""
        hotel_uuid = UUID(hotel_id)
        stay = await self.repo.find_by_room(
            room_number=room_number,
            hotel_id=hotel_uuid
        )
        
        if not stay:
            return None
            
        return GuestContext(
            guest_name=stay.guest_name,
            room_number=stay.room_number,
            check_in=str(stay.check_in_date) if stay.check_in_date else None,
            check_out=str(stay.check_out_date) if stay.check_out_date else None,
            is_checked_in=True,
            hms_booking_id=stay.hms_booking_id
        )
