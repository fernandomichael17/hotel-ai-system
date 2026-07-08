from pydantic import BaseModel
from typing import Optional

class CheckInRequest(BaseModel):
    """Model data request pendaftaran tamu check-in."""
    hotel_id: str
    wa_number: str
    guest_name: str
    room_number: str
    check_in_date: str
    check_out_date: str
    booking_source: str = "manual_fo"
    hms_booking_id: Optional[str] = None

class CheckOutRequest(BaseModel):
    """Model data request konfirmasi checkout tamu."""
    hotel_id: str
    wa_number: str

class GuestStayResponse(BaseModel):
    """Model data response representasi detail stay inap tamu."""
    id: str
    hotel_id: str
    wa_number: str
    guest_name: str
    room_number: Optional[str] = None
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None
    status: str
    booking_source: str
