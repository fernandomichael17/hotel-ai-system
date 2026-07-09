from backend.core.channel.context import ConversationContext

class RescheduleHandler:
    """Workflow handler untuk penjadwalan ulang reservasi (Reschedule) - placeholder."""
    
    def __init__(self, db=None):
        self.db = db
        
    async def handle(
        self,
        ctx: ConversationContext
    ) -> str:
        """
        Reschedule workflow — coming August 2026.
        """
        return (
            f"Terima kasih telah menghubungi {ctx.hotel.hotel_name}. "
            "Untuk melakukan perubahan jadwal menginap (*reschedule*), silakan hubungi layanan pelanggan kami:\n"
            "📞 (021) 1234-5678\n"
            "📧 info@hotel.com\n\n"
            "Tim kami siap membantu Anda melakukan penyesuaian jadwal."
        )
