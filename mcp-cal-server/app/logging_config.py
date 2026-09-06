"""Structured (JSON) logging setup.

Replaces the original code's print() calls, which are invisible to any
log aggregator and carry no severity, timestamp, or request context.
JSON output lets this plug straight into CloudWatch Logs, Datadog, etc.
"""
import logging
import sys
from pythonjsonlogger import json as jsonlogger

from app.config import settings


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())

    # Quiet noisy third-party loggers unless we're debugging
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


logger = logging.getLogger("mcp-cal-server")
