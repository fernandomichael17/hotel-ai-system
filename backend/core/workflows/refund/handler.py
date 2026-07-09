from backend.core.channel.context import ConversationContext

class RefundHandler:
    """Workflow handler untuk pengajuan pengembalian dana (Refund) - placeholder."""
    
    def __init__(self, db=None):
        self.db = db
        
    async def handle(
        self,
        ctx: ConversationContext
    ) -> str:
        """
        Refund workflow — coming August 2026.
        """
        return (
            f"Terima kasih telah menghubungi {ctx.hotel.hotel_name}. "
            "Untuk pengajuan pengembalian dana (*refund*), silakan hubungi bagian administrasi keuangan kami:\n"
            "📞 (021) 1234-5678\n"
            "📧 info@hotel.com\n\n"
            "Kami akan memandu Anda untuk melengkapi dokumen pengajuan pengembalian dana."
        )
