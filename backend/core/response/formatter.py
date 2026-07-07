class ResponseFormatter:
    """Format response based on channel."""
    
    def format(self, content: str, channel: str, intent: str | None = None) -> str:
        if channel == "whatsapp":
            # Apply whatsapp formatting
            # Max 4096 characters, maybe truncate if needed
            if len(content) > 4096:
                content = content[:4093] + "..."
            return content
        elif channel == "web":
            return content
        return content
