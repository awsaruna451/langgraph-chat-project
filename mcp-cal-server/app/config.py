"""Centralized, environment-driven configuration.

All settings are overridable via environment variables (or a local .env
file during development), so nothing environment-specific is hardcoded
into the app itself — this is what makes the same image deployable to
dev, staging, and prod unchanged.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MCP_", extra="ignore")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # CORS - comma-separated list of allowed origins. Never default to "*"
    # in a deployable config; require it to be set explicitly per environment.
    cors_allowed_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


settings = Settings()