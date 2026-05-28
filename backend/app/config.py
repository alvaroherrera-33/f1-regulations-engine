from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Admin API key -- required to access /api/upload, /api/admin/*, POST /api/sync/check
    # Set ADMIN_API_KEY in your deployment environment. If unset, admin routes are disabled.
    admin_api_key: str = Field(default="")

    # SQL logging -- enable only in dev, never in production
    sql_echo: bool = Field(default=False)

    # HMAC secret for feedback tokens.  Auto-generated per-process if left empty
    # (tokens expire on server restart).  Set a stable value in production to
    # survive Render restarts.
    feedback_hmac_secret: str = Field(default="")

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
