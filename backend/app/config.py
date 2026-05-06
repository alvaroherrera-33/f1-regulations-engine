from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str
    
    # OpenRouter
    openrouter_api_key: str
    llm_model: str = "openai/gpt-oss-120b"
    
    # CORS
    allowed_origins: str = "http://localhost:3000"
    
    # Upload settings
    max_upload_size: int = Field(default=50 * 1024 * 1024)  # 50MB
    upload_dir: str = Field(default="data/regulations")
    
    # Server settings
    port: int = Field(default=8000)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # Ignore any extra env vars so Docker doesn't crash
        case_sensitive=False,
    )
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins as list."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


# Singleton instance
settings = Settings()
