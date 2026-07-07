from typing import Optional
from .schemas import HotelContext

class ChannelResolver:
    """Resolver for resolving incoming messages to a hotel context."""
    
    async def resolve(
        self,
        wa_number_to: Optional[str],
        hotel_slug: Optional[str] = None
    ) -> Optional[HotelContext]:
        # 1. Kalau ada wa_number_to -> lookup di tabel hotels by wa_number
        # 2. Kalau ada hotel_slug -> lookup by slug
        # 3. Kalau tidak ketemu -> return None (caller akan handle: tanya user)
        
        # Untuk sekarang dengan dummy data:
        return HotelContext(
            hotel_id="00000000-0000-0000-0000-000000000000",
            hotel_name="Hotel Demo Metland",
            slug="demo",
            wa_number=wa_number_to
        )
