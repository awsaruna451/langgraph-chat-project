from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.util.http import parse_excluded_urls
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from fastmcp import FastMCP

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.config import settings
from app.logging_config import configure_logging, logger
from app.metrics import HTTPMetricsMiddleware, MCPMetricsMiddleware, register_process_metrics
from app.tools.math_tools import register_math_tools
from app.tracing import configure_tracing

configure_tracing()   # first: the tracer provider must exist before logging is set up
configure_logging()

register_process_metrics()  # cross-platform process_* metrics (psutil)

mcp = FastMCP("cal-server")
mcp.add_middleware(MCPMetricsMiddleware())   # tool calls / errors / latency / protocol requests
register_math_tools(mcp)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """Liveness/readiness probe for load balancers and orchestrators."""
    return JSONResponse({"status": "ok"})


# --- New route: goes right alongside your existing /health route,
# same pattern, same decorator style. ---
@mcp.custom_route("/metrics", methods=["GET"])
async def metrics(request: Request) -> Response:
    """Prometheus scrape endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def main() -> None:
    logger.info(
        "starting mcp-cal-server",
        extra={"host": settings.host, "port": settings.port, "cors_origins": settings.cors_origins_list},
    )
    mcp.run(
        transport="http",
        host=settings.host,
        port=settings.port,
        stateless_http=True,
        middleware=[
            # First = outermost: extracts the incoming `traceparent`, starts the server
            # span, and makes trace_id available to everything below (incl. tool calls).
            Middleware(
                OpenTelemetryMiddleware,
                excluded_urls=parse_excluded_urls("/health,/metrics"),
            ),
            # HTTP request count / latency / errors / in-progress (skips /health, /metrics).
            Middleware(HTTPMetricsMiddleware),
            Middleware(
                CORSMiddleware,
                allow_origins=settings.cors_origins_list,
                allow_credentials=True,
                allow_methods=["GET", "POST"],
                allow_headers=["*"],
            ),
        ],
    )


if __name__ == "__main__":
    main()