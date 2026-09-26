"""Prometheus metrics for the MCP server.

Layers (each answers a different question):
  1. HTTP / transport   -> HTTPMetricsMiddleware   (is the server reachable, fast, healthy?)
  2. MCP protocol/tools -> MCPMetricsMiddleware    (which tool is slow, failing, busy?)
  3. Process / runtime  -> ProcessCollector below (psutil: same code path on every OS)
  4. Per-tool business  -> the `tool_name` label on the tool metrics (no extra metrics needed)

Cardinality rules: labels only ever hold values from a small fixed set
(known paths, MCP method names, registered tool names). Client-supplied
strings (unknown tool names, arbitrary URLs) are collapsed to "unknown"/"other".
"""
import time

import psutil

from fastmcp.exceptions import NotFoundError
from fastmcp.server.middleware import Middleware, MiddlewareContext
from prometheus_client import PROCESS_COLLECTOR, REGISTRY, Counter, Gauge, Histogram, Info
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
from prometheus_client.registry import Collector
from starlette.types import ASGIApp, Message, Receive, Scope, Send

try:
    import resource  # stdlib, POSIX only (Linux/macOS); absent on Windows
except ImportError:  # pragma: no cover
    resource = None

from app.config import settings
from app.logging_config import logger

# Tools here are fast; start the buckets at 1ms.
_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)

# --- Build info: one series, lets you correlate a regression with a deploy ---
SERVER_INFO = Info("mcp_server", "MCP server build information")
SERVER_INFO.info(
    {
        "service": settings.service_name,
        "version": settings.service_version,
        "env": settings.environment,
    }
)

# --- 1. HTTP / transport ---
HTTP_REQUESTS = Counter(
    "http_requests_total", "HTTP requests", ["method", "path", "status"]
)  # errors = status=~"5.."
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "path"], buckets=_BUCKETS
)
HTTP_IN_PROGRESS = Gauge(
    "http_requests_in_progress", "HTTP requests currently being handled", ["method"]
)

# --- 2. MCP protocol + tools (names/labels of the two original metrics are unchanged) ---
MCP_REQUESTS = Counter(
    "mcp_requests_total", "MCP protocol requests (tools/list, tools/call, ...)", ["method", "status"]
)
TOOL_CALLS = Counter("mcp_tool_calls_total", "Total MCP tool calls", ["tool_name", "status"])
TOOL_LATENCY = Histogram(
    "mcp_tool_call_duration_seconds", "MCP tool call latency", ["tool_name"], buckets=_BUCKETS
)
TOOL_ERRORS = Counter(
    "mcp_tool_errors_total", "MCP tool call errors", ["tool_name", "error_type"]
)
TOOL_IN_PROGRESS = Gauge("mcp_tool_calls_in_progress", "Tool calls currently executing")


# =========================
# HTTP middleware (pure ASGI: safe with streaming responses)
# =========================

_KNOWN_PATHS = {"/mcp", "/health", "/metrics"}
_SKIP_PATHS = {"/health", "/metrics"}  # probe/scrape traffic would drown the real signal


class HTTPMetricsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"].rstrip("/") or "/"
        if path in _SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        label_path = path if path in _KNOWN_PATHS else "other"
        method = scope["method"]
        status = 500  # what we report if the app raises before sending a response
        started = time.perf_counter()
        HTTP_IN_PROGRESS.labels(method).inc()

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            HTTP_IN_PROGRESS.labels(method).dec()
            HTTP_REQUESTS.labels(method, label_path, str(status)).inc()
            HTTP_LATENCY.labels(method, label_path).observe(time.perf_counter() - started)


# =========================
# MCP middleware (FastMCP server-side hooks)
# =========================

class MCPMetricsMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        """Every protocol request: tools/list, tools/call, ping, ..."""
        status = "success"
        try:
            return await call_next(context)
        except Exception:
            status = "error"
            raise
        finally:
            MCP_REQUESTS.labels(context.method or "unknown", status).inc()

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool = context.message.name
        started = time.perf_counter()
        status = "success"
        TOOL_IN_PROGRESS.inc()
        try:
            return await call_next(context)
        except Exception as exc:
            status = "error"
            if isinstance(exc, NotFoundError):
                tool = "unknown"  # never let a client-supplied name become a label value
            # FastMCP wraps tool failures; report the original exception type when present
            root = exc.__cause__ or exc
            TOOL_ERRORS.labels(tool, type(root).__name__).inc()
            raise
        finally:
            elapsed = time.perf_counter() - started
            TOOL_IN_PROGRESS.dec()
            TOOL_CALLS.labels(tool, status).inc()
            TOOL_LATENCY.labels(tool).observe(elapsed)
            # Metrics tell you THAT it's slow/failing; this line + trace_id tells you WHICH call.
            logger.info(
                "tool call finished",
                extra={"tool": tool, "status": status, "duration_ms": round(elapsed * 1000, 1)},
            )


# =========================
# 3. Process metrics
# =========================
# prometheus_client's built-in process collector reads /proc, so it only works on
# Linux. This collector uses psutil instead: ONE code path on Linux, macOS and
# Windows (dev/prod parity), exposing the same standard `process_*` names so any
# existing dashboard or alert keeps working. GC (python_gc_*) and python_info are
# already OS-independent in prometheus_client and are left as they are.

class ProcessCollector(Collector):
    def __init__(self) -> None:
        self._proc = psutil.Process()
        self._warned = False

    def collect(self):
        proc = self._proc
        try:
            with proc.oneshot():  # batches the underlying syscalls
                cpu = proc.cpu_times()
                mem = proc.memory_info()
                start_time = proc.create_time()
                # Capability checks (not OS checks): these don't exist on every platform.
                open_fds = proc.num_fds() if hasattr(proc, "num_fds") else None
        except (psutil.Error, OSError):
            # One failing collector must not turn the whole /metrics scrape into a 500.
            if not self._warned:
                logger.warning("process metrics collection failed", exc_info=True)
                self._warned = True
            return

        yield CounterMetricFamily(
            "process_cpu_seconds", "Total user and system CPU time in seconds.",
            value=cpu.user + cpu.system,
        )
        yield GaugeMetricFamily(
            "process_resident_memory_bytes", "Resident memory size in bytes.", value=mem.rss
        )
        yield GaugeMetricFamily(
            "process_virtual_memory_bytes", "Virtual memory size in bytes.", value=mem.vms
        )
        yield GaugeMetricFamily(
            "process_start_time_seconds", "Start time of the process since unix epoch.",
            value=start_time,
        )
        if open_fds is not None:
            yield GaugeMetricFamily(
                "process_open_fds", "Number of open file descriptors.", value=open_fds
            )
        if resource is not None:
            soft_limit = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
            if soft_limit != resource.RLIM_INFINITY:
                yield GaugeMetricFamily(
                    "process_max_fds", "Maximum number of open file descriptors.",
                    value=soft_limit,
                )


def register_process_metrics() -> None:
    """Swap prometheus_client's /proc-based collector for the psutil one. Idempotent."""
    try:
        REGISTRY.unregister(PROCESS_COLLECTOR)
    except KeyError:
        pass  # already unregistered (e.g. called twice)
    try:
        REGISTRY.register(ProcessCollector())
    except ValueError:
        pass  # already registered