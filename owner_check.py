"""
Middleware для проверки владельца бота.
Игнорирует все сообщения от пользователей, кроме владельца.
"""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from config import OWNER_ID


class OwnerCheckMiddleware(BaseMiddleware):
    """
    Middleware, проверяющий, что сообщение отправлено владельцем бота.
    Если отправитель не является владельцем — сообщение игнорируется.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Проверяем, что это сообщение
        if isinstance(event, Message):
            user = event.from_user
            if user and user.id != OWNER_ID:
                # Не владелец — игнорируем
                return None

        # Владелец — передаём дальше
        return await handler(event, data)
