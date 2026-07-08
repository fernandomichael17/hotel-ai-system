from typing import Optional
from backend.core.channel.schemas import GuestContext
from backend.integrations.hms.schemas import (
    GuestLookupResponse,
    RoomAvailabilityResponse
)
from backend.db.models import BookingDraft

class HMSDataMapper:
    """Mapper untuk menerjemahkan format data internal HMS ke model data internal chatbot."""

    @staticmethod
    def to_guest_context(response: GuestLookupResponse) -> Optional[GuestContext]:
        """Defensive mapper untuk mengubah data tamu HMS ke format GuestContext."""
        if not response.found:
            return None
            
        data = response.model_dump() if hasattr(response, "model_dump") else (response.__dict__ if hasattr(response, "__dict__") else {})
        
        # Defensive lookup: Mengantisipasi perbedaan nama kolom dari remote HMS API
        guest_name = (
            data.get("guest_name") or 
            data.get("nama_tamu") or 
            data.get("name") or 
            "Tamu"
        )
        room_number = (
            data.get("room_number") or 
            data.get("room_no") or 
            data.get("kamar") or 
            data.get("no_kamar") or 
            ""
        )
        check_in = data.get("check_in_date") or data.get("check_in")
        check_out = data.get("check_out_date") or data.get("check_out")
        
        return GuestContext(
            guest_name=guest_name,
            room_number=room_number,
            check_in=check_in,
            check_out=check_out,
            is_checked_in=True
        )

    @staticmethod
    def to_availability_summary(response: RoomAvailabilityResponse) -> str:
        """Menerjemahkan status availability kamar ke format string ringkas untuk konsumsi LLM."""
        if response.available:
            price_str = str(int(response.price_per_night)) if response.price_per_night is not None else "-"
            total_str = str(int(response.total_price)) if response.total_price is not None else "-"
            
            return (
                "status    | room_type | price_per_night | total\n"
                f"tersedia  | {response.room_type}    | {price_str}          | {total_str}"
            )
        else:
            reason_str = response.reason or "Kamar penuh"
            alt_str = ", ".join(response.alternatives) if response.alternatives else "-"
            return (
                "status        | reason              | alternatives\n"
                f"tidak tersedia| {reason_str}        | {alt_str}"
            )

    @staticmethod
    def booking_draft_to_hms_request(draft: BookingDraft) -> dict:
        """Mengonversi rancangan draft booking lokal ke format dict request HMS API asli."""
        return {
            "guest_name": draft.guest_name or "Tamu",
            "arrival_date": draft.check_in_date or "",
            "departure_date": draft.check_out_date or "",
            "room_type_code": draft.room_type or "",
            "adults": draft.num_guests or 1,
            "remarks": draft.special_request or "",
            "source_code": "CHATBOT",
            "channel": "whatsapp"
        }
