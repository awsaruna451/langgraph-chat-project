"""Math tools exposed over MCP.

Compared to the original example, each tool:
- logs via the structured logger instead of print()
- raises fastmcp.exceptions.ToolError for invalid input, so the client
  gets a proper MCP-level error instead of an unhandled exception /
  stack trace (which could also leak internals)
- has a docstring the MCP client can display to an LLM as tool guidance
"""
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from app.logging_config import logger


def register_math_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def add(a: float, b: float) -> float:
        """Add two numbers and return the sum."""
        logger.info("add called", extra={"a": a, "b": b})
        return a + b

    @mcp.tool()
    def subtract(a: float, b: float) -> float:
        """Subtract b from a and return the difference."""
        logger.info("subtract called", extra={"a": a, "b": b})
        return a - b

    @mcp.tool()
    def multiply(a: float, b: float) -> float:
        """Multiply two numbers and return the product."""
        logger.info("multiply called", extra={"a": a, "b": b})
        return a * b

    @mcp.tool()
    def divide(a: float, b: float) -> float:
        """Divide a by b and return the quotient. b must not be zero."""
        logger.info("divide called", extra={"a": a, "b": b})
        if b == 0:
            logger.warning("divide by zero rejected", extra={"a": a, "b": b})
            raise ToolError("Cannot divide by zero.")
        return a / b
