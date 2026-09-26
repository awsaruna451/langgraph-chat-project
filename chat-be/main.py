import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_fastapi_instrumentator import Instrumentator

from core.observability import setup_observability
from core.settings import get_settings
from schema.schemas import ChatRequest
from service.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_service(request: Request) -> ChatService:
    return request.app.state.chat_service


ServiceDep = Annotated[ChatService, Depends(get_service)]


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/api/chat")
async def chat(req: ChatRequest, service: ServiceDep):
    logger.info("chat request received user_id=%s thread_id=%s", req.user_id, req.thread_id)
    try:
        response = await service.send_message(req.user_id, req.thread_id, req.message)
    except Exception:
        # Logged here, inside the request span, so the record carries trace_id.
        logger.exception("chat request failed thread_id=%s", req.thread_id)
        raise HTTPException(status_code=500, detail="Internal error")
    return {"response": response}


async def sse_event_generator(service: ChatService, request: Request, chat_req: ChatRequest):
    started = time.perf_counter()
    logger.info("stream started user_id=%s thread_id=%s", chat_req.user_id, chat_req.thread_id)
    try:
        async for event in service.stream_message(
            chat_req.user_id, chat_req.thread_id, chat_req.message, request
        ):
            yield f"data: {json.dumps(event)}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        logger.info(
            "stream completed thread_id=%s duration_ms=%d",
            chat_req.thread_id,
            (time.perf_counter() - started) * 1000,
        )
    except Exception:
        logger.exception("stream failed thread_id=%s", chat_req.thread_id)
        # Do not leak internal error text to the client.
        yield f"data: {json.dumps({'type': 'error', 'message': 'Internal error'})}\n\n"


@router.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, request: Request, service: ServiceDep):
    return StreamingResponse(
        sse_event_generator(service, request, req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # prevents nginx from buffering the stream
        },
    )


@router.get("/api/conversation/{thread_id}")
async def conversation(thread_id: str, service: ServiceDep):
    logger.info("conversation requested thread_id=%s", thread_id)
    return service.get_conversation(thread_id)


@router.get("/api/conversations")
async def conversations(user_id: str, service: ServiceDep):
    logger.info("conversations requested user_id=%s", user_id)
    return service.get_all_thread_ids(user_id)


def create_app() -> FastAPI:
    settings = get_settings()
    provider = setup_observability(settings)   # first: nothing may log before this

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "service starting name=%s version=%s env=%s",
            settings.service_name, settings.service_version, settings.env,
        )
        yield
        logger.info("service stopping")
        provider.shutdown()                    # flush any pending spans

    app = FastAPI(title=settings.service_name, lifespan=lifespan)
    app.state.chat_service = ChatService()

    Instrumentator().instrument(app).expose(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    # After every add_middleware call, so the span is the outermost layer.
    FastAPIInstrumentor.instrument_app(app, excluded_urls="/health,/metrics")
    return app


app = create_app()