from langgraph.graph import StateGraph, END
from typing import TypedDict
from langchain_openai import ChatOpenAI
from typing import Annotated
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
import os

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini")

# =========================
# STATE
# =========================

class MessagesState(TypedDict):
    messages: Annotated[list, add_messages]


# =========================
# NODE
# =========================

def ask_llm(state: MessagesState) -> MessagesState:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


# =========================
# GRAPH + PERSISTENT DB
# =========================

graph = StateGraph(MessagesState)
graph.add_node("ask_llm", ask_llm)
graph.set_entry_point("ask_llm")
graph.add_edge("ask_llm", END)
memory = MemorySaver()
store = InMemoryStore()  
app = graph.compile(checkpointer=memory, store=store)



# =========================
# SEND MESSAGE
# =========================

def send_message(user_id: str, thread_id: str, user_text: str) -> str:

    """Send a message and return the AI reply. This writes to the DB."""
   
    result = app.invoke(
        {"messages": [HumanMessage(content=user_text)]}, config={"configurable": {"thread_id": thread_id, "user_id": user_id}})
    return result["messages"][-1].content


def get_all_thread_ids(user_id: str) -> list[str]:
    """
    Return all thread IDs ordered by most recent activity first.
    memory.list(None) returns checkpoints newest-first, so the first time
    we encounter a thread_id is always its most recent checkpoint.
    """
    seen: dict[str, str] = {}  # thread_id -> latest ts

    for ckpt in memory.list(None):
        thread_id = ckpt.config["configurable"]["thread_id"]
        user_id = ckpt.config["configurable"]["user_id"]
        ts = ckpt.checkpoint.get("ts", "")
        if thread_id not in seen:
            seen[thread_id] = ts  # first encounter = most recent

    return sorted(seen, key=lambda t: seen[t], reverse=False)


def get_conversation(thread_id: str) -> list[dict]:
    """
    Read the full conversation for thread_id from the DB.

    memory.list(config) returns CheckpointTuple objects newest-first.
    The very first (latest) checkpoint always holds the full accumulated
    message list in checkpoint["channel_values"]["messages"], so we only
    need that one — no manual msgpack decoding, no writes-table parsing.

    Returns:
        [{"role": "human" | "ai", "content": "..."}, ...]
    """

    print(thread_id)
    config = {"configurable": {"thread_id": thread_id}}
    for ckpt in memory.list(config):
        print(thread_id)
        msgs = ckpt.checkpoint.get("channel_values", {}).get("messages", [])
        print(msgs)
        return [{"role": m.type, "content": m.content} for m in msgs]
    return []