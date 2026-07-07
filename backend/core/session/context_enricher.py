from typing import Optional
from ..channel.schemas import GuestContext
from ...db.database import AsyncSessionLocal
from ...db.repositories.guest_stay_repo import GuestStayRepository

class ContextEnricher:
    """Enrich context with guest data."""
    
    async def enrich(self, user_identifier: str, hotel_id: str) -> Optional[GuestContext]:
        async with AsyncSessionLocal() as db_session:
            repo = GuestStayRepository(db_session)
            stay = await repo.find_active(user_identifier, hotel_id)
            
            if stay:
                return GuestContext(
                    guest_name=stay.guest_name,
                    room_number=stay.room_number,
                    check_in=str(stay.check_in_date),
                    check_out=str(stay.check_out_date),
                    is_checked_in=True
                )
                
            return None
