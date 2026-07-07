from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "多智能体软件开发平台"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite+aiosqlite:///./backend.db"
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000", "http://127.0.0.1:3000"]
    USE_PAID_LLM_API: bool = True
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")


settings = Settings()
