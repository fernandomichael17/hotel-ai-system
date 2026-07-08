from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.db.database import init_db, check_db_connection

# Import router-router yang didefinisikan
from backend.api.v1.chat import router as chat_router
from backend.api.v1.webhook import router as webhook_router
from backend.api.v1.admin import router as admin_router
from backend.api.portal.auth import router as auth_router
from backend.api.portal.documents import router as documents_router
from backend.api.portal.hotels import router as hotels_router

app = FastAPI(
    title="Hotel AI Chatbot",
    description="Metland Hotel Group AI Assistant",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """
    Event handler saat aplikasi FastAPI pertama kali dijalankan.
    Menginisialisasi tabel database dan melakukan logging status server.
    """
    await init_db()
    print("Database initialized")
    print("Server ready")

@app.get("/health")
async def health_check():
    """
    Endpoint health check untuk memonitor kesehatan aplikasi dan koneksi database.
    """
    db_healthy = await check_db_connection()
    return {
        "status": "ok",
        "version": "0.1.0",
        "model": settings.model_name,
        "mock_hms": settings.use_mock_hms,
        "db": db_healthy
    }

@app.get("/")
async def root():
    """
    Endpoint root yang menampilkan pesan pembuka API.
    """
    return {"message": "Hotel AI Chatbot API"}

# Include routers dengan prefix masing-masing
app.include_router(chat_router, prefix="/api/v1")
app.include_router(webhook_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/portal")
app.include_router(documents_router, prefix="/portal")
app.include_router(hotels_router, prefix="/portal")
