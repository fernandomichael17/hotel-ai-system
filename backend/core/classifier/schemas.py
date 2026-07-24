from enum import Enum
from dataclasses import dataclass
from typing import Optional, List

class IntentType(str, Enum):
    """
    Enum untuk tipe intent klasifikasi chatbot hotel.
    """
    FAQ = "faq"
    GREETING = "greeting"
    BOOKING_INQUIRY = "booking_inquiry"
    BOOKING_REQUEST = "booking_request"
    COMPLAINT = "complaint"
    CANCELLATION = "cancellation"
    REFUND = "refund"
    REFUND_INQUIRY = "refund_inquiry"
    RESCHEDULE = "reschedule"
    AMENITIES = "amenities"
    ESCALATE = "escalate"
    UNKNOWN = "unknown"

@dataclass
class IntentResult:
    """
    Dataclass untuk menyimpan hasil klasifikasi intent tunggal.

    Attributes:
        intent (IntentType): Tipe intent yang berhasil diklasifikasikan.
        confidence (float): Tingkat kepercayaan hasil klasifikasi (0.0 sampai 1.0).
        raw_response (str): Respons mentah asli dari model LLM.
    """
    intent: IntentType
    confidence: float
    raw_response: str

@dataclass
class ExtractionResult:
    """
    Dataclass untuk menyimpan hasil ekstraksi parameter pemesanan dari pesan pengguna.

    Attributes:
        name (Optional[str]): Nama tamu yang memesan.
        check_in_date (Optional[str]): Tanggal check-in pemesanan.
        check_out_date (Optional[str]): Tanggal check-out pemesanan.
        room_type (Optional[str]): Tipe kamar yang dipesan.
        raw_response (str): Respons mentah asli berbentuk JSON string dari model LLM.
    """
    name: Optional[str]
    check_in_date: Optional[str]
    check_out_date: Optional[str]
    room_type: Optional[str]
    raw_response: str

@dataclass
class DualIntentResult:
    """
    Dataclass untuk menyimpan hasil deteksi multi-intent (lebih dari satu intent sekaligus).

    Attributes:
        intents (List[IntentType]): Daftar intent yang berhasil dideteksi dalam pesan.
        raw_response (str): Respons mentah asli dari model LLM.
    """
    intents: List[IntentType]
    raw_response: str
