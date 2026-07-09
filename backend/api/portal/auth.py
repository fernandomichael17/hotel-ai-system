from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from jose import JWTError, jwt

from backend.db.database import get_db
from backend.config import settings

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/portal/auth/login"
)

class LoginRequest(BaseModel):
    hotel_slug: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    hotel_id: str
    hotel_name: str
    expires_at: str

class TokenData(BaseModel):
    hotel_id: str
    hotel_slug: str
    hotel_name: str

@router.post("/auth/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login ke admin portal untuk staff hotel berdasarkan slug dan password global.
    """
    from backend.db.repositories.hotel_repo import HotelRepository
    repo = HotelRepository(db)
    
    # 1. Cari hotel berdasarkan slug
    hotel = await repo.find_by_slug(request.hotel_slug)
    if not hotel:
        raise HTTPException(
            status_code=404,
            detail="Hotel tidak ditemukan"
        )
        
    # 2. Cek password vs settings.portal_password
    if request.password != settings.portal_password:
        raise HTTPException(
            status_code=401,
            detail="Password salah"
        )
        
    # 3. Generate JWT dengan payload info hotel
    expire = datetime.utcnow() + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "hotel_id": str(hotel.id),
        "hotel_slug": hotel.slug,
        "hotel_name": hotel.name,
        "exp": expire
    }
    
    token = jwt.encode(
        payload,
        settings.secret_key,
        algorithm="HS256"
    )
    
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        hotel_id=str(hotel.id),
        hotel_name=hotel.name,
        expires_at=expire.isoformat()
    )

async def get_current_hotel(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> TokenData:
    """
    Dependency Injection untuk memvalidasi otentikasi JWT token dan mengembalikan info hotel yang aktif.
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="Token tidak valid atau expired",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"]
        )
        hotel_id = payload.get("hotel_id")
        hotel_slug = payload.get("hotel_slug")
        hotel_name = payload.get("hotel_name")
        
        if not hotel_id or not hotel_slug or not hotel_name:
            raise credentials_exception
            
        return TokenData(
            hotel_id=hotel_id,
            hotel_slug=hotel_slug,
            hotel_name=hotel_name
        )
    except JWTError:
        raise credentials_exception
