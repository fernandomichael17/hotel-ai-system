"""
Schema untuk booking workflow.
Semua state booking ada di sini.
"""

from pydantic import BaseModel
from enum import Enum
from typing import Any

class BookingStep(str, Enum):
    """
    Tahapan dalam booking flow.
    Dipakai untuk track posisi user
    dalam percakapan booking.
    """
    INQUIRY          = "inquiry"
    # User tanya ketersediaan/harga

    COLLECTING       = "collecting"
    # Bot sedang collect parameter

    CONFIRMING       = "confirming"
    # Bot menampilkan summary,
    # menunggu konfirmasi user

    UPSELLING        = "upselling"
    # Bot menawarkan paket tambahan

    COMPLETED        = "completed"
    # Booking draft sudah dibuat

    CANCELLED        = "cancelled"
    # User batalkan di tengah jalan

class CollectedParams(BaseModel):
    """
    Parameter booking yang sudah
    berhasil dikumpulkan dari user.
    Semua nullable — diisi bertahap.
    """
    guest_name: str | None = None
    wa_number: str | None = None
    check_in_date: str | None = None
    check_out_date: str | None = None
    room_type: str | None = None
    num_guests: int | None = None
    num_children: int | None = 0
    special_request: str | None = None

    def missing_required(self) -> list[str]:
        """
        Mengembalikan daftar label parameter wajib yang belum diisi oleh tamu.

        Return:
            list[str]: Daftar nama label parameter wajib yang masih kosong.
        """
        required = {
            "guest_name": "nama tamu",
            "wa_number": "nomor WhatsApp",
            "check_in_date": "tanggal check-in",
            "check_out_date": "tanggal check-out",
            "room_type": "tipe kamar",
            "num_guests": "jumlah tamu dewasa"
        }
        return [
            label for field, label
            in required.items()
            if not getattr(self, field)
        ]

    def is_complete(self) -> bool:
        return len(self.missing_required()) == 0

    def to_summary(self) -> str:
        """
        Format params sebagai summary
        yang ditampilkan ke user
        sebelum konfirmasi.

        Format output:
        🏨 Tipe Kamar  : Deluxe
        📅 Check-in    : 15 Juli
        📅 Check-out   : 17 Juli
        👥 Tamu Dewasa : 2 orang
        👶 Anak-anak   : 1 orang
        📝 Request     : Kamar lantai atas
        📞 WhatsApp    : 08123456789
        👤 Nama        : Budi Santoso
        """
        lines = []
        room_map = {
            "standard": "Standard",
            "deluxe": "Deluxe",
            "suite": "Suite",
            "presidential_suite":
                "Presidential Suite"
        }
        lines.append(
            f"🏨 Tipe Kamar  : "
            f"{room_map.get(self.room_type, self.room_type)}"
        )
        lines.append(
            f"📅 Check-in    : "
            f"{self.check_in_date or '-'}"
        )
        if self.check_out_date:
            lines.append(
                f"📅 Check-out   : "
                f"{self.check_out_date}"
            )
        lines.append(
            f"👥 Tamu Dewasa : "
            f"{self.num_guests or '-'} orang"
        )
        if self.num_children:
            lines.append(
                f"👶 Anak-anak   : "
                f"{self.num_children} orang"
            )
        if self.special_request:
            lines.append(
                f"📝 Request     : "
                f"{self.special_request}"
            )
        lines.append(
            f"📞 WhatsApp    : "
            f"{self.wa_number or '-'}"
        )
        lines.append(
            f"👤 Nama        : "
            f"{self.guest_name or '-'}"
        )
        return "\n".join(lines)

class UpsellOffer(BaseModel):
    """
    Satu item upsell yang ditawarkan ke user.
    Diambil dari hotel_policies table.
    """
    key: str
    name: str
    price: int
    unit: str
    accepted: bool = False

    def format_offer(self) -> str:
        """
        Format untuk ditampilkan ke user.
        Contoh: "Paket Sarapan — Rp 100.000/orang/malam"
        """
        price_fmt = f"Rp {self.price:,}".replace(
            ",", "."
        )
        return f"{self.name} — {price_fmt}/{self.unit}"

class BookingState(BaseModel):
    """
    State lengkap booking dalam satu session.
    Disimpan di session context —
    bukan di database sampai draft dibuat.
    """
    step: BookingStep = BookingStep.INQUIRY
    params: CollectedParams = CollectedParams()
    upsell_offers: list[UpsellOffer] = []
    upsell_index: int = 0
    # Index upsell yang sedang ditawarkan
    # Ditawarkan satu per satu, bukan sekaligus
    availability_checked: bool = False
    availability_result: dict | None = None
    booking_ref: str | None = None
    # Diisi setelah booking draft berhasil dibuat

    def current_upsell(self) -> UpsellOffer | None:
        """Return upsell yang sedang ditawarkan"""
        if self.upsell_index < len(self.upsell_offers):
            return self.upsell_offers[self.upsell_index]
        return None

    def next_upsell(self) -> UpsellOffer | None:
        """Pindah ke upsell berikutnya"""
        self.upsell_index += 1
        return self.current_upsell()

    def accepted_upsells(self) -> list[str]:
        """Return list key upsell yang diterima"""
        return [
            u.key for u in self.upsell_offers
            if u.accepted
        ]
