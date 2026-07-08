from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime, date, timedelta
from typing import Optional
from backend.core.guest.schemas import (
    CheckInRequest,
    CheckOutRequest,
    GuestStayResponse
)
from backend.db.repositories.guest_stay_repo import (
    GuestStayRepository
)
from backend.db.models import GuestStay

class StayManager:
    """Stay manager untuk memproses reservasi check-in dan checkout tamu."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = GuestStayRepository(db)
        
    async def check_in(
        self,
        req: CheckInRequest
    ) -> GuestStayResponse:
        """Memproses check-in tamu dan mematikan inap aktif lama (jika terdeteksi double check-in)."""
        hotel_uuid = UUID(req.hotel_id)
        
        # 1. Checkout status lama jika terjadi double check-in
        existing_stay = await self.repo.find_active_by_wa(req.wa_number, hotel_uuid)
        if existing_stay:
            await self.repo.checkout(existing_stay.id)
            
        # 2. Parse str date ke datetime.date
        try:
            in_date = datetime.strptime(req.check_in_date, "%Y-%m-%d").date()
        except ValueError:
            in_date = date.today()
            
        try:
            out_date = datetime.strptime(req.check_out_date, "%Y-%m-%d").date()
        except ValueError:
            out_date = date.today() + timedelta(days=1)
            
        # 3. Buat GuestStay baru
        stay = await self.repo.create(
            hotel_id=hotel_uuid,
            wa_number=req.wa_number,
            guest_name=req.guest_name,
            room_number=req.room_number,
            check_in_date=in_date,
            check_out_date=out_date,
            booking_source=req.booking_source,
            hms_booking_id=req.hms_booking_id
        )
        
        return GuestStayResponse(
            id=str(stay.id),
            hotel_id=str(stay.hotel_id),
            wa_number=stay.wa_number,
            guest_name=stay.guest_name,
            room_number=stay.room_number,
            check_in_date=str(stay.check_in_date) if stay.check_in_date else None,
            check_out_date=str(stay.check_out_date) if stay.check_out_date else None,
            status=stay.status,
            booking_source=stay.booking_source
        )
        
    async def check_out(
        self,
        req: CheckOutRequest
    ) -> bool:
        """Melakukan checkout tamu inap secara manual."""
        hotel_uuid = UUID(req.hotel_id)
        stay = await self.repo.find_active_by_wa(req.wa_number, hotel_uuid)
        
        if not stay:
            return False
            
        await self.repo.checkout(stay.id)
        return True
        
    async def get_active_stay(
        self,
        wa_number: str,
        hotel_id: str
    ) -> Optional[GuestStayResponse]:
        """Mendapatkan stay aktif checked-in tamu berdasarkan nomor WhatsApp."""
        hotel_uuid = UUID(hotel_id)
        stay = await self.repo.find_active_by_wa(wa_number, hotel_uuid)
        
        if not stay:
            return None
            
        return GuestStayResponse(
            id=str(stay.id),
            hotel_id=str(stay.hotel_id),
            wa_number=stay.wa_number,
            guest_name=stay.guest_name,
            room_number=stay.room_number,
            check_in_date=str(stay.check_in_date) if stay.check_in_date else None,
            check_out_date=str(stay.check_out_date) if stay.check_out_date else None,
            status=stay.status,
            booking_source=stay.booking_source
        )
        
    async def auto_checkout_expired(self) -> int:
        """Menyelesaikan inap (checkout) secara otomatis jika tanggal check_out terlampaui."""
        today = date.today()
        stmt = select(GuestStay).where(
            GuestStay.status == "checked_in",
            GuestStay.check_out_date < today
        )
        result = await self.db.execute(stmt)
        expired_stays = result.scalars().all()
        
        count = 0
        for stay in expired_stays:
            stay.status = "checked_out"
            stay.updated_at = datetime.utcnow()
            count += 1
            
        if count > 0:
            await self.db.commit()
            
        return count
