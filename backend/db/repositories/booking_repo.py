from uuid import UUID
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import BookingDraft
from backend.config import settings

class BookingRepository:
    """Repository untuk mengelola draf pemesanan kamar (BookingDraft)."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def find_by_id(self, id: UUID) -> Optional[BookingDraft]:
        """Mencari draf booking berdasarkan UUID."""
        result = await self.db.execute(
            select(BookingDraft).where(BookingDraft.id == id)
        )
        return result.scalar_one_or_none()
        
    async def find_by_session(self, session_id: UUID) -> List[BookingDraft]:
        """Mencari semua draf booking dalam satu sesi percakapan."""
        result = await self.db.execute(
            select(BookingDraft)
            .where(BookingDraft.session_id == session_id)
            .order_by(BookingDraft.created_at.desc())
        )
        return list(result.scalars().all())
        
    async def find_by_hotel(self, hotel_id: UUID, status: Optional[str] = None) -> List[BookingDraft]:
        """Mencari draf booking di hotel tertentu, dapat difilter status."""
        stmt = select(BookingDraft).where(BookingDraft.hotel_id == hotel_id)
        if status is not None:
            stmt = stmt.where(BookingDraft.status == status)
        stmt = stmt.order_by(BookingDraft.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
        
    async def find_by_wa_number(self, wa_number: str, hotel_id: UUID) -> List[BookingDraft]:
        """Mencari histori draf booking tamu berdasarkan nomor WhatsApp di hotel tertentu."""
        result = await self.db.execute(
            select(BookingDraft)
            .where(BookingDraft.wa_number == wa_number, BookingDraft.hotel_id == hotel_id)
            .order_by(BookingDraft.created_at.desc())
        )
        return list(result.scalars().all())
        
    async def find_active_draft(self, session_id: UUID) -> Optional[BookingDraft]:
        """Mengambil draf booking yang sedang berjalan (status='draft') dalam sesi ini."""
        result = await self.db.execute(
            select(BookingDraft)
            .where(BookingDraft.session_id == session_id, BookingDraft.status == "draft")
            .order_by(BookingDraft.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
        
    async def create(self, hotel_id: UUID, session_id: UUID, **kwargs) -> BookingDraft:
        """Membuat draf booking baru."""
        booking = BookingDraft(
            hotel_id=hotel_id,
            session_id=session_id,
            **kwargs
        )
        self.db.add(booking)
        await self.db.commit()
        await self.db.refresh(booking)
        return booking
        
    async def update_params(self, booking_id: UUID, **kwargs) -> Optional[BookingDraft]:
        """Memperbarui kolom data pada draf booking tertentu."""
        booking = await self.find_by_id(booking_id)
        if booking:
            for key, val in kwargs.items():
                if hasattr(booking, key):
                    setattr(booking, key, val)
            booking.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(booking)
        return booking
        
    async def update_status(self, booking_id: UUID, status: str, 
                            hms_booking_id: Optional[str] = None) -> Optional[BookingDraft]:
        """Mengupdate status draf booking serta HMS ID jika ada."""
        booking = await self.find_by_id(booking_id)
        if booking:
            booking.status = status
            if hms_booking_id is not None:
                booking.hms_booking_id = hms_booking_id
            booking.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(booking)
        return booking

def get_booking_repo(db: AsyncSession) -> BookingRepository:
    """Helper Dependency Injection untuk BookingRepository di FastAPI."""
    return BookingRepository(db)
