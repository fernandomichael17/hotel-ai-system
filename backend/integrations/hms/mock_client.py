import uuid
from .schemas import (
    RoomAvailabilityRequest,
    RoomAvailabilityResponse,
    BookingDraftRequest,
    BookingDraftResponse,
    GuestLookupRequest,
    GuestLookupResponse
)

class MockHMSClient:
    """Mock client for Hotel Management System integration."""
    
    async def check_availability(self, req: RoomAvailabilityRequest) -> RoomAvailabilityResponse:
        # Selalu return available: True
        # Kecuali room_type = "presidential_suite" dan date mengandung "31 Desember"
        if req.room_type == "presidential_suite" and "31 Desember" in req.date:
            return RoomAvailabilityResponse(
                available=False,
                room_type=req.room_type,
                date=req.date,
                price_per_night=5000000.0,
                reason="Fully booked for New Year's Eve"
            )
            
        return RoomAvailabilityResponse(
            available=True,
            room_type=req.room_type,
            date=req.date,
            price_per_night=850000.0
        )
        
    async def create_booking_draft(self, req: BookingDraftRequest) -> BookingDraftResponse:
        # Generate booking_id = "MOCK-{uuid4 4 char}"
        booking_id = f"MOCK-{str(uuid.uuid4())[:4].upper()}"
        return BookingDraftResponse(
            booking_id=booking_id,
            status="draft",
            params=req.model_dump()
        )
        
    async def lookup_guest(self, req: GuestLookupRequest) -> GuestLookupResponse:
        # Return dummy guest data
        return GuestLookupResponse(
            found=True,
            guest_name="Tamu Demo",
            room_number="101",
            check_in="2026-07-01",
            check_out="2026-07-05"
        )
