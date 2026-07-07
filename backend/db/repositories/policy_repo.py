from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid
from ..models import HotelPolicy

class PolicyRepository:
    """Repository for HotelPolicy model."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def find_by_hotel_and_type(self, hotel_id: str, policy_type: str) -> Optional[HotelPolicy]:
        stmt = select(HotelPolicy).where(
            HotelPolicy.hotel_id == uuid.UUID(hotel_id),
            HotelPolicy.policy_type == policy_type,
            HotelPolicy.is_active == True
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
        
    async def upsert(self, data: dict) -> HotelPolicy:
        # Check if exists
        stmt = select(HotelPolicy).where(
            HotelPolicy.hotel_id == uuid.UUID(data['hotel_id']),
            HotelPolicy.policy_type == data['policy_type']
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.rules = data['rules']
            existing.is_active = data.get('is_active', True)
            policy = existing
        else:
            policy = HotelPolicy(**data)
            self.session.add(policy)
            
        await self.session.commit()
        await self.session.refresh(policy)
        return policy
