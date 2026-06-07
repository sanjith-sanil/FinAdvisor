from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    secret_key: str
    email_encryption_key: str
    upload_dir: str = "./uploads"
    max_pdf_size_mb: int = 10
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:8000"]
    email_check_interval_minutes: int = 2
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    google_login_redirect_uri: str | None = None
    server_base_url: str = "http://localhost:8000"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    ai_system_prompt: str | None = None


settings = Settings()
