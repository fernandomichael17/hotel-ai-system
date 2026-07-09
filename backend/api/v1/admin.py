from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.database import get_db

router = APIRouter()

@router.get("/admin/hotels")
async def list_hotels(
    db: AsyncSession = Depends(get_db)
):
    """List semua hotel yang aktif"""
    from backend.db.repositories.hotel_repo import HotelRepository
    repo = HotelRepository(db)
    hotels = await repo.find_all_active()
    return {
        "hotels": [
            {
                "id": str(h.id),
                "name": h.name,
                "slug": h.slug,
                "wa_number": h.wa_number,
                "waha_session": h.waha_session
            }
            for h in hotels
        ]
    }

@router.get("/admin/sessions")
async def list_sessions(
    hotel_id: str | None = None,
    db: AsyncSession = Depends(get_db)
):
    """List session aktif"""
    from sqlalchemy import select
    from backend.db.models import Session
    
    query = select(Session).where(
        Session.status == "active"
    )
    if hotel_id:
        from uuid import UUID
        from fastapi import HTTPException
        try:
            hotel_uuid = UUID(hotel_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid hotel_id UUID format")
        query = query.where(
            Session.hotel_id == hotel_uuid
        )
    
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    return {
        "total": len(sessions),
        "sessions": [
            {
                "id": str(s.id),
                "user": s.user_identifier,
                "channel": s.channel,
                "created_at": str(s.created_at)
            }
            for s in sessions
        ]
    }
