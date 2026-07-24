import re
from backend.core.response.templates import (
    FALLBACK_OPTIONS,
    ESCALATE_TO_HUMAN
)

CONFIDENCE_THRESHOLD = 0.6
ESCALATE_KEYWORDS = [
    "staff", "cs", "customer service", "operator", "front office", "fo",
    "human", "bantuan langsung", "bicara langsung", "hubungi langsung", "admin"
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
        """Memeriksa apakah pesan mengandung permintaan eskalasi ke staff manusia dengan batas kata yang ketat."""
        msg_lower = message.lower()
        for kw in ESCALATE_KEYWORDS:
            # Cek kata kunci yang berdiri sendiri (word boundary)
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, msg_lower):
                return True
        return False
    
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
        message: str,
        has_active_workflow: bool = False
    ) -> str | None:
        """
        Menyaring masukan pilihan menu numerik dari user (1-5) dengan mendeteksi workflow aktif.
        """
        if has_active_workflow:
            return None
            
        msg = message.strip()
        menu_map = {
            "1": "faq",
            "2": "booking_inquiry",
            "3": "complaint",
            "4": "amenities",
            "5": "escalate"
        }
        return menu_map.get(msg)
