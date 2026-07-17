"""
Модуль логирования.
Настраивает логгер для записи действий и ошибок.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from config import LOG_LEVEL, OWNER_ID


# Создаём папку для логов
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Формат логов
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger() -> logging.Logger:
    """Настраивает и возвращает корневой логгер."""
    logger = logging.getLogger("bot")
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # Обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    # Обработчик для файла
    log_file = LOG_DIR / f"bot_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# Глобальный экземпляр логгера
logger = setup_logger()


def log_action(action: str, details: str = "") -> None:
    """Логирует действие бота."""
    message = f"[ACTION] {action}"
    if details:
        message += f" | {details}"
    logger.info(message)


def log_error(error: Exception, context: str = "") -> None:
    """Логирует ошибку."""
    message = f"[ERROR] {type(error).__name__}: {error}"
    if context:
        message += f" | Контекст: {context}"
    logger.error(message, exc_info=True)


def log_message_event(event_type: str, user_id: int, chat_id: int, details: str = "") -> None:
    """Логирует событие, связанное с сообщением."""
    message = f"[EVENT] {event_type} | user={user_id} chat={chat_id}"
    if details:
        message += f" | {details}"
    logger.info(message)
