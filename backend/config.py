import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "MAASA - Multi-Agent Autonomous Software Architect"
    API_V1_STR: str = "/api/v1"
    
    # JWT Auth Config
    # In production, change this secret key
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-key-for-jwt-maasa-2026-auth")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week
    
    # Database
    # Default to SQLite local file in backend directory
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./maasa.db")
    
    # LLM Settings (Optional)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)

    class Config:
        case_sensitive = True

settings = Settings()
