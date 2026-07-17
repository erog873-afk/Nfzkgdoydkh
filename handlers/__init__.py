"""Модуль обработчиков команд и событий бота."""

from .start import router as start_router
from .autoresponder import router as autoresponder_router
from .settings import router as settings_router
from .status import router as status_router
from .info import router as info_router
from .monitoring import router as monitoring_router

__all__ = [
    "start_router",
    "autoresponder_router",
    "settings_router",
    "status_router",
    "info_router",
    "monitoring_router",
]
