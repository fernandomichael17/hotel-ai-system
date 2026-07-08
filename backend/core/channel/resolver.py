from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from backend.core.channel.schemas import HotelContext
from backend.db.repositories.hotel_repo import HotelRepository

DUMMY_HOTEL = HotelContext(
    hotel_id="00000000-0000-0000-0000-000000000001",
    hotel_name="Hotel Demo Metland",
    slug="demo",
    wa_number=None,
    waha_session=None
)

class ChannelResolver:
    """
    Resolve hotel context dari berbagai sumber input yang mungkin.
    
    Menjaga agar kode di luar modul integrasi tidak perlu 
    tahu dari mana hotel_id dikonfigurasi.
    """
    
    def __init__(self, db: AsyncSession):
        self.hotel_repo = HotelRepository(db)
    
    async def resolve(
        self,
        waha_session: Optional[str] = None,
        hotel_slug: Optional[str] = None,
        wa_number_to: Optional[str] = None
    ) -> Optional[HotelContext]:
        """
        Menentukan hotel berdasarkan parameter session WAHA, slug, atau nomor WA tujuan.
        Mengembalikan DUMMY_HOTEL jika debug aktif di level konfigurasi.
        """
        # Priority 1: WAHA session
        if waha_session:
            hotel = await self.hotel_repo.find_by_waha_session(waha_session)
            if hotel:
                return self._to_context(hotel)
        
        # Priority 2: hotel slug
        if hotel_slug:
            hotel = await self.hotel_repo.find_by_slug(hotel_slug)
            if hotel:
                return self._to_context(hotel)
        
        # Priority 3: nomor WA tujuan
        if wa_number_to:
            hotel = await self.hotel_repo.find_by_wa_number(wa_number_to)
            if hotel:
                return self._to_context(hotel)
        
        # Skenario tidak terdaftar di database
        from backend.config import settings
        if settings.debug:
            return DUMMY_HOTEL
            
        return None
    
    def _to_context(self, hotel) -> HotelContext:
        """Menerjemahkan model database Hotel ke Pydantic HotelContext."""
        return HotelContext(
            hotel_id=str(hotel.id),
            hotel_name=hotel.name,
            slug=hotel.slug,
            wa_number=hotel.wa_number,
            waha_session=hotel.waha_session
        )
