from backend.core.channel.context import ConversationContext

class BookingHandler:
    """Workflow handler untuk pemesanan kamar (Booking) - placeholder."""
    
    def __init__(self, db=None):
        self.db = db
        
    async def handle(
        self,
        ctx: ConversationContext
    ) -> str:
        """
        Booking workflow — coming August 2026.
        """
        return (
            "Terima kasih atas minat Anda "
            f"untuk menginap di "
            f"{ctx.hotel.hotel_name}! 🏨\n\n"
            "Untuk pemesanan kamar saat ini "
            "silakan hubungi kami:\n"
            "📞 (021) 1234-5678\n"
            "📧 info@hotel.com\n\n"
            "Fitur pemesanan via chat akan "
            "segera tersedia."
        )
