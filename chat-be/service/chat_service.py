# service/chat_service.py
import logging
from typing import AsyncGenerator
from fastapi import Request
from application.chat_app_long import (
    get_app,
    send_message,
    stream_message,
    get_all_thread_ids,
    get_conversation,
)

logger = logging.getLogger(__name__)


class ChatService:

    async def send_message(self, user_id: str, thread_id: str, message: str):
        logger.info("send_message thread_id=%s", thread_id)
        response = await send_message(user_id, thread_id, message)
        return response

    async def stream_message(
        self, user_id: str, thread_id: str, message: str, request: Request
    ) -> AsyncGenerator[dict, None]:
        logger.info("stream_message thread_id=%s", thread_id)
        async for event in stream_message(user_id, thread_id, message, request):
            yield event

    def get_all_thread_ids(self, user_id: str):
        logger.info("get_all_thread_ids user_id=%s", user_id)
        return get_all_thread_ids(user_id)

    def get_conversation(self, thread_id: str):
        logger.info("get_conversation thread_id=%s", thread_id)
        return get_conversation(thread_id)