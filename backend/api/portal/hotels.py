import re
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from uuid import UUID

from backend.db.database import get_db
from backend.api.portal.auth import (
    get_current_hotel, TokenData
)
from backend.core.guest.stay_manager import (
    StayManager
)
from backend.core.guest.schemas import (
    CheckInRequest, CheckOutRequest, GuestStayResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

class GuestStayListResponse(BaseModel):
    id: str
    guest_name: str
    wa_number: str
    room_number: str | None
    check_in_date: str | None
    check_out_date: str | None
    status: str
    booking_source: str

@router.get("/hotel/info")
async def get_hotel_info(
    current_hotel: TokenData = Depends(get_current_hotel),
    db: AsyncSession = Depends(get_db)
):
    """
    Mengambil profil dasar properti hotel yang sedang diakses.
    """
    from backend.db.repositories.hotel_repo import HotelRepository
    repo = HotelRepository(db)
    
    try:
        hotel = await repo.find_by_slug(current_hotel.hotel_slug)
    except Exception as e:
        logger.error(f"Gagal mengambil info hotel: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Gagal memproses data hotel")
        
    if not hotel:
        raise HTTPException(
            status_code=404,
            detail="Hotel tidak ditemukan"
        )
        
    return {
        "id": str(hotel.id),
        "name": hotel.name,
        "slug": hotel.slug,
        "wa_number": hotel.wa_number,
        "waha_session": hotel.waha_session,
        "is_active": hotel.is_active
    }

@router.get("/hotel/stays", response_model=list[GuestStayListResponse])
async def list_active_stays(
    current_hotel: TokenData = Depends(get_current_hotel),
    db: AsyncSession = Depends(get_db)
):
    """
    List semua tamu yang sedang aktif checked_in di hotel ini.
    """
    from sqlalchemy import select
    from backend.db.models import GuestStay
    
    try:
        result = await db.execute(
            select(GuestStay).where(
                GuestStay.hotel_id == UUID(current_hotel.hotel_id),
                GuestStay.status == "checked_in"
            ).order_by(GuestStay.created_at.desc())
        )
        stays = result.scalars().all()
    except Exception as e:
        logger.error(f"Gagal mengambil daftar stays: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Gagal memproses daftar stays")
        
    return [
        GuestStayListResponse(
            id=str(s.id),
            guest_name=s.guest_name,
            wa_number=s.wa_number,
            room_number=s.room_number,
            check_in_date=str(s.check_in_date) if s.check_in_date else None,
            check_out_date=str(s.check_out_date) if s.check_out_date else None,
            status=s.status,
            booking_source=s.booking_source
        )
        for s in stays
    ]

@router.post("/hotel/checkin")
async def manual_checkin(
    request: CheckInRequest,
    current_hotel: TokenData = Depends(get_current_hotel),
    db: AsyncSession = Depends(get_db)
):
    """
    Input check-in tamu secara manual oleh Front Office.
    """
    # 1. Override hotel_id dari JWT token untuk alasan keamanan tenant
    request.hotel_id = current_hotel.hotel_id
    
    # 2. Validasi tanggal
    if request.check_out_date <= request.check_in_date:
        raise HTTPException(
            status_code=400,
            detail="Tanggal check-out harus setelah check-in"
        )
        
    # 3. Validasi nomor WA (10-15 digit angka)
    if not re.match(r"^\d{10,15}$", request.wa_number):
        raise HTTPException(
            status_code=400,
            detail="Nomor WhatsApp tidak valid. Harus terdiri dari 10-15 digit angka."
        )
        
    try:
        stay_mgr = StayManager(db)
        result = await stay_mgr.check_in(request)
    except Exception as e:
        logger.error(f"Gagal melakukan manual check-in: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Gagal memproses check-in")
        
    return {
        "success": True,
        "message": f"Check-in berhasil untuk {result.guest_name}",
        "stay": result
    }

@router.post("/hotel/checkout")
async def manual_checkout(
    wa_number: str,
    current_hotel: TokenData = Depends(get_current_hotel),
    db: AsyncSession = Depends(get_db)
):
    """
    Checkout tamu secara manual dari dashboard admin.
    """
    # Validasi nomor WA
    if not re.match(r"^\d{10,15}$", wa_number):
        raise HTTPException(
            status_code=400,
            detail="Nomor WhatsApp tidak valid. Harus terdiri dari 10-15 digit angka."
        )
        
    req = CheckOutRequest(
        hotel_id=current_hotel.hotel_id,
        wa_number=wa_number
    )
    
    try:
        stay_mgr = StayManager(db)
        success = await stay_mgr.check_out(req)
    except Exception as e:
        logger.error(f"Gagal melakukan manual check-out untuk {wa_number}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Gagal memproses check-out")
        
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Tidak ada tamu aktif dengan nomor tersebut"
        )
        
    return {
        "success": True,
        "message": "Checkout berhasil"
    }

@router.get("/hotel/bookings")
async def list_pending_bookings(
    current_hotel: TokenData = Depends(get_current_hotel),
    db: AsyncSession = Depends(get_db)
):
    """
    Melihat draf pemesanan kamar yang masuk melalui chatbot untuk difollow up oleh tim sales.
    """
    from backend.db.repositories.booking_repo import BookingRepository
    
    try:
        repo = BookingRepository(db)
        bookings = await repo.find_by_hotel(
            hotel_id=UUID(current_hotel.hotel_id),
            status=None  # Mengambil seluruh status bookings
        )
    except Exception as e:
        logger.error(f"Gagal mengambil daftar bookings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Gagal memproses daftar bookings")
        
    return {
        "total": len(bookings),
        "bookings": [
            {
                "id": str(b.id),
                "guest_name": b.guest_name,
                "wa_number": b.wa_number,
                "room_type": b.room_type,
                "check_in": b.check_in_date,
                "check_out": b.check_out_date,
                "num_guests": b.num_guests,
                "special_request": b.special_request,
                "status": b.status,
                "created_at": str(b.created_at)
            }
            for b in bookings
        ]
    }
