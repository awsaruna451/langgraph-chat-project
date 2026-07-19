from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from schema.schemas import ChatRequest
from service.chat_service import ChatService

app = FastAPI()
service = ChatService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat")
def chat(req: ChatRequest):
    response = service.send_message(req.user_id, req.thread_id, req.message)
    return {"response": response}


@app.get("/conversation/{thread_id}")
def conversation(thread_id: str):
    return service.get_conversation(thread_id)


@app.get("/conversations")
def conversations(user_id: str):
    return service.get_all_thread_ids(user_id)