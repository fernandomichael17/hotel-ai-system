from pydantic import BaseModel
from typing import Optional, List

class RoomAvailabilityRequest(BaseModel):
    """Model data request untuk memeriksa ketersediaan kamar di HMS."""
    hotel_id: str
    room_type: str
    check_in_date: str
    check_out_date: Optional[str] = None
    num_guests: int = 1
    num_children: int = 0

class BookingCreateRequest(BaseModel):
    """Model data request untuk membuat pemesanan kamar baru di HMS."""
    hotel_id: str
    guest_name: str
    wa_number: str
    room_type: str
    check_in_date: str
    check_out_date: str
    num_guests: int
    num_children: int = 0
    special_request: Optional[str] = None
    upsell_items: List[str] = []
    source: str = "chatbot"

class GuestLookupRequest(BaseModel):
    """Model data request untuk mencari informasi inap tamu (enriched session)."""
    wa_number: str
    hotel_id: str

class RoomExtensionRequest(BaseModel):
    """Model data request untuk perpanjangan masa inap kamar."""
    hms_booking_id: str
    hotel_id: str
    new_check_out_date: str

class RoomAvailabilityResponse(BaseModel):
    """Model data response hasil pengecekan ketersediaan kamar HMS."""
    available: bool
    room_type: str
    check_in_date: str
    check_out_date: Optional[str] = None
    price_per_night: Optional[float] = None
    total_price: Optional[float] = None
    currency: str = "IDR"
    reason: Optional[str] = None
    alternatives: List[str] = []

class BookingCreateResponse(BaseModel):
    """Model data response dari pembuatan pemesanan kamar baru HMS."""
    success: bool
    hms_booking_id: Optional[str] = None
    status: str
    message: str
    estimated_confirmation: Optional[str] = None

class GuestLookupResponse(BaseModel):
    """Model data response pencarian inap tamu HMS."""
    found: bool
    guest_name: Optional[str] = None
    room_number: Optional[str] = None
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None
    hms_booking_id: Optional[str] = None
    wa_number: Optional[str] = None

class RoomExtensionResponse(BaseModel):
    """Model data response hasil permintaan perpanjangan masa inap HMS."""
    success: bool
    hms_booking_id: Optional[str] = None
    new_check_out_date: Optional[str] = None
    additional_charge: Optional[float] = None
    message: str
