"""
Вспомогательные функции для обработки сообщений и работы с датами.
"""

from datetime import datetime
from typing import Optional

import pytz

from config import TIMEZONE


def format_datetime(dt: Optional[datetime] = None, tz_name: str = TIMEZONE) -> str:
    """Форматирует дату и время в читаемый вид."""
    if dt is None:
        dt = datetime.now()
    tz = pytz.timezone(tz_name)
    local_dt = dt.astimezone(tz) if dt.tzinfo else tz.localize(dt)
    return local_dt.strftime("%d.%m.%Y %H:%M:%S")


def get_message_type(message) -> str:
    """Определяет тип сообщения."""
    if message.text:
        return "текст"
    elif message.photo:
        return "фото"
    elif message.video:
        return "видео"
    elif message.video_note:
        return "кружок"
    elif message.voice:
        return "голосовое"
    elif message.document:
        doc = message.document
        if doc.mime_type:
            if doc.mime_type.startswith("audio"):
                return "аудиофайл"
            elif doc.mime_type.startswith("video"):
                return "видеофайл"
        return "документ"
    elif message.animation:
        return "GIF"
    elif message.sticker:
        return "стикер"
    elif message.contact:
        return "контакт"
    elif message.location:
        return "геолокация"
    elif message.venue:
        return "место"
    elif message.poll:
        return "опрос"
    elif message.dice:
        return "дайс"
    elif message.invoice:
        return "инвойс"
    elif message.game:
        return "игра"
    elif message.video_chat_started:
        return "видеозвонок"
    elif message.video_chat_ended:
        return "конец видеозвонка"
    elif message.video_chat_participants_invited:
        return "приглашение в видеозвонок"
    elif message.video_chat_scheduled:
        return "запланированный видеозвонок"
    elif message.story:
        return "сторис"
    elif message.giveaway:
        return "розыгрыш"
    elif message.giveaway_winners:
        return "победители розыгрыша"
    elif message.giveaway_created:
        return "создан розыгрыш"
    elif message.chat_shared:
        return "поделённый чат"
    elif message.users_shared:
        return "поделённые пользователи"
    elif message.write_access_allowed:
        return "разрешение на написание"
    elif message.chat_boost_added:
        return "добавлен буст чата"
    elif message.effect_id:
        return "эффект"
    elif message.link_preview_options:
        return "ссылка"
    else:
        return "неизвестный тип"


def get_message_content(message) -> str:
    """Извлекает текстовое содержимое сообщения."""
    if message.text:
        return message.text
    elif message.caption:
        return message.caption
    elif message.photo:
        return "[фото]"
    elif message.video:
        return "[видео]"
    elif message.video_note:
        return "[кружок]"
    elif message.voice:
        return "[голосовое]"
    elif message.document:
        return f"[документ: {message.document.file_name}]"
    elif message.animation:
        return "[GIF]"
    elif message.sticker:
        emoji = message.sticker.emoji or ""
        return f"[стикер {emoji}]"
    elif message.contact:
        c = message.contact
        return f"[контакт: {c.first_name} {c.last_name or ''} {c.phone_number}]"
    elif message.location:
        loc = message.location
        return f"[геолокация: {loc.latitude}, {loc.longitude}]"
    elif message.venue:
        v = message.venue
        return f"[место: {v.title}]"
    elif message.poll:
        return f"[опрос: {message.poll.question}]"
    elif message.dice:
        return f"[дайс: {message.dice.emoji}]"
    else:
        return "[медиа]"


def fill_template(
    template: str,
    first_name: str = "",
    last_name: str = "",
    username: str = "",
    user_id: int = 0
) -> str:
    """Заполняет шаблон автоответчика переменными."""
    name = f"{first_name} {last_name}".strip()
    now = datetime.now()

    return template.format(
        name=name or "Пользователь",
        username=f"@{username}" if username else "нет username",
        first_name=first_name or "Пользователь",
        last_name=last_name or "",
        time=now.strftime("%H:%M"),
        date=now.strftime("%d.%m.%Y"),
    )
