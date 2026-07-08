from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def placeholder():
    """
    Endpoint placeholder untuk router admin.
    """
    return {"status": "coming soon"}
