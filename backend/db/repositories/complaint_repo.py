from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid
from ..models import ComplaintTicket

class ComplaintRepository:
    """Repository for ComplaintTicket model."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def create(self, data: dict) -> ComplaintTicket:
        ticket = ComplaintTicket(**data)
        self.session.add(ticket)
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket
        
    async def find_by_hotel(self, hotel_id: str) -> List[ComplaintTicket]:
        stmt = select(ComplaintTicket).where(ComplaintTicket.hotel_id == uuid.UUID(hotel_id))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
        
    async def update_status(self, ticket_id: str, status: str) -> ComplaintTicket:
        stmt = select(ComplaintTicket).where(ComplaintTicket.id == uuid.UUID(ticket_id))
        result = await self.session.execute(stmt)
        ticket = result.scalar_one()
        ticket.status = status
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket
