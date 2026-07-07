from pydantic import BaseModel
from typing import Optional

class RoomAvailabilityRequest(BaseModel):
    room_type: str
    date: str
    hotel_id: str

class RoomAvailabilityResponse(BaseModel):
    available: bool
    room_type: str
    date: str
    price_per_night: float
    reason: Optional[str] = None

class BookingDraftRequest(BaseModel):
    guest_name: str
    room_type: str
    check_in_date: str
    check_out_date: str
    num_guests: int
    hotel_id: str

class BookingDraftResponse(BaseModel):
    booking_id: str
    status: str
    params: dict

class GuestLookupRequest(BaseModel):
    wa_number: str
    hotel_id: str

class GuestLookupResponse(BaseModel):
    found: bool
    guest_name: Optional[str] = None
    room_number: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
