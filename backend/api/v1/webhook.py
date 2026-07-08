from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def placeholder():
    """
    Endpoint placeholder untuk router webhook.
    """
    return {"status": "coming soon"}
