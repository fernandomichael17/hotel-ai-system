from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy import text
from typing import AsyncGenerator
from backend.config import settings
from backend.db.models import Base

# 1. Buat async engine dari settings.database_url
engine = create_async_engine(settings.database_url, echo=settings.debug)

# 2. Buat AsyncSessionLocal
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 3. Fungsi get_db() -> AsyncGenerator[AsyncSession]
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency generator untuk FastAPI yang menyediakan async database session.
    Setelah request selesai, session akan ditutup secara otomatis.
    
    Yields:
        AsyncSession: Sesi koneksi database asinkron.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# 4. Fungsi init_db()
async def init_db() -> None:
    """
    Menginisialisasi database dengan membuat extension pgvector 
    serta men-generate semua skema tabel dari model-model yang terdaftar secara asinkron.
    """
    async with engine.begin() as conn:
        # Jalankan: CREATE EXTENSION IF NOT EXISTS vector
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Jalankan: Base.metadata.create_all (dengan run_sync)
        await conn.run_sync(Base.metadata.create_all)

# 5. Fungsi check_db_connection() -> bool
async def check_db_connection() -> bool:
    """
    Memeriksa kesehatan koneksi ke database dengan melakukan query sederhana.
    Mengembalikan True jika sukses, False jika terjadi kegagalan.
    
    Returns:
        bool: Status keberhasilan koneksi ke database.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
