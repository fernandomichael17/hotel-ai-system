from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application Settings."""
    database_url: str
    llm_base_url: str = "http://localhost:8000"
    model_name: str = "hotel-llm"
    embedding_model: str = "intfloat/multilingual-e5-base"
    use_mock_hms: bool = True
    hms_base_url: str
    hms_api_key: str
    wa_api_url: str
    wa_token: str
    wa_phone_id: str
    secret_key: str
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
