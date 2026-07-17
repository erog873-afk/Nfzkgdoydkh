"""
Конфигурация бота.
Загружает настройки из .env файла и предоставляет глобальные константы.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv(Path(__file__).parent / ".env")

# ==================== ТОКЕНЫ И ID ====================

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/bot_database.db")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")

# ==================== ВАЛИДАЦИЯ ====================

def validate_config() -> None:
    """Проверяет обязательные параметры конфигурации."""
    errors: list[str] = []

    if not BOT_TOKEN:
        errors.append("BOT_TOKEN не задан в .env файле")
    if OWNER_ID == 0:
        errors.append("OWNER_ID не задан в .env файле")

    if errors:
        raise ValueError(
            "Ошибки конфигурации:\n" + "\n".join(f"  - {e}" for e in errors)
        )

# ==================== ТЕКСТЫ ====================

DEFAULT_AUTORESPONDER_TEXT: str = (
    "Здравствуйте, {first_name}.\n"
    "Сейчас я не могу ответить.\n"
    "Я обязательно свяжусь с вами позже."
)

# Список переменных, поддерживаемых в автоответчике
SUPPORTED_VARIABLES: list[str] = [
    "{name}",
    "{username}",
    "{first_name}",
    "{last_name}",
    "{time}",
    "{date}",
]
