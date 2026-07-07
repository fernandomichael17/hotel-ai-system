from pydantic import BaseModel
from typing import Optional

class HotelContext(BaseModel):
    hotel_id: str
    hotel_name: str
    wa_number: Optional[str] = None
    slug: str

class GuestContext(BaseModel):
    guest_name: str
    room_number: str
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    is_checked_in: bool = False

class IncomingMessage(BaseModel):
    wa_number_from: str
    wa_number_to: Optional[str] = None
    content: str
    channel: str = "whatsapp"
    hotel_context: Optional[HotelContext] = None
    guest_context: Optional[GuestContext] = None
