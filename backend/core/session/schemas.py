from pydantic import BaseModel
from typing import Optional, List

class MessageHistory(BaseModel):
    """Model representasi riwayat pesan tunggal untuk konsumsi LLM."""
    role: str
    content: str
    intent: Optional[str] = None
    created_at: Optional[str] = None

class SessionData(BaseModel):
    """Model data sesi aktif yang menampung riwayat pesan percakapan."""
    session_id: str
    hotel_id: str
    user_identifier: str
    channel: str
    status: str
    history: List[MessageHistory] = []
    created_at: str
    expires_at: Optional[str] = None
