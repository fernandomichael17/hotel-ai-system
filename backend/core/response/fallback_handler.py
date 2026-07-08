from backend.core.response.templates import (
    FALLBACK_OPTIONS,
    ESCALATE_TO_HUMAN
)

CONFIDENCE_THRESHOLD = 0.6
ESCALATE_KEYWORDS = [
    "staff", "human", "manusia",
    "cs", "operator", "petugas",
    "front office", "fo", "resepsionis"
]

class FallbackHandler:
    """Handler untuk menangani kondisi ketika bot gagal mengklasifikasikan intent atau membutuhkan eskalasi."""
    
    def should_fallback(
        self,
        confidence: float
    ) -> bool:
        """Menentukan apakah bot harus fallback berdasarkan batas minimal skor confidence."""
        return confidence < CONFIDENCE_THRESHOLD
    
    def is_escalation_request(
        self,
        message: str
    ) -> bool:
        """Memeriksa apakah pesan mengandung permintaan eskalasi ke staff manusia."""
        msg_lower = message.lower()
        return any(
            kw in msg_lower
            for kw in ESCALATE_KEYWORDS
        )
    
    def get_fallback_response(
        self,
        channel: str = "web"
    ) -> str:
        """Mengembalikan teks menu pilihan fallback standar."""
        return FALLBACK_OPTIONS
    
    def get_escalation_response(
        self,
        phone: str = "(021) 1234-5678"
    ) -> str:
        """Mengembalikan teks konfirmasi eskalasi staff dengan nomor telepon terformat."""
        return ESCALATE_TO_HUMAN.format(
            phone=phone
        )
    
    def handle_menu_selection(
        self,
        message: str
    ) -> str | None:
        """
        Menyaring masukan pilihan menu numerik dari user (1-5).
        Mengembalikan jenis intent string yang bersangkutan.
        """
        msg = message.strip()
        menu_map = {
            "1": "faq",
            "2": "booking_inquiry",
            "3": "complaint",
            "4": "amenities",
            "5": "escalate"
        }
        return menu_map.get(msg)
