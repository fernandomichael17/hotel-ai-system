from backend.core.channel.context import ConversationContext

class ComplaintHandler:
    """Workflow handler untuk pelaporan keluhan kamar (Complaint) - placeholder."""
    
    def __init__(self, db=None):
        self.db = db
        
    async def handle(
        self,
        ctx: ConversationContext
    ) -> str:
        """
        Complaint workflow — coming August 2026.
        """
        return (
            f"Mohon maaf atas ketidaknyamanan Anda selama menginap di {ctx.hotel.hotel_name}. 🙏\n\n"
            "Untuk menyampaikan keluhan secara langsung agar dapat segera kami tangani, silakan hubungi tim Front Office kami:\n"
            "📞 (021) 1234-5678\n"
            "📧 info@hotel.com\n\n"
            "Kami akan segera menindaklanjuti keluhan Anda."
        )
