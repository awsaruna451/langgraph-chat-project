"""Tracing + logging setup. Call setup_observability() once, before the app is built."""
import logging
import logging.config

from opentelemetry import propagate, trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from core.settings import Settings

# {app} is filled with the service name from settings (OTEL_SERVICE_NAME) at setup time.
_TEXT_FORMAT = (
    "%(asctime)s | %(levelname)-8s | {app} | %(name)s | "
    "trace_id=%(otelTraceID)s span_id=%(otelSpanID)s | %(message)s"
)
_JSON_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s %(otelTraceID)s %(otelSpanID)s"
_OTEL_DEFAULTS = {"otelTraceID": "-", "otelSpanID": "-"}


def _setup_tracing(settings: Settings) -> TracerProvider:
    # The SDK provider is what generates real IDs; the bare API returns all-zero IDs.
    # Sampling is configured with the standard OTEL_TRACES_SAMPLER / _ARG env vars.
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.service_name,
                "service.version": settings.service_version,
                "deployment.environment": settings.env,
            }
        )
    )
    if settings.otlp_enabled:
        # Only when an endpoint is configured. Endpoint, headers and timeout come
        # from the standard OTEL_EXPORTER_OTLP_* env vars.
        # Needs: pip install opentelemetry-exporter-otlp-proto-http
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    trace.set_tracer_provider(provider)
    return provider


def _setup_logging(settings: Settings) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                # "defaults" needs Python 3.12+; older versions ignore it.
                "text": {
                    "format": _TEXT_FORMAT.format(app=settings.service_name.replace("%", "%%")),
                    "defaults": _OTEL_DEFAULTS,
                },
                "json": {
                    "()": "pythonjsonlogger.json.JsonFormatter",
                    "fmt": _JSON_FORMAT,
                    "rename_fields": {
                        "asctime": "timestamp",
                        "levelname": "level",
                        "name": "logger",
                        "otelTraceID": "trace_id",
                        "otelSpanID": "span_id",
                    },
                    "static_fields": {
                        "service": settings.service_name,
                        "version": settings.service_version,
                        "env": settings.env,
                    },
                },
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": settings.log_format,
                }
            },
            "root": {"level": settings.log_level, "handlers": ["stdout"]},
            "loggers": {
                # Route uvicorn through the root handler: one format, one sink.
                "uvicorn": {"handlers": [], "propagate": True},
                "uvicorn.error": {"handlers": [], "propagate": True},
                "uvicorn.access": {"handlers": [], "propagate": True},
                # Chatty libraries
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
            },
        }
    )


def _setup_propagation() -> None:
    # Explicit W3C Trace Context (`traceparent` / `tracestate`) + baggage, so behavior
    # does not depend on the OTEL_PROPAGATORS env var. Used for BOTH extracting the
    # incoming header (FastAPIInstrumentor) and injecting into outgoing calls.
    propagate.set_global_textmap(
        CompositePropagator([TraceContextTextMapPropagator(), W3CBaggagePropagator()])
    )
    # Outgoing HTTP: adds a client span and injects `traceparent` on every httpx call.
    # langchain-mcp-adapters and the OpenAI SDK both use httpx, so your MCP server
    # receives the same trace ID. (Note: this also sends the header to api.openai.com.)
    HTTPXClientInstrumentor().instrument()


def setup_observability(settings: Settings) -> TracerProvider:
    provider = _setup_tracing(settings)
    _setup_propagation()
    # Adds otelTraceID / otelSpanID to every LogRecord. Must run before logging is used.
    # inject_trace_context=True is REQUIRED on current versions: with
    # set_logging_format=False and no inject flag, nothing is injected.
    LoggingInstrumentor().instrument(set_logging_format=False, inject_trace_context=True)
    _setup_logging(settings)
    return provider