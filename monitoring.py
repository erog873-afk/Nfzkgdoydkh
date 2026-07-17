"""
Обработчик мониторинга сообщений.
Отслеживает удалённые и изменённые сообщения.
"""

import json
from datetime import datetime
from typing import Optional

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)

from config import OWNER_ID
from database import (
    save_deleted_message, save_edited_message,
    get_deleted_messages, get_edited_messages,
    update_stats, get_setting, set_setting
)
from utils.helpers import (
    get_message_type, get_message_content,
    format_datetime
)
from logger import log_action, log_error

router = Router(name="monitoring")


# ==================== ХРАНИЛИЩЕ СООБЩЕНИЙ ====================

# Словарь для хранения последних сообщений (для отслеживания изменений)
# Ключ: message_id, значение: данные сообщения
message_store: dict[int, dict] = {}

# Словарь для хранения business_connection_id по user_id
# Ключ: user_id, значение: business_connection_id
business_connections: dict[int, str] = {}


async def store_message(message: Message) -> None:
    """Сохраняет сообщение для последующего отслеживания изменений."""
    if not message.from_user:
        return

    user = message.from_user
    message_data = {
        "chat_id": message.chat.id,
        "user_id": user.id,
        "user_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
        "username": user.username or "",
        "message_type": get_message_type(message),
        "content": get_message_content(message),
        "date": message.date,
        "business_connection_id": getattr(message, "business_connection_id", None),
    }

    message_store[message.message_id] = message_data

    # Сохраняем business_connection_id если есть
    biz_conn = getattr(message, "business_connection_id", None)
    if biz_conn:
        business_connections[user.id] = biz_conn
        await set_setting("business_connections", business_connections)

    # Ограничиваем размер хранилища
    if len(message_store) > 10000:
        # Удаляем старые записи
        oldest_keys = sorted(message_store.keys())[:5000]
        for key in oldest_keys:
            del message_store[key]


async def get_stored_message(message_id: int) -> Optional[dict]:
    """Получает сохранённое сообщение по ID."""
    return message_store.get(message_id)


async def get_business_connection_id(user_id: int) -> Optional[str]:
    """Получает business_connection_id для пользователя."""
    # Сначала из памяти
    if user_id in business_connections:
        return business_connections[user_id]
    # Затем из базы
    saved = await get_setting("business_connections", {})
    if isinstance(saved, dict) and str(user_id) in saved:
        return saved[str(user_id)]
    return None


# ==================== ОБРАБОТЧИКИ ====================

@router.message()
async def handle_message(message: Message) -> None:
    """Обрабатывает все входящие сообщения для мониторинга."""
    try:
        # Сохраняем сообщение для отслеживания изменений
        await store_message(message)

        # Обновляем статистику
        await update_stats("messages_processed")

        # Обрабатываем автоответчик
        from .autoresponder import handle_auto_reply
        await handle_auto_reply(message)

    except Exception as e:
        log_error(e, f"Ошибка обработки сообщения {message.message_id}")


# ==================== МОНИТОРИНГ УДАЛЕНИЙ ====================

async def notify_owner_deleted(
    bot,
    chat_id: int,
    user_id: int,
    user_name: str,
    username: str,
    message_type: str,
    content: str,
    attachment: Optional[str] = None
) -> None:
    """Отправляет уведомление владельцу об удалённом сообщении."""
    try:
        # Сохраняем в базу
        await save_deleted_message(
            chat_id=chat_id,
            user_id=user_id,
            user_name=user_name,
            username=username,
            message_type=message_type,
            content=content,
            attachment=attachment
        )

        # Проверяем, включены ли уведомления
        notifications = await get_setting("notifications_enabled", True)
        if not notifications:
            return

        # Формируем уведомление
        now = datetime.now()
        username_display = f"@{username}" if username else "нет username"

        text = (
            "🗑 <b>Удалённое сообщение</b>\n\n"
            f"👤 Пользователь: <b>{user_name}</b>\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📛 Username: {username_display}\n"
            f"💬 Тип: {message_type}\n"
            f"📅 Дата: {format_datetime(now)}\n\n"
            f"📝 Содержимое:\n<code>{content[:1000]}</code>"
        )

        if attachment:
            text += f"\n\n📎 Вложение: {attachment}"

        await bot.send_message(
            chat_id=OWNER_ID,
            text=text,
            parse_mode="HTML"
        )

        log_action("MONITORING", f"Уведомлено об удалении от {user_id}")

    except Exception as e:
        log_error(e, "Ошибка отправки уведомления об удалении")


async def notify_owner_edited(
    bot,
    chat_id: int,
    user_id: int,
    user_name: str,
    username: str,
    message_type: str,
    old_content: str,
    new_content: str
) -> None:
    """Отправляет уведомление владельцу об изменённом сообщении."""
    try:
        # Сохраняем в базу
        await save_edited_message(
            chat_id=chat_id,
            user_id=user_id,
            user_name=user_name,
            username=username,
            message_type=message_type,
            old_content=old_content,
            new_content=new_content
        )

        # Проверяем, включены ли уведомления
        notifications = await get_setting("notifications_enabled", True)
        if not notifications:
            return

        # Формируем уведомление
        username_display = f"@{username}" if username else "нет username"
        now = datetime.now()

        text = (
            "✏ <b>Изменённое сообщение</b>\n\n"
            f"👤 Пользователь: <b>{user_name}</b>\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📛 Username: {username_display}\n"
            f"💬 Тип: {message_type}\n"
            f"🕐 Время изменения: {format_datetime(now)}\n\n"
            f"<b>СТАРОЕ СООБЩЕНИЕ:</b>\n"
            f"<code>{old_content[:500]}</code>\n\n"
            f"↓\n\n"
            f"<b>НОВОЕ СООБЩЕНИЕ:</b>\n"
            f"<code>{new_content[:500]}</code>"
        )

        await bot.send_message(
            chat_id=OWNER_ID,
            text=text,
            parse_mode="HTML"
        )

        log_action("MONITORING", f"Уведомлено об изменении от {user_id}")

    except Exception as e:
        log_error(e, "Ошибка отправки уведомления об изменении")


# ==================== ПРОСМОТР ИСТОРИИ ====================

@router.callback_query(F.data == "menu:deleted")
async def callback_deleted_menu(callback_query: CallbackQuery) -> None:
    """Показывает последние удалённые сообщения."""
    if callback_query.from_user.id != OWNER_ID:
        return

    messages = await get_deleted_messages(limit=5)

    if not messages:
        text = "🗑 <b>Удалённые сообщения</b>\n\nПока не обнаружено."
    else:
        text = "🗑 <b>Последние удалённые сообщения:</b>\n\n"
        for i, msg in enumerate(messages, 1):
            username = f"@{msg['username']}" if msg['username'] else "нет username"
            text += (
                f"<b>{i}.</b> {msg['user_name']} ({username})\n"
                f"   Тип: {msg['message_type']} | {msg['created_at']}\n"
                f"   Содержимое: <code>{msg['content'][:100]}</code>\n\n"
            )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Очистить историю", callback_data="del:clear")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")],
    ])

    await callback_query.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.callback_query(F.data == "del:clear")
async def callback_clear_deleted(callback_query: CallbackQuery) -> None:
    """Очищает историю удалённых сообщений."""
    if callback_query.from_user.id != OWNER_ID:
        return

    from database import clear_deleted_messages
    await clear_deleted_messages()

    await callback_query.message.edit_text(
        "🗑 История удалённых сообщений очищена!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")]
        ])
    )
    await callback_query.answer()


@router.callback_query(F.data == "menu:edited")
async def callback_edited_menu(callback_query: CallbackQuery) -> None:
    """Показывает последние изменённые сообщения."""
    if callback_query.from_user.id != OWNER_ID:
        return

    messages = await get_edited_messages(limit=5)

    if not messages:
        text = "✏ <b>Изменённые сообщения</b>\n\nПока не обнаружено."
    else:
        text = "✏ <b>Последние изменённые сообщения:</b>\n\n"
        for i, msg in enumerate(messages, 1):
            username = f"@{msg['username']}" if msg['username'] else "нет username"
            text += (
                f"<b>{i}.</b> {msg['user_name']} ({username})\n"
                f"   Тип: {msg['message_type']} | {msg['created_at']}\n"
                f"   Старое: <code>{msg['old_content'][:80]}</code>\n"
                f"   Новое: <code>{msg['new_content'][:80]}</code>\n\n"
            )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Очистить историю", callback_data="edit:clear")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")],
    ])

    await callback_query.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.callback_query(F.data == "edit:clear")
async def callback_clear_edited(callback_query: CallbackQuery) -> None:
    """Очищает историю изменённых сообщений."""
    if callback_query.from_user.id != OWNER_ID:
        return

    from database import clear_edited_messages
    await clear_edited_messages()

    await callback_query.message.edit_text(
        "🗑 История изменённых сообщений очищена!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")]
        ])
    )
    await callback_query.answer()
