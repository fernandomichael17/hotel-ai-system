from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .config import settings
from .db.database import init_db
from .api.v1 import chat, webhook, admin
from .api.portal import auth, documents, hotels

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event to handle application startup and shutdown."""
    await init_db()
    yield

app = FastAPI(
    title="Hotel AI Chatbot",
    description="Backend API for Hotel AI Chatbot System",
    version="1.0.0",
    lifespan=lifespan
)

# Setup CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(webhook.router, prefix="/api/v1", tags=["Webhook"])
app.include_router(admin.router, prefix="/api/v1", tags=["Admin"])
app.include_router(auth.router, prefix="/api/portal", tags=["Portal Auth"])
app.include_router(documents.router, prefix="/api/portal", tags=["Portal Documents"])
app.include_router(hotels.router, prefix="/api/portal", tags=["Portal Hotels"])

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "model": settings.model_name}
