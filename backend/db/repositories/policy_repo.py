from uuid import UUID
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import HotelPolicy
from backend.config import settings

class PolicyRepository:
    """Repository untuk mengelola kebijakan fleksibel (HotelPolicy) per hotel."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def find_by_id(self, id: UUID) -> Optional[HotelPolicy]:
        """Mencari kebijakan berdasarkan UUID."""
        result = await self.db.execute(
            select(HotelPolicy).where(HotelPolicy.id == id)
        )
        return result.scalar_one_or_none()
        
    async def find_by_type(self, hotel_id: UUID, policy_type: str) -> Optional[HotelPolicy]:
        """Mencari kebijakan aktif berdasarkan tipenya di hotel tertentu."""
        result = await self.db.execute(
            select(HotelPolicy).where(
                HotelPolicy.hotel_id == hotel_id,
                HotelPolicy.policy_type == policy_type,
                HotelPolicy.is_active == True
            )
        )
        return result.scalar_one_or_none()
        
    async def find_all_by_hotel(self, hotel_id: UUID) -> List[HotelPolicy]:
        """Mendapatkan daftar seluruh kebijakan aktif milik hotel tertentu."""
        result = await self.db.execute(
            select(HotelPolicy).where(
                HotelPolicy.hotel_id == hotel_id,
                HotelPolicy.is_active == True
            )
        )
        return list(result.scalars().all())
        
    async def upsert(self, hotel_id: UUID, policy_type: str, rules: dict) -> HotelPolicy:
        """Menyimpan kebijakan baru atau memperbarui rules yang sudah terdaftar."""
        existing = await self.find_by_type(hotel_id, policy_type)
        if existing:
            existing.rules = rules
            existing.updated_at = datetime.utcnow()
            policy = existing
        else:
            policy = HotelPolicy(
                hotel_id=hotel_id,
                policy_type=policy_type,
                rules=rules,
                is_active=True
            )
            self.db.add(policy)
            
        await self.db.commit()
        await self.db.refresh(policy)
        return policy
        
    async def deactivate(self, hotel_id: UUID, policy_type: str) -> bool:
        """Menonaktifkan (soft delete) kebijakan hotel tertentu."""
        stmt = update(HotelPolicy).where(
            HotelPolicy.hotel_id == hotel_id,
            HotelPolicy.policy_type == policy_type
        ).values(
            is_active=False,
            updated_at=datetime.utcnow()
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

def get_policy_repo(db: AsyncSession) -> PolicyRepository:
    """Helper Dependency Injection untuk PolicyRepository di FastAPI."""
    return PolicyRepository(db)
