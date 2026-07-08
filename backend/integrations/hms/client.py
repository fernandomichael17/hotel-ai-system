import httpx
from backend.config import settings
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

class HMSClient:
    """
    Real client untuk integrasi API HMS (Hotel Management System) komersial asli.
    
    Seluruh operasi memicu NotImplementedError karena HMS API internal Metland 
    saat ini belum dibuka aksesnya secara network.
    """
    
    def __init__(self):
        self.base_url = settings.hms_base_url
        self.api_key = settings.hms_api_key
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0
        )

    async def check_availability(self, req: RoomAvailabilityRequest) -> RoomAvailabilityResponse:
        """Memeriksa ketersediaan kamar pada server API HMS asli."""
        raise NotImplementedError(
            "HMS API belum dikonfigurasi. "
            "Set USE_MOCK_HMS=true di .env untuk menggunakan client simulasi."
        )

    async def create_booking(self, req: BookingCreateRequest) -> BookingCreateResponse:
        """Membuat pemesanan kamar baru pada server API HMS asli."""
        raise NotImplementedError(
            "HMS API belum dikonfigurasi. "
            "Set USE_MOCK_HMS=true di .env untuk menggunakan client simulasi."
        )

    async def lookup_guest(self, req: GuestLookupRequest) -> GuestLookupResponse:
        """Mencari data inap tamu aktif pada server API HMS asli."""
        raise NotImplementedError(
            "HMS API belum dikonfigurasi. "
            "Set USE_MOCK_HMS=true di .env untuk menggunakan client simulasi."
        )

    async def extend_stay(self, req: RoomExtensionRequest) -> RoomExtensionResponse:
        """Melakukan perpanjangan inap kamar pada server API HMS asli."""
        raise NotImplementedError(
            "HMS API belum dikonfigurasi. "
            "Set USE_MOCK_HMS=true di .env untuk menggunakan client simulasi."
        )
