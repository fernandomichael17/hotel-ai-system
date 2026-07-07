class FallbackHandler:
    """Handle intent classification fallback."""
    
    def should_fallback(self, confidence: float, threshold: float = 0.6) -> bool:
        return confidence < threshold
        
    def get_fallback_response(self, message: str, channel: str) -> str:
        return (
            "Maaf, saya kurang memahami permintaan Anda. Apakah Anda ingin:\n"
            "1. Informasi hotel\n"
            "2. Booking kamar\n"
            "3. Menyampaikan keluhan\n"
            "4. Proses refund"
        )
