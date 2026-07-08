import random
from datetime import datetime, date, timedelta
from typing import Optional, List
from .schemas import (
    RoomAvailabilityRequest,
    RoomAvailabilityResponse,
    BookingCreateRequest,
    BookingCreateResponse,
    GuestLookupRequest,
    GuestLookupResponse,
    RoomExtensionRequest,
    RoomExtensionResponse
)

class MockHMSClient:
    """
    Mock HMS client untuk keperluan development lokal tanpa koneksi network.
    
    Menyediakan data mock realistis untuk simulasi workflow reservasi, 
    pencarian tamu (enriched session), dan perpanjangan inap.
    """

    ROOM_PRICES = {
        "standard": 500000.0,
        "deluxe": 850000.0,
        "suite": 1500000.0,
        "presidential_suite": 3500000.0
    }

    UNAVAILABLE_CONDITIONS = [
        ("presidential_suite", "31 Desember"),
        ("presidential_suite", "31 december"),
        ("suite", "31 Desember"),
    ]

    async def check_availability(self, req: RoomAvailabilityRequest) -> RoomAvailabilityResponse:
        """Memeriksa ketersediaan kamar secara simulatif (mock)."""
        room_type = req.room_type.lower().strip()
        if room_type not in self.ROOM_PRICES:
            return RoomAvailabilityResponse(
                available=False,
                room_type=req.room_type,
                check_in_date=req.check_in_date,
                reason="Tipe kamar tidak tersedia"
            )

        # Cek kondisi fully booked (simulasi)
        for un_type, un_date in self.UNAVAILABLE_CONDITIONS:
            if un_type == room_type and (un_date in req.check_in_date or (req.check_out_date and un_date in req.check_out_date)):
                alternatives = [t for t in self.ROOM_PRICES.keys() if t != room_type]
                return RoomAvailabilityResponse(
                    available=False,
                    room_type=req.room_type,
                    check_in_date=req.check_in_date,
                    check_out_date=req.check_out_date,
                    reason="Kamar penuh untuk tanggal tersebut",
                    alternatives=alternatives
                )

        price_per_night = self.ROOM_PRICES[room_type]
        total_price = None

        if req.check_out_date:
            try:
                in_d = datetime.strptime(req.check_in_date, "%Y-%m-%d")
                out_d = datetime.strptime(req.check_out_date, "%Y-%m-%d")
                nights = (out_d - in_d).days
                if nights <= 0:
                    nights = 1
            except Exception:
                nights = 1  # Fallback 1 malam jika format teks bebas
            total_price = price_per_night * nights

        return RoomAvailabilityResponse(
            available=True,
            room_type=req.room_type,
            check_in_date=req.check_in_date,
            check_out_date=req.check_out_date,
            price_per_night=price_per_night,
            total_price=total_price,
            currency="IDR",
            reason=None
        )

    async def create_booking(self, req: BookingCreateRequest) -> BookingCreateResponse:
        """Membuat pemesanan baru secara simulatif."""
        prefix = req.hotel_id[:4].upper() if req.hotel_id else "MOCK"
        digits = "".join([str(random.randint(0, 9)) for _ in range(6)])
        booking_id = f"MOCK-{prefix}-{digits}"

        return BookingCreateResponse(
            success=True,
            hms_booking_id=booking_id,
            status="pending_confirmation",
            message="Booking berhasil didaftarkan di HMS mock",
            estimated_confirmation="1x24 jam kerja"
        )

    async def lookup_guest(self, req: GuestLookupRequest) -> GuestLookupResponse:
        """Mencari tamu inap aktif secara simulatif. Nomor berawalan 628999 disimulasikan tidak ketemu."""
        if req.wa_number.startswith("628999"):
            return GuestLookupResponse(found=False)

        today_str = date.today().strftime("%Y-%m-%d")
        checkout_str = (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")

        return GuestLookupResponse(
            found=True,
            guest_name="Tamu Demo",
            room_number="301",
            check_in_date=today_str,
            check_out_date=checkout_str,
            hms_booking_id="MOCK-HMS-000001",
            wa_number=req.wa_number
        )

    async def extend_stay(self, req: RoomExtensionRequest) -> RoomExtensionResponse:
        """Memperpanjang masa inap tamu secara simulatif."""
        price = self.ROOM_PRICES["deluxe"]
        return RoomExtensionResponse(
            success=True,
            hms_booking_id=req.hms_booking_id,
            new_check_out_date=req.new_check_out_date,
            additional_charge=price,
            message="Perpanjangan inap berhasil dikonfirmasi secara mock"
        )
