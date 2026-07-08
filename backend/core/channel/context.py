from typing import Optional, List
from backend.core.channel.schemas import (
    HotelContext, GuestContext, IncomingMessage
)

class ConversationContext:
    """
    Single object yang berisi seluruh konteks satu pesan.
    
    Digenerate sekali per request pesan masuk untuk kemudian 
    diteruskan ke workflow handler.
    """
    def __init__(
        self,
        message: IncomingMessage,
        hotel: HotelContext,
        guest: Optional[GuestContext] = None,
        session_id: Optional[str] = None,
        history: Optional[List[dict]] = None
    ):
        self.message = message
        self.hotel = hotel
        self.guest = guest
        self.session_id = session_id
        self.history = history or []
        self.is_enriched = guest is not None and guest.is_checked_in

    @property
    def hotel_id(self) -> str:
        """Mendapatkan ID hotel dari konteks."""
        return self.hotel.hotel_id

    @property
    def user_id(self) -> str:
        """Mendapatkan ID pengirim pesan."""
        return self.message.user_identifier

    @property
    def guest_name(self) -> Optional[str]:
        """Mendapatkan nama tamu jika sesi ter-enrich."""
        return self.guest.guest_name if self.guest else None

    @property
    def room_number(self) -> Optional[str]:
        """Mendapatkan nomor kamar jika sesi ter-enrich."""
        return self.guest.room_number if self.guest else None

    def to_dict(self) -> dict:
        """Mengonversi konteks ke bentuk dict untuk log auditing."""
        return {
            "hotel_id": self.hotel_id,
            "hotel_name": self.hotel.hotel_name,
            "user_id": self.user_id,
            "is_enriched": self.is_enriched,
            "guest_name": self.guest_name,
            "room_number": self.room_number,
            "session_id": self.session_id,
            "history_length": len(self.history)
        }
