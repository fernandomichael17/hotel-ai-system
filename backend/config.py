from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application Settings untuk Hotel AI Chatbot.
    
    Database:
        database_url: Konfigurasi URL untuk koneksi database PostgreSQL via asyncpg.
        
    LLM:
        llm_base_url: URL server lokal vLLM.
        model_name: Nama model yang digunakan (Qwen 4B).
        embedding_model: Nama model untuk sentence-transformers.
        
    HMS:
        use_mock_hms: Mengaktifkan/menonaktifkan HMS Mocking via factory pattern.
        hms_base_url: URL untuk request API ke Hotel Management System.
        hms_api_key: Kredensial API Key untuk integrasi HMS.
        
    WAHA:
        waha_url: URL untuk service WhatsApp self-hosted (WAHA).
        waha_api_key: Kredensial API Key untuk WAHA.
        
    Notification:
        smtp_host: Alamat server SMTP untuk email notifikasi.
        smtp_port: Port dari server SMTP.
        smtp_user: Username login server SMTP.
        smtp_password: Password login server SMTP.
        notification_email: Alamat email tujuan atau pengirim default notifikasi.
        
    App:
        secret_key: Kunci rahasia untuk otentikasi JWT / passlib.
        debug: Mode debug aplikasi FastAPI.
        app_port: Port yang digunakan aplikasi FastAPI untuk berjalan.
    """
    
    # Database
    database_url: str

    # LLM
    llm_base_url: str = "http://localhost:8000"
    model_name: str = "hotel-llm"
    embedding_model: str = "jinaai/jina-embeddings-v5-text-nano"

    # HMS
    use_mock_hms: bool = True
    hms_base_url: str = "http://localhost:9000"
    hms_api_key: str = "dummy-key"

    # WAHA
    waha_url: str = "http://localhost:3000"
    waha_api_key: str = ""

    # Notification
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notification_email: str = ""

    # App
    secret_key: str
    debug: bool = False
    app_port: int = 8001

    # Portal Admin
    portal_password: str = "admin123"
    jwt_expire_hours: int = 24
    allowed_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

try:
    settings = Settings()
except Exception:
    # Fallback saat di-import dalam keadaan env variabel wajib belum tersedia (missing)
    # untuk memenuhi syarat "bisa diimport tanpa error meski .env belum ada"
    settings = Settings(
        database_url="postgresql+asyncpg://mock:mock@localhost:5432/mock",
        secret_key="mock-secret-key"
    )
