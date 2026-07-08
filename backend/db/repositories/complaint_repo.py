from uuid import UUID
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import ComplaintTicket
from backend.config import settings

class ComplaintRepository:
    """Repository untuk mengelola tiket keluhan pelanggan (ComplaintTicket)."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def find_by_id(self, id: UUID) -> Optional[ComplaintTicket]:
        """Mencari tiket keluhan berdasarkan UUID."""
        result = await self.db.execute(
            select(ComplaintTicket).where(ComplaintTicket.id == id)
        )
        return result.scalar_one_or_none()
        
    async def find_by_hotel(self, hotel_id: UUID, status: Optional[str] = None, 
                            department: Optional[str] = None) -> List[ComplaintTicket]:
        """Mencari keluhan di hotel tertentu, opsional difilter status dan departemen."""
        stmt = select(ComplaintTicket).where(ComplaintTicket.hotel_id == hotel_id)
        if status is not None:
            stmt = stmt.where(ComplaintTicket.status == status)
        if department is not None:
            stmt = stmt.where(ComplaintTicket.department == department)
        stmt = stmt.order_by(ComplaintTicket.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
        
    async def find_by_session(self, session_id: UUID) -> List[ComplaintTicket]:
        """Mencari semua tiket keluhan dalam satu sesi percakapan."""
        result = await self.db.execute(
            select(ComplaintTicket)
            .where(ComplaintTicket.session_id == session_id)
            .order_by(ComplaintTicket.created_at.desc())
        )
        return list(result.scalars().all())
        
    async def find_open_by_room(self, room_number: str, hotel_id: UUID) -> List[ComplaintTicket]:
        """Mendapatkan keluhan belum selesai (status open/in_progress) di kamar tertentu."""
        result = await self.db.execute(
            select(ComplaintTicket).where(
                ComplaintTicket.room_number == room_number,
                ComplaintTicket.hotel_id == hotel_id,
                ComplaintTicket.status.in_(["open", "in_progress"])
            )
        )
        return list(result.scalars().all())
        
    async def create(self, hotel_id: UUID, session_id: UUID, description: str, **kwargs) -> ComplaintTicket:
        """Membuat tiket keluhan baru."""
        ticket = ComplaintTicket(
            hotel_id=hotel_id,
            session_id=session_id,
            description=description,
            **kwargs
        )
        self.db.add(ticket)
        await self.db.commit()
        await self.db.refresh(ticket)
        return ticket
        
    async def update_status(self, ticket_id: UUID, status: str, 
                            resolved_at: Optional[datetime] = None) -> Optional[ComplaintTicket]:
        """Mengubah status tiket keluhan."""
        ticket = await self.find_by_id(ticket_id)
        if ticket:
            ticket.status = status
            if resolved_at is not None:
                ticket.resolved_at = resolved_at
            elif status == "resolved":
                ticket.resolved_at = datetime.utcnow()
            ticket.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(ticket)
        return ticket
        
    async def update_department(self, ticket_id: UUID, department: str) -> Optional[ComplaintTicket]:
        """Mendistribusikan tiket keluhan ke departemen lain."""
        ticket = await self.find_by_id(ticket_id)
        if ticket:
            ticket.department = department
            ticket.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(ticket)
        return ticket

def get_complaint_repo(db: AsyncSession) -> ComplaintRepository:
    """Helper Dependency Injection untuk ComplaintRepository di FastAPI."""
    return ComplaintRepository(db)
