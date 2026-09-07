import json
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    response = await service.send_message(req.user_id, req.thread_id, req.message)
    return {"response": response}


async def sse_event_generator(request: Request, chat_req: ChatRequest):
    try:
        async for event in service.stream_message(
            chat_req.user_id, chat_req.thread_id, chat_req.message, request
        ):
            yield f"data: {json.dumps(event)}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    return StreamingResponse(
        sse_event_generator(request, req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # prevents nginx from buffering the stream
        },
    )


@app.get("/api/conversation/{thread_id}")
async def conversation(thread_id: str):
    return service.get_conversation(thread_id)


@app.get("/api/conversations")
async def conversations(user_id: str):
    return service.get_all_thread_ids(user_id)