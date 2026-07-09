from fastapi import APIRouter, Request
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Placeholder webhook untuk WAHA.
    
    Nanti akan:
    1. Parse WAHA payload
    2. Extract: session, from, body, media
    3. Forward ke chat endpoint logic
    4. Send response via WAHA API
    
    Format payload WAHA yang akan diterima:
    {
      "event": "message",
      "session": "hotel-slug",
      "payload": {
        "from": "628xxx@c.us",
        "body": "pesan user",
        "hasMedia": false,
        "fromMe": false
      }
    }
    """
    try:
        payload = await request.json()
        logger.info(f"Webhook received payload: {payload}")
    except Exception as e:
        logger.error(f"Gagal mem-parse json webhook WAHA: {str(e)}")
        return {"status": "error", "message": "Invalid JSON"}
        
    return {"status": "received"}

@router.get("/webhook/health")
async def webhook_health():
    """Endpoint pengecekan status kesiapan webhook."""
    return {"status": "webhook ready"}
