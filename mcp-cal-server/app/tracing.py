"""OpenTelemetry tracing setup: real trace IDs + W3C Trace Context propagation.

Incoming `traceparent` headers (e.g. from the chat backend) are extracted by
OpenTelemetryMiddleware (see main.py), so this service's logs carry the SAME
trace_id as the caller. Call configure_tracing() before configure_logging().
"""
from opentelemetry import propagate, trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.config import settings


def configure_tracing() -> TracerProvider:
    # The SDK provider generates real IDs; the bare API returns all-zero IDs.
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.service_name,
                "service.version": settings.service_version,
                "deployment.environment": settings.environment,
            }
        )
    )
    trace.set_tracer_provider(provider)

    # Explicit W3C Trace Context (traceparent/tracestate) + baggage.
    propagate.set_global_textmap(
        CompositePropagator([TraceContextTextMapPropagator(), W3CBaggagePropagator()])
    )
    return provider