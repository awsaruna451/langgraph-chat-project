import os
import uuid
import asyncio
import requests

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
from fastapi import Request
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-cal-server:8000/mcp")


# =========================
# LOCAL TOOLS
# =========================

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a given city name.

    Args:
        city: The city name, e.g. "Negombo" or "London,UK".
    """
    if not OPENWEATHER_API_KEY:
        return "Weather tool is not configured: missing OPENWEATHER_API_KEY."

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError:
        if resp.status_code == 404:
            return f"Could not find weather for '{city}'. Check the city name."
        return f"Weather API error: {resp.status_code} - {resp.text}"
    except requests.exceptions.RequestException as e:
        return f"Failed to reach weather service: {e}"

    desc = data["weather"][0]["description"]
    temp = data["main"]["temp"]
    feels_like = data["main"]["feels_like"]
    humidity = data["main"]["humidity"]
    wind = data["wind"]["speed"]

    return (
        f"Weather in {data.get('name', city)}: {desc}, "
        f"temperature {temp}°C (feels like {feels_like}°C), "
        f"humidity {humidity}%, wind {wind} m/s."
    )


@tool
def get_stock_quote(symbol: str) -> str:
    """Get the latest stock quote (price, change, volume, etc.) for a given ticker symbol.

    Args:
        symbol: The stock ticker symbol, e.g. "AAPL", "MSFT", "IBM".
    """
    if not ALPHAVANTAGE_API_KEY:
        return "Stock quote tool is not configured: missing ALPHAVANTAGE_API_KEY."

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": ALPHAVANTAGE_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return f"Failed to reach Alpha Vantage: {e}"

    # Alpha Vantage returns 200 OK even for errors/rate limits, so check the payload.
    if "Note" in data:
        return "Alpha Vantage rate limit reached. Please try again in a moment."
    if "Information" in data:
        return f"Alpha Vantage error: {data['Information']}"

    quote = data.get("Global Quote", {})
    if not quote or not quote.get("01. symbol"):
        return f"Could not find a quote for '{symbol}'. Check the ticker symbol."

    price = quote.get("05. price")
    change = quote.get("09. change")
    change_pct = quote.get("10. change percent")
    volume = quote.get("06. volume")
    prev_close = quote.get("08. previous close")
    latest_day = quote.get("07. latest trading day")

    return (
        f"Quote for {quote.get('01. symbol', symbol)} (as of {latest_day}): "
        f"price ${price}, change {change} ({change_pct}), "
        f"previous close ${prev_close}, volume {volume}."
    )


LOCAL_TOOLS = [get_weather, get_stock_quote]

llm = ChatOpenAI(model="gpt-4o-mini", streaming=True)


# =========================
# MCP CLIENT
# =========================

mcp_servers = {
    "cal-server": {
        "url": MCP_SERVER_URL,
        "transport": "streamable_http",
    }
}

mcp_client = MultiServerMCPClient(mcp_servers)


async def load_mcp_tools() -> list:
    """Load tool objects from all configured MCP servers.

    Returns an empty list (and logs) instead of raising, so a single
    misbehaving/offline MCP server doesn't take the whole app down.
    """
    try:
        mcp_tools = await mcp_client.get_tools()
        print(f"[MCP] Loaded {len(mcp_tools)} tool(s): "
              f"{[t.name for t in mcp_tools]}")
        return mcp_tools
    except Exception as e:
        print(f"[MCP] Failed to load MCP tools: {e}")
        return []


# =========================
# STATE
# =========================

class MessagesState(TypedDict):
    messages: Annotated[list, add_messages]


# =========================
# NODE FACTORY
# =========================

def make_ask_llm(llm_with_tools):
    """Build the ask_llm node bound to a specific llm-with-tools instance.

    We need this factory because the tool list (and therefore the bound
    llm) isn't known until MCP tools have been loaded asynchronously.
    """

    async def ask_llm(state: MessagesState, config: RunnableConfig, *, store: BaseStore) -> MessagesState:
        user_id = config["configurable"]["user_id"]
        thread_id = config["configurable"]["thread_id"]
        namespace = (user_id, "memories")

        # 1. Pull everything we know about this user
        memories = store.search(namespace)
        facts = "\n".join(f"- {m.value['text']}" for m in memories)

        system_prompt = (
            "You are a helpful, general-purpose assistant. Answer the user's "
            "questions directly using your own knowledge and reasoning.\n\n"
            "You additionally have access to tools for real-time or external "
            "data that you cannot know accurately on your own (e.g. current "
            "weather, live stock prices, and other connected services). Call "
            "a tool ONLY when the user's request actually needs that live "
            "data. For everything else — general knowledge, explanations, "
            "writing, coding, advice, conversation — just answer normally "
            "without calling a tool. Never guess data a tool can give you "
            "accurately."
        )
        if facts:
            system_prompt += f"\n\nThings you know about this user:\n{facts}"

        # 2. Answer (may include tool calls)
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = await llm_with_tools.ainvoke(messages)

        # 3. Save the user's message as a memory (only plain human turns,
        #    not the re-entry after a tool call/response round-trip)
        last_msg = state["messages"][-1]
        if isinstance(last_msg, HumanMessage):
            store.put(namespace, str(uuid.uuid4()), {"text": last_msg.content})

        # 4. Register this thread as belonging to this user
        store.put((user_id, "threads"), thread_id, {"thread_id": thread_id})

        return {"messages": [response]}

    return ask_llm


# =========================
# GRAPH + DB (lazy async init)
# =========================

memory = MemorySaver()      # short-term: conversation history per thread
store = InMemoryStore()     # long-term: facts per user, across all threads

_app_cache: dict = {}
_app_lock = asyncio.Lock()


async def get_app():
    """Build (once) and return the compiled graph, with MCP tools loaded.

    MCP tool discovery is async, so the graph can't be built at import
    time. This lazily builds it on first use and caches the result.
    """
    if "app" in _app_cache:
        return _app_cache["app"]

    async with _app_lock:
        # Re-check in case another coroutine built it while we waited.
        if "app" in _app_cache:
            return _app_cache["app"]

        mcp_tools = await load_mcp_tools()
        tools = LOCAL_TOOLS + mcp_tools

        llm_with_tools = llm.bind_tools(tools)
        tool_node = ToolNode(tools)

        graph = StateGraph(MessagesState)
        graph.add_node("ask_llm", make_ask_llm(llm_with_tools))
        graph.add_node("tools", tool_node)
        graph.set_entry_point("ask_llm")
        graph.add_conditional_edges("ask_llm", tools_condition)
        graph.add_edge("tools", "ask_llm")

        compiled = graph.compile(checkpointer=memory, store=store)
        _app_cache["app"] = compiled
        return compiled


# =========================
# SEND MESSAGE
# =========================

async def send_message(user_id: str, thread_id: str, user_text: str) -> str:
    """Send a message and return the AI reply."""
    app = await get_app()
    result = await app.ainvoke(
        {"messages": [HumanMessage(content=user_text)]},
        config={"configurable": {"thread_id": thread_id, "user_id": user_id}},
    )
    return result["messages"][-1].content


def send_message_sync(user_id: str, thread_id: str, user_text: str) -> str:
    """Convenience sync wrapper for scripts/tests (not for use inside FastAPI)."""
    return asyncio.run(send_message(user_id, thread_id, user_text))


def get_all_thread_ids(user_id: str) -> list[str]:
    items = store.search((user_id, "threads"))
    return [item.value["thread_id"] for item in items]


def get_conversation(thread_id: str) -> list[dict]:
    config = {"configurable": {"thread_id": thread_id}}
    for ckpt in memory.list(config):
        msgs = ckpt.checkpoint.get("channel_values", {}).get("messages", [])
        return [{"role": m.type, "content": m.content} for m in msgs]
    return []


def get_user_memories(user_id: str) -> list[str]:
    """See everything stored long-term for a user."""
    return [m.value["text"] for m in store.search((user_id, "memories"))]


async def stream_message(user_id: str, thread_id: str, user_text: str, request: Request):
    app = await get_app()
    config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}

    astream = app.astream_events(
        {"messages": [HumanMessage(content=user_text)]},
        config=config,
        version="v2",
    )

    try:
        async for event in astream:
            if await request.is_disconnected():
                # actually close the underlying generator, not just stop yielding
                await astream.aclose()
                break

            kind = event["event"]

            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield {"type": "token", "content": chunk.content}

            elif kind == "on_tool_start":
                yield {
                    "type": "tool_start",
                    "tool": event["name"],
                    "input": event["data"].get("input"),
                }

            elif kind == "on_tool_end":
                yield {
                    "type": "tool_end",
                    "tool": event["name"],
                    "output": str(event["data"].get("output", ""))[:500],
                }

    except asyncio.CancelledError:
        await astream.aclose()
        raise