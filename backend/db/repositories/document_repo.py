from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
import uuid
from ..models import Document

class DocumentRepository:
    """Repository for Document model."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def create(self, data: dict) -> Document:
        doc = Document(**data)
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)
        return doc
        
    async def find_by_hotel(self, hotel_id: str) -> List[Document]:
        stmt = select(Document).where(Document.hotel_id == uuid.UUID(hotel_id))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
        
    async def delete_by_hotel(self, hotel_id: str) -> int:
        stmt = delete(Document).where(Document.hotel_id == uuid.UUID(hotel_id))
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount
