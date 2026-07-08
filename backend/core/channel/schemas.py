from pydantic import BaseModel
from typing import Optional

class HotelContext(BaseModel):
    """Model konteks hotel yang digunakan oleh resolver."""
    hotel_id: str
    hotel_name: str
    slug: str
    wa_number: Optional[str] = None
    waha_session: Optional[str] = None

class GuestContext(BaseModel):
    """Model konteks inap tamu untuk enriched session."""
    guest_name: str
    room_number: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    is_checked_in: bool = False
    hms_booking_id: Optional[str] = None

class IncomingMessage(BaseModel):
    """Model representasi pesan masuk dari API/WhatsApp."""
    user_identifier: str
    content: str
    channel: str = "web"
    hotel_slug: Optional[str] = None
    waha_session: Optional[str] = None
    has_media: bool = False
    media_url: Optional[str] = None
    hotel_context: Optional[HotelContext] = None
    guest_context: Optional[GuestContext] = None
