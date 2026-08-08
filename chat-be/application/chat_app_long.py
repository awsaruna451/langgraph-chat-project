
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
from fastapi import Request
import asyncio
import uuid

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", streaming=True)


# =========================
# STATE
# =========================

class MessagesState(TypedDict):
    messages: Annotated[list, add_messages]


# =========================
# NODE
# =========================

async def ask_llm(state: MessagesState, config: RunnableConfig, *, store: BaseStore) -> MessagesState:
    user_id = config["configurable"]["user_id"]
    thread_id = config["configurable"]["thread_id"]
    namespace = (user_id, "memories")

    # 1. Pull everything we know about this user
    memories = store.search(namespace)
    facts = "\n".join(f"- {m.value['text']}" for m in memories)

    system_prompt = "You are a helpful assistant."
    if facts:
        system_prompt += f"\n\nThings you know about this user:\n{facts}"

    # 2. Answer
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = await llm.ainvoke(messages)

    # 3. Save the user's message as a memory
    store.put(namespace, str(uuid.uuid4()), {"text": state["messages"][-1].content})

    # 4. Register this thread as belonging to this user (dedup by using thread_id as the key)
    store.put((user_id, "threads"), thread_id, {"thread_id": thread_id})

    return {"messages": [response]}


# =========================
# GRAPH + DB
# =========================

graph = StateGraph(MessagesState)
graph.add_node("ask_llm", ask_llm)
graph.set_entry_point("ask_llm")
graph.add_edge("ask_llm", END)

memory = MemorySaver()      # short-term: conversation history per thread
store = InMemoryStore()     # long-term: facts per user, across all threads

app = graph.compile(checkpointer=memory, store=store)


# =========================
# SEND MESSAGE
# =========================

def send_message(user_id: str, thread_id: str, user_text: str) -> str:
    """Send a message and return the AI reply."""
    result = app.invoke(
        {"messages": [HumanMessage(content=user_text)]},
        config={"configurable": {"thread_id": thread_id, "user_id": user_id}},
    )
    return result["messages"][-1].content


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

    except asyncio.CancelledError:
        await astream.aclose()
        raise