class ResponseFormatter:
    """Formatter respon pesan untuk menyesuaikan output di channel Web atau WhatsApp."""
    
    MAX_WA_LENGTH = 4096
    
    def format(
        self,
        content: str,
        channel: str = "web",
        intent: str | None = None
    ) -> str:
        """
        Format response sesuai channel.
        
        WhatsApp:
        - Truncate kalau > MAX_WA_LENGTH
        - Pastikan tidak ada karakter yang rusak di WA
        
        Web:
        - Return as-is
        """
        if channel == "whatsapp":
            return self._format_whatsapp(content)
        return content
    
    def _format_whatsapp(self, content: str) -> str:
        """
        Menerapkan aturan format pesan untuk WhatsApp.
        1. Maksimal 4096 karakter.
        2. Jika pesan terpotong -> tambahkan kalimat penjelas hubungi staff.
        3. Menjaga karakter agar kompatibel dengan WA.
        """
        if len(content) <= self.MAX_WA_LENGTH:
            return content
        
        truncated = content[:self.MAX_WA_LENGTH - 50]
        return truncated + \
               "\n\n_(pesan terpotong — " \
               "hubungi staff untuk info lengkap)_"
