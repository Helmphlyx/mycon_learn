"""Application configuration using environment variables."""

import secrets
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "sqlite:///./mycon_learn.db"

    # Authentication
    app_password: str = ""  # Set this to enable password protection
    secret_key: str = secrets.token_urlsafe(32)  # For session signing

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # CORS (comma-separated origins, or * for all)
    cors_origins: str = "*"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def auth_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return bool(self.app_password)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
