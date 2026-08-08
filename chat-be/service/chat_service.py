# service/chat_service.py
from typing import AsyncGenerator
from fastapi import Request
from application.chat_app_long import (
    app,
    send_message,
    stream_message,
    get_all_thread_ids,
    get_conversation,
)


class ChatService:

    def send_message(self, user_id: str, thread_id: str, message: str):
        response = send_message(user_id, thread_id, message)
        return response

    async def stream_message(
        self, user_id: str, thread_id: str, message: str, request: Request
    ) -> AsyncGenerator[dict, None]:
        async for event in stream_message(user_id, thread_id, message, request):
            yield event

    def get_all_thread_ids(self, user_id: str):
        return get_all_thread_ids(user_id)

    def get_conversation(self, thread_id: str):
        return get_conversation(thread_id)