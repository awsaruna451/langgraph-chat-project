"""Structured (JSON) logging setup.

Replaces the original code's print() calls, which are invisible to any
log aggregator and carry no severity, timestamp, or request context.
JSON output lets this plug straight into CloudWatch Logs, Datadog, etc.

Every record carries trace_id / span_id (OpenTelemetry) and service/env/version.
"""
import logging
import sys

from opentelemetry.instrumentation.logging import LoggingInstrumentor
from pythonjsonlogger import json as jsonlogger

from app.config import settings


def configure_logging() -> None:
    # Adds otelTraceID / otelSpanID to every LogRecord. Must run before logging is used.
    # inject_trace_context=True is required on current versions; with
    # set_logging_format=False and no inject flag, nothing is injected.
    LoggingInstrumentor().instrument(set_logging_format=False, inject_trace_context=True)

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s %(otelTraceID)s %(otelSpanID)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "otelTraceID": "trace_id",
            "otelSpanID": "span_id",
        },
        static_fields={
            "service": settings.service_name,
            "env": settings.environment,
            "version": settings.service_version,
        },
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())

    # Quiet noisy third-party loggers unless we're debugging
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


logger = logging.getLogger("mcp-cal-server")