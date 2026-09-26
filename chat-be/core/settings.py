"""Environment-driven configuration (12-factor). No hard-coded deploy values."""
import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    service_name: str
    service_version: str
    env: str
    log_level: str
    log_format: str          # "json" (prod / log aggregators) or "text" (local dev)
    cors_origins: tuple[str, ...]
    otlp_enabled: bool       # True when OTEL_EXPORTER_OTLP_ENDPOINT is set


@lru_cache
def get_settings() -> Settings:
    env = os.getenv("APP_ENV", "dev").lower()
    return Settings(
        service_name=os.getenv("OTEL_SERVICE_NAME", "chat-service"),
        service_version=os.getenv("APP_VERSION", "0.0.0"),
        env=env,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_format=os.getenv("LOG_FORMAT", "text" if env == "dev" else "json").lower(),
        cors_origins=tuple(
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        ),
        otlp_enabled=bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
    )