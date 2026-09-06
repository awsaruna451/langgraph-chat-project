from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from fastmcp import FastMCP

from app.config import settings
from app.logging_config import configure_logging, logger
from app.tools.math_tools import register_math_tools

configure_logging()

mcp = FastMCP("cal-server")
register_math_tools(mcp)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """Liveness/readiness probe for load balancers and orchestrators."""
    return JSONResponse({"status": "ok"})


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
            Middleware(
                CORSMiddleware,
                allow_origins=settings.cors_origins_list,
                allow_credentials=True,
                allow_methods=["GET", "POST"],
                allow_headers=["*"],
            )
        ],
    )


if __name__ == "__main__":
    main()