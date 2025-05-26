"""Configuration settings for the API."""
import os
from typing import Dict, Any, Optional, List
from pydantic import BaseSettings, Field, validator, HttpUrl, AnyHttpUrl
from pathlib import Path

class ApiSettings(BaseSettings):
    """API configuration settings."""
    
    # Application
    APP_NAME: str = "agi-prompt-system"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    SECRET_KEY: str = Field(
        default=os.getenv("SECRET_KEY", "insecure-secret-key-change-me"),
        min_length=32,
        max_length=100,
    )
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = os.cpu_count() or 1
    RELOAD: bool = False
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    CORS_CREDENTIALS: bool = True
    
    # Security
    RATE_LIMIT: str = "100/minute"
    SECURE_COOKIES: bool = True
    SESSION_COOKIE_NAME: str = "agi_session"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_SAMESITE: str = "lax"
    
    # Database
    DATABASE_URL: str = "sqlite:///./sql_app.db"
    DATABASE_ECHO: bool = False
    
    # Cache
    CACHE_BACKEND: str = "redis"
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 300  # 5 minutes
    
    # Authentication
    AUTH_ENABLED: bool = False
    JWT_SECRET_KEY: str = Field(
        default=os.getenv("JWT_SECRET_KEY", "insecure-jwt-secret-change-me"),
        min_length=32,
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # External Services
    NVIDIA_API_KEY: Optional[str] = os.getenv("NVIDIA_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 8001
    ENABLE_TRACING: bool = True
    TRACING_SERVICE_NAME: str = "agi-prompt-api"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Internationalization
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: List[str] = ["en", "fr", "es", "de", "zh"]
    
    # File Storage
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: List[str] = ["txt", "pdf", "docx"]

    # Celery Time Limits
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(
        default=300, 
        description="Celery task soft time limit in seconds"
    )
    CELERY_TASK_TIME_LIMIT: int = Field(
        default=360, 
        description="Celery task hard time limit in seconds"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        """Validate environment value."""
        envs = ["development", "testing", "staging", "production"]
        if v not in envs:
            raise ValueError(f"ENVIRONMENT must be one of {envs}")
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.ENVIRONMENT == "testing"
    
    def get_database_url(self) -> str:
        """Get database URL with test prefix if in testing mode."""
        if self.is_testing:
            return f"{self.DATABASE_URL}_test"
        return self.DATABASE_URL

# Create settings instance
settings = ApiSettings()

# Create necessary directories
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
