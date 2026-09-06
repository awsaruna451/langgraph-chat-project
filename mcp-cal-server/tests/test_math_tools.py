"""Unit tests for the math tools.

Calls the underlying functions directly (via FastMCP's tool manager)
rather than spinning up a live server, so the suite runs fast and needs
no network access.
"""
import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from app.tools.math_tools import register_math_tools


@pytest.fixture
def mcp() -> FastMCP:
    server = FastMCP("test-math-server")
    register_math_tools(server)
    return server


async def _call(mcp: FastMCP, name: str, **kwargs):
    tool = await mcp.get_tool(name)
    return await tool.run(kwargs)


@pytest.mark.asyncio
async def test_add(mcp: FastMCP):
    result = await _call(mcp, "add", a=2, b=3)
    assert result.structured_content == {"result": 5}


@pytest.mark.asyncio
async def test_subtract(mcp: FastMCP):
    result = await _call(mcp, "subtract", a=5, b=3)
    assert result.structured_content == {"result": 2}


@pytest.mark.asyncio
async def test_multiply(mcp: FastMCP):
    result = await _call(mcp, "multiply", a=4, b=3)
    assert result.structured_content == {"result": 12}


@pytest.mark.asyncio
async def test_divide(mcp: FastMCP):
    result = await _call(mcp, "divide", a=10, b=2)
    assert result.structured_content == {"result": 5}


@pytest.mark.asyncio
async def test_divide_by_zero_raises(mcp: FastMCP):
    with pytest.raises(ToolError):
        await _call(mcp, "divide", a=10, b=0)
