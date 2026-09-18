from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # LLM Settings
    LLM_PROVIDER: str = "gemini"  # "gemini", "groq", "openai", "generic"
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gemini-1.5-flash"
    LLM_BASE_URL: Optional[str] = None
    TIMEOUT_SECONDS: float = 15.0


settings = Settings()