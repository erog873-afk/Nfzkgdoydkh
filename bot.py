"""
Главный файл Telegram-бота.
Инициализирует бота, регистрирует обработчики и запускает polling.
"""

import asyncio
import sys
import random
from pathlib import Path
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    Message, CallbackQuery, BotCommand, BotCommandScopeDefault,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BusinessConnection, BusinessMessagesDeleted
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode

from config import BOT_TOKEN, OWNER_ID, validate_config, DEFAULT_AUTORESPONDER_TEXT
from database import (
    init_database, get_setting, set_setting, update_stats,
    save_deleted_message, save_edited_message, get_deleted_messages,
    get_edited_messages, clear_all_logs, is_user_ignored
)
from logger import logger, log_action, log_error
from utils.helpers import (
    get_message_type, get_message_content, fill_template, format_datetime
)

# Глобальная ссылка на бота — используется во всех хендлерах
_bot: Optional[Bot] = None


def get_bot() -> Bot:
    """Возвращает экземпляр бота."""
    return _bot


# ==================== ХРАНИЛИЩЕ ====================

message_store: dict[int, dict] = {}
business_chat_map: dict[int, str] = {}

# Время последнего автоответа каждому пользователю {user_id: timestamp}
auto_reply_cooldown: dict[int, float] = {}


def store_message_data(message: Message) -> None:
    """Сохраняет данные сообщения + file_id для вложений."""
    user = message.from_user
    biz_conn = getattr(message, "business_connection_id", None)

    data = {
        "chat_id": message.chat.id,
        "user_id": user.id if user else 0,
        "user_name": f"{user.first_name or ''} {user.last_name or ''}".strip() if user else "",
        "username": user.username or "" if user else "",
        "message_type": get_message_type(message),
        "content": get_message_content(message),
        "date": datetime.now().isoformat(),
        "business_connection_id": biz_conn,
        "file_id": None,
        "file_type": None,
        "file_name": None,
    }

    # Извлекаем file_id для вложений (фото, видео, голос, стикер и т.д.)
    if message.photo:
        data["file_id"] = message.photo[-1].file_id
        data["file_type"] = "photo"
    elif message.video:
        data["file_id"] = message.video.file_id
        data["file_type"] = "video"
        data["file_name"] = message.video.file_name
    elif message.video_note:
        data["file_id"] = message.video_note.file_id
        data["file_type"] = "video_note"
    elif message.voice:
        data["file_id"] = message.voice.file_id
        data["file_type"] = "voice"
    elif message.animation:
        data["file_id"] = message.animation.file_id
        data["file_type"] = "animation"
    elif message.document:
        data["file_id"] = message.document.file_id
        data["file_type"] = "document"
        data["file_name"] = message.document.file_name
    elif message.sticker:
        data["file_id"] = message.sticker.file_id
        data["file_type"] = "sticker"
        data["file_name"] = message.sticker.emoji
    elif message.audio:
        data["file_id"] = message.audio.file_id
        data["file_type"] = "audio"
        data["file_name"] = message.audio.file_name
    elif message.contact:
        data["file_type"] = "contact"
    elif message.location:
        data["file_type"] = "location"

    message_store[message.message_id] = data

    if biz_conn:
        business_chat_map[message.chat.id] = biz_conn

    if len(message_store) > 50000:
        oldest = sorted(message_store.keys())[:25000]
        for key in oldest:
            del message_store[key]


# ==================== РОУТЕРЫ ====================

owner_router = Router(name="owner")
business_router = Router(name="business")


# ==================== УТИЛИТЫ ====================

def get_main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📨 Автоответчик", callback_data="menu:autoresponder"),
            InlineKeyboardButton(text="🗑 Удалённые", callback_data="menu:deleted"),
        ],
        [
            InlineKeyboardButton(text="✏ Изменённые", callback_data="menu:edited"),
            InlineKeyboardButton(text="⚙ Настройки", callback_data="menu:settings"),
        ],
        [
            InlineKeyboardButton(text="📊 Статус", callback_data="menu:status"),
            InlineKeyboardButton(text="ℹ Информация", callback_data="menu:info"),
        ],
    ])


def get_back_kb(target: str = "menu:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=target)]
    ])


async def _send_owner(text: str) -> None:
    """Отправляет сообщение владельцу через глобального бота."""
    bot = get_bot()
    if bot:
        try:
            await bot.send_message(chat_id=OWNER_ID, text=text, parse_mode=ParseMode.HTML)
            log_action("NOTIFY", f"Отправлено владельцу: {text[:80]}")
        except Exception as e:
            log_error(e, f"Ошибка отправки владельцу: {text[:80]}")
    else:
        logger.error("Bot не инициализирован, не могу отправить сообщение владельцу")


# ==================== /start ====================

@owner_router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user and message.from_user.id != OWNER_ID:
        return
    log_action("START", f"Открыто меню")
    await message.answer(
        "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        reply_markup=get_main_menu_kb(),
        parse_mode=ParseMode.HTML
    )


@owner_router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    if not message.from_user or message.from_user.id != OWNER_ID:
        return
    from database import get_stats
    stats = await get_stats()
    biz = await get_setting("business_connected", False)
    ar = await get_setting("autoresponder_enabled", False)
    await message.answer(
        "📊 <b>Статус</b>\n\n"
        f"🏢 Business: <b>{'✅' if biz else '❌'}</b>\n"
        f"📨 Автоответчик: <b>{'✅' if ar else '❌'}</b>\n\n"
        f"📈 Сообщений: <b>{stats.get('messages_processed', 0)}</b>\n"
        f"✏ Изменений: <b>{stats.get('messages_edited_detected', 0)}</b>\n"
        f"🗑 Удалений: <b>{stats.get('messages_deleted_detected', 0)}</b>\n"
        f"💬 Автоответов: <b>{stats.get('auto_replies_sent', 0)}</b>",
        parse_mode=ParseMode.HTML
    )


@owner_router.message(Command("ar"))
async def cmd_ar(message: Message) -> None:
    if not message.from_user or message.from_user.id != OWNER_ID:
        return
    enabled = await get_setting("autoresponder_enabled", False)
    text_val = await get_setting("autoresponder_text", DEFAULT_AUTORESPONDER_TEXT)
    await message.answer(
        f"📨 <b>Автоответчик</b>\n\n"
        f"Статус: <b>{'✅' if enabled else '❌'}</b>\n"
        f"Текст:\n<code>{text_val}</code>",
        reply_markup=get_back_kb("menu:autoresponder"),
        parse_mode=ParseMode.HTML
    )


# ==================== BUSINESS СООБЩЕНИЯ ====================

@business_router.business_connection()
async def on_biz_connect(event: BusinessConnection) -> None:
    bot = get_bot()
    if event.is_enabled:
        await set_setting("business_connected", True)
        log_action("BIZ", f"Подключён: {event.business_connection_id}")
        if bot:
            await bot.send_message(
                chat_id=OWNER_ID,
                text=(
                    f"🏢 <b>Telegram Business подключён!</b>\n\n"
                    f"ID: <code>{event.business_connection_id}</code>"
                ),
                parse_mode=ParseMode.HTML
            )
    else:
        await set_setting("business_connected", False)
        if bot:
            await bot.send_message(chat_id=OWNER_ID, text="⚠️ Telegram Business отключён!")


@business_router.business_message()
async def on_business_message(message: Message) -> None:
    """Входящее business-сообщение."""
    store_message_data(message)
    await update_stats("messages_processed")
    await _handle_auto_reply(message)

    user = message.from_user
    if user:
        log_action(
            "BIZ_MSG",
            f"От {user.id} (@{user.username or '?'}): "
            f"{message.text[:50] if message.text else '[медиа]'}"
        )


@business_router.edited_business_message()
async def on_edited_biz(message: Message) -> None:
    """Изменённое business-сообщение."""
    user = message.from_user
    if not user:
        return

    old_data = message_store.get(message.message_id)
    new_content = get_message_content(message)

    store_message_data(message)

    if not old_data or old_data.get("content") == new_content:
        return

    await save_edited_message(
        chat_id=message.chat.id,
        user_id=user.id,
        user_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
        username=user.username or "",
        message_type=get_message_type(message),
        old_content=old_data.get("content", ""),
        new_content=new_content
    )
    await update_stats("messages_edited_detected")

    notifications = await get_setting("notifications_enabled", True)
    if notifications:
        username = f"@{user.username}" if user.username else "нет"
        text = (
            "✏ <b>Изменённое сообщение</b>\n\n"
            f"👤 {user.first_name or ''} {user.last_name or ''} ({username})\n"
            f"🆔 <code>{user.id}</code>\n"
            f"🕐 {format_datetime()}\n\n"
            f"<b>СТАРОЕ:</b>\n<code>{old_data.get('content', '')[:1500]}</code>\n\n"
            f"↓\n\n"
            f"<b>НОВОЕ:</b>\n<code>{new_content[:1500]}</code>"
        )
        await _send_owner(text)

    log_action("EDIT", f"От {user.id}")


@business_router.deleted_business_messages()
async def on_deleted(event: BusinessMessagesDeleted) -> None:
    """Удалённые business-сообщения — с вложениями."""
    bot = get_bot()
    biz_id = event.business_connection_id
    chat = event.chat
    message_ids = event.message_ids

    log_action("DELETE", f"IDs: {message_ids}, biz={biz_id}")

    for mid in message_ids:
        stored = message_store.pop(mid, None)

        if stored:
            username = f"@{stored['username']}" if stored['username'] else "нет"
            caption = (
                f"🗑 <b>Удалённое сообщение</b>\n\n"
                f"👤 {stored['user_name']} ({username})\n"
                f"🆔 <code>{stored['user_id']}</code>\n"
                f"💬 {stored['message_type']}\n"
                f"🕐 {stored['date']}\n\n"
                f"<b>Содержимое:</b>\n<code>{stored['content'][:2000]}</code>"
            )

            # Сохраняем в базу
            await save_deleted_message(
                chat_id=stored['chat_id'],
                user_id=stored['user_id'],
                user_name=stored['user_name'],
                username=stored['username'],
                message_type=stored['message_type'],
                content=stored['content']
            )

            # Отправляем с вложением если есть file_id
            if bot and stored.get("file_id") and stored.get("file_type"):
                try:
                    file_id = stored["file_id"]
                    file_type = stored["file_type"]

                    if file_type == "photo":
                        await bot.send_photo(chat_id=OWNER_ID, photo=file_id, caption=caption, parse_mode=ParseMode.HTML)
                    elif file_type == "video":
                        await bot.send_video(chat_id=OWNER_ID, video=file_id, caption=caption, parse_mode=ParseMode.HTML)
                    elif file_type == "voice":
                        await bot.send_voice(chat_id=OWNER_ID, voice=file_id, caption=caption, parse_mode=ParseMode.HTML)
                    elif file_type == "video_note":
                        await bot.send_video_note(chat_id=OWNER_ID, video_note=file_id)
                        # Video note не поддерживает caption, отправляем текст отдельно
                        await _send_owner(caption)
                    elif file_type == "animation":
                        await bot.send_animation(chat_id=OWNER_ID, animation=file_id, caption=caption, parse_mode=ParseMode.HTML)
                    elif file_type == "document":
                        await bot.send_document(chat_id=OWNER_ID, document=file_id, caption=caption, parse_mode=ParseMode.HTML)
                    elif file_type == "sticker":
                        await bot.send_sticker(chat_id=OWNER_ID, sticker=file_id)
                        # Стикер не поддерживает caption
                        await _send_owner(caption)
                    elif file_type == "audio":
                        await bot.send_audio(chat_id=OWNER_ID, audio=file_id, caption=caption, parse_mode=ParseMode.HTML)
                    else:
                        await _send_owner(caption)

                    log_action("DELETE", f"Отправлено с вложением ({file_type})")
                    continue  # Уже отправили, пропускаем _send_owner

                except Exception as e:
                    log_error(e, f"Ошибка отправки вложения {file_type}")
                    # Фоллбэк — отправляем текст
                    await _send_owner(caption)
            else:
                # Нет вложения — просто текст
                await _send_owner(caption)
        else:
            # Не нашли в хранилище
            text = (
                "🗑 <b>Удалённое сообщение</b>\n\n"
                f"📌 Message ID: <code>{mid}</code>\n"
                f"💬 Чат: <code>{chat.id}</code>\n\n"
                "⚠️ Содержимое неизвестно — сообщение не было "
                "получено ботом до удаления"
            )
            await _send_owner(text)

        await update_stats("messages_deleted_detected")


# ==================== ОБЫЧНЫЕ СООБЩЕНИЯ ====================

@owner_router.message()
async def on_regular_message(message: Message) -> None:
    """Любое обычное сообщение от владельца."""
    if not message.from_user or message.from_user.id != OWNER_ID:
        return

    store_message_data(message)
    await update_stats("messages_processed")

    # Текстовый ввод
    waiting = await get_setting("waiting_ar_text", False)
    if waiting and message.text:
        await set_setting("autoresponder_text", message.text)
        await set_setting("waiting_ar_text", False)
        log_action("AR", f"Текст изменён")
        await message.answer(
            f"✅ Текст обновлён!\n\n<code>{message.text}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_kb("menu:autoresponder")
        )


@owner_router.edited_message()
async def on_edited(message: Message) -> None:
    """Изменённое обычное сообщение."""
    user = message.from_user
    if not user or user.id != OWNER_ID:
        return

    old_data = message_store.get(message.message_id)
    new_content = get_message_content(message)
    store_message_data(message)

    if not old_data or old_data.get("content") == new_content:
        return

    await save_edited_message(
        chat_id=message.chat.id,
        user_id=user.id,
        user_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
        username=user.username or "",
        message_type=get_message_type(message),
        old_content=old_data.get("content", ""),
        new_content=new_content
    )
    await update_stats("messages_edited_detected")

    notifications = await get_setting("notifications_enabled", True)
    if notifications:
        username = f"@{user.username}" if user.username else "нет"
        await _send_owner(
            "✏ <b>Изменённое сообщение</b>\n\n"
            f"👤 {user.first_name or ''} {user.last_name or ''} ({username})\n"
            f"🕐 {format_datetime()}\n\n"
            f"<b>СТАРОЕ:</b>\n<code>{old_data.get('content', '')[:1500]}</code>\n\n"
            f"↓\n\n"
            f"<b>НОВОЕ:</b>\n<code>{new_content[:1500]}</code>"
        )


# ==================== CALLBACK QUERY ====================

@owner_router.callback_query(F.data == "menu:main")
async def cb_main(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    await c.message.edit_text("🏠 <b>Главное меню</b>\n\nВыберите раздел:", reply_markup=get_main_menu_kb(), parse_mode=ParseMode.HTML)
    await c.answer()


@owner_router.callback_query(F.data == "menu:autoresponder")
async def cb_ar_menu(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    enabled = await get_setting("autoresponder_enabled", False)
    text_val = await get_setting("autoresponder_text", DEFAULT_AUTORESPONDER_TEXT)
    delay = await get_setting("autoresponder_delay", 0)
    rnd = await get_setting("autoresponder_random_delay", False)
    d_text = _format_delay(delay, rnd)

    await c.message.edit_text(
        f"📨 <b>Автоответчик</b>\n\n"
        f"Статус: <b>{'✅ Включён' if enabled else '❌ Выключен'}</b>\n"
        f"Задержка: <b>{d_text}</b>\n\n"
        f"Текст:\n<code>{text_val}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Включить", callback_data="ar:on"),
                InlineKeyboardButton(text="❌ Выключить", callback_data="ar:off"),
            ],
            [InlineKeyboardButton(text="📝 Изменить текст", callback_data="ar:text")],
            [InlineKeyboardButton(text="⏱ Задержка", callback_data="ar:delay_menu")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")],
        ]),
        parse_mode=ParseMode.HTML
    )
    await c.answer()


def _format_delay(delay: int, is_random: bool) -> str:
    if is_random:
        if delay == 1:
            return "Случайная 1-6 сек"
        elif delay == 3:
            return "Случайная 3-8 сек"
        elif delay == 5:
            return "Случайная 5-10 сек"
        elif delay == 10:
            return "Случайная 10-15 сек"
        elif delay == 30:
            return "Случайная 30-40 сек"
        elif delay == 60:
            return "Случайная 1-2 мин"
        elif delay == 120:
            return "Случайная 2-3 мин"
        elif delay == 300:
            return "Случайная 5-6 мин"
        elif delay == 600:
            return "Случайная 10-15 мин"
        elif delay == 900:
            return "Случайная 15-20 мин"
        elif delay == 1800:
            return "Случайная 30-35 мин"
        else:
            return f"Случайная {delay}-{delay+5} сек"
    else:
        if delay == 0:
            return "Мгновенно"
        elif delay < 60:
            return f"{delay} сек"
        elif delay < 3600:
            return f"{delay // 60} мин"
        else:
            return f"{delay // 3600} ч"


@owner_router.callback_query(F.data == "ar:on")
async def cb_ar_on(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    await set_setting("autoresponder_enabled", True)
    log_action("AR", "Включён")
    await c.message.edit_text("✅ Автоответчик включён!", reply_markup=get_back_kb("menu:autoresponder"))
    await c.answer()


@owner_router.callback_query(F.data == "ar:off")
async def cb_ar_off(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    await set_setting("autoresponder_enabled", False)
    log_action("AR", "Выключен")
    await c.message.edit_text("❌ Автоответчик выключен!", reply_markup=get_back_kb("menu:autoresponder"))
    await c.answer()


@owner_router.callback_query(F.data == "ar:text")
async def cb_ar_text(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    text_val = await get_setting("autoresponder_text", DEFAULT_AUTORESPONDER_TEXT)
    await set_setting("waiting_ar_text", True)
    await c.message.edit_text(
        f"📝 <b>Введите новый текст:</b>\n\n"
        f"Текущий:\n<code>{text_val}</code>\n\n"
        "Переменные: {{name}} {{username}} {{first_name}} {{last_name}} {{time}} {{date}}",
        parse_mode=ParseMode.HTML
    )
    await c.answer()


@owner_router.callback_query(F.data == "ar:delay_menu")
async def cb_ar_delay(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    delay = await get_setting("autoresponder_delay", 0)
    rnd = await get_setting("autoresponder_random_delay", False)
    d_text = _format_delay(delay, rnd)

    await c.message.edit_text(
        f"⏱ <b>Задержка ответа:</b> {d_text}\n\nВыберите новую задержку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="0 (мгновенно)", callback_data="ar:d:0:f"),
                InlineKeyboardButton(text="1-6 сек", callback_data="ar:d:1:r"),
            ],
            [
                InlineKeyboardButton(text="3-8 сек", callback_data="ar:d:3:r"),
                InlineKeyboardButton(text="5-10 сек", callback_data="ar:d:5:r"),
            ],
            [
                InlineKeyboardButton(text="10-15 сек", callback_data="ar:d:10:r"),
                InlineKeyboardButton(text="30-40 сек", callback_data="ar:d:30:r"),
            ],
            [
                InlineKeyboardButton(text="1-2 мин", callback_data="ar:d:60:r"),
                InlineKeyboardButton(text="2-3 мин", callback_data="ar:d:120:r"),
            ],
            [
                InlineKeyboardButton(text="5-6 мин", callback_data="ar:d:300:r"),
                InlineKeyboardButton(text="10-15 мин", callback_data="ar:d:600:r"),
            ],
            [
                InlineKeyboardButton(text="15-20 мин", callback_data="ar:d:900:r"),
                InlineKeyboardButton(text="30-35 мин", callback_data="ar:d:1800:r"),
            ],
            [
                InlineKeyboardButton(text="Фикс. 30 сек", callback_data="ar:d:30:f"),
                InlineKeyboardButton(text="Фикс. 1 мин", callback_data="ar:d:60:f"),
            ],
            [
                InlineKeyboardButton(text="Фикс. 5 мин", callback_data="ar:d:300:f"),
                InlineKeyboardButton(text="Фикс. 10 мин", callback_data="ar:d:600:f"),
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:autoresponder")],
        ]),
        parse_mode=ParseMode.HTML
    )
    await c.answer()


@owner_router.callback_query(F.data.startswith("ar:d:"))
async def cb_ar_delay_set(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    parts = c.data.split(":")
    delay = int(parts[2])
    is_random = parts[3] == "r"
    await set_setting("autoresponder_delay", delay)
    await set_setting("autoresponder_random_delay", is_random)
    d_text = _format_delay(delay, is_random)
    log_action("AR", f"Задержка: {d_text}")
    await c.message.edit_text(f"✅ Задержка: <b>{d_text}</b>", reply_markup=get_back_kb("menu:autoresponder"), parse_mode=ParseMode.HTML)
    await c.answer()


@owner_router.callback_query(F.data == "menu:deleted")
async def cb_deleted(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    messages = await get_deleted_messages(limit=5)
    if not messages:
        text = "🗑 <b>Удалённые сообщения</b>\n\nПока не обнаружено."
    else:
        text = "🗑 <b>Последние удалённые:</b>\n\n"
        for i, msg in enumerate(messages, 1):
            text += f"<b>{i}.</b> {msg['user_name']} | {msg['created_at']}\n   <code>{msg['content'][:100]}</code>\n\n"
    await c.message.edit_text(text, reply_markup=get_back_kb("menu:main"), parse_mode=ParseMode.HTML)
    await c.answer()


@owner_router.callback_query(F.data == "menu:edited")
async def cb_edited(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    messages = await get_edited_messages(limit=5)
    if not messages:
        text = "✏ <b>Изменённые сообщения</b>\n\nПока не обнаружено."
    else:
        text = "✏ <b>Последние изменения:</b>\n\n"
        for i, msg in enumerate(messages, 1):
            text += f"<b>{i}.</b> {msg['user_name']} | {msg['created_at']}\n   Было: <code>{msg['old_content'][:80]}</code>\n   Стало: <code>{msg['new_content'][:80]}</code>\n\n"
    await c.message.edit_text(text, reply_markup=get_back_kb("menu:main"), parse_mode=ParseMode.HTML)
    await c.answer()


@owner_router.callback_query(F.data == "menu:settings")
async def cb_settings(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    tz = await get_setting("timezone", "Europe/Moscow")
    notifs = await get_setting("notifications_enabled", True)
    await c.message.edit_text(
        "⚙ <b>Настройки</b>\n\n"
        f"🕐 Часовой пояс: <b>{tz}</b>\n"
        f"🔔 Уведомления: <b>{'✅ Включены' if notifs else '❌ Выключены'}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Уведомления", callback_data="set:notifs")],
            [InlineKeyboardButton(text="🕐 Часовой пояс", callback_data="set:tz")],
            [InlineKeyboardButton(text="🗑 Очистить всё", callback_data="set:clear_all")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")],
        ]),
        parse_mode=ParseMode.HTML
    )
    await c.answer()


@owner_router.callback_query(F.data == "set:notifs")
async def cb_set_notifs(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    current = await get_setting("notifications_enabled", True)
    await set_setting("notifications_enabled", not current)
    status = "включены" if not current else "выключены"
    log_action("SETTINGS", f"Уведомления {status}")
    await c.message.edit_text(f"✅ Уведомления <b>{status}</b>!", reply_markup=get_back_kb("menu:settings"), parse_mode=ParseMode.HTML)
    await c.answer()


@owner_router.callback_query(F.data == "set:tz")
async def cb_set_tz(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    buttons = [
        [InlineKeyboardButton(text="Europe/Moscow", callback_data="tz:Europe/Moscow")],
        [InlineKeyboardButton(text="Europe/Kiev", callback_data="tz:Europe/Kiev")],
        [InlineKeyboardButton(text="Asia/Almaty", callback_data="tz:Asia/Almaty")],
        [InlineKeyboardButton(text="Asia/Tashkent", callback_data="tz:Asia/Tashkent")],
        [InlineKeyboardButton(text="Asia/Bishkek", callback_data="tz:Asia/Bishkek")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:settings")],
    ]
    await c.message.edit_text("🕐 <b>Выберите часовой пояс:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)
    await c.answer()


@owner_router.callback_query(F.data.startswith("tz:"))
async def cb_tz_set(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    tz = c.data.split(":", 1)[1]
    await set_setting("timezone", tz)
    log_action("SETTINGS", f"Часовой пояс: {tz}")
    await c.message.edit_text(f"✅ Часовой пояс: <b>{tz}</b>", reply_markup=get_back_kb("menu:settings"), parse_mode=ParseMode.HTML)
    await c.answer()


@owner_router.callback_query(F.data == "set:clear_all")
async def cb_clear_all(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    await clear_all_logs()
    log_action("SETTINGS", "Логи очищены")
    await c.message.edit_text("🗑 Логи очищены!", reply_markup=get_back_kb("menu:settings"))
    await c.answer()


@owner_router.callback_query(F.data == "menu:status")
async def cb_status(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    from database import get_stats
    stats = await get_stats()
    biz = await get_setting("business_connected", False)
    ar = await get_setting("autoresponder_enabled", False)
    await c.message.edit_text(
        "📊 <b>Статус</b>\n\n"
        f"🏢 Business: <b>{'✅' if biz else '❌'}</b>\n"
        f"📨 Автоответчик: <b>{'✅' if ar else '❌'}</b>\n\n"
        f"📈 Сообщений: <b>{stats.get('messages_processed', 0)}</b>\n"
        f"✏ Изменений: <b>{stats.get('messages_edited_detected', 0)}</b>\n"
        f"🗑 Удалений: <b>{stats.get('messages_deleted_detected', 0)}</b>\n"
        f"💬 Автоответов: <b>{stats.get('auto_replies_sent', 0)}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="menu:status")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")],
        ]),
        parse_mode=ParseMode.HTML
    )
    await c.answer()


@owner_router.callback_query(F.data == "menu:info")
async def cb_info(c: CallbackQuery) -> None:
    if c.from_user.id != OWNER_ID:
        await c.answer()
        return
    await c.message.edit_text(
        "ℹ <b>Информация</b>\n\n"
        "Telegram Business Monitor Bot v1.0\n\n"
        "<b>Возможности:</b>\n"
        "• Автоответчик с переменными\n"
        "• Мониторинг удалённых сообщений\n"
        "• Мониторинг изменённых сообщений\n"
        "• Панель управления\n\n"
        "<b>Ограничения Telegram API:</b>\n"
        "Удалённые сообщения показывают содержимое\n"
        "только если бот получил их до удаления.",
        reply_markup=get_back_kb("menu:main"),
        parse_mode=ParseMode.HTML
    )
    await c.answer()


# ==================== АВТООТВЕТЧИК ====================

async def _handle_auto_reply(message: Message) -> None:
    """
    Автоответчик с интервалом НА КАЖДОГО ПОЛЬЗОВАТЕЛЯ.
    После первого ответа пользователю — следующий ответ только через задержку.
    """
    try:
        import time

        enabled = await get_setting("autoresponder_enabled", False)
        if not enabled:
            return

        user = message.from_user
        if not user or user.id == OWNER_ID:
            return

        biz_conn = getattr(message, "business_connection_id", None)
        if not biz_conn:
            return

        if await is_user_ignored(user.id):
            return

        # Проверяем cooldown для ЭТОГО пользователя
        delay = await get_setting("autoresponder_delay", 0)
        random_delay = await get_setting("autoresponder_random_delay", False)

        now = time.time()
        last_reply = auto_reply_cooldown.get(user.id, 0)

        # Вычисляем задержку
        if random_delay:
            actual_delay = random.randint(delay, delay + 5)
        else:
            actual_delay = delay

        # Если ещё не прошёл интервал — пропускаем ответ
        if now - last_reply < actual_delay:
            log_action("AR_SKIP", f"Cooldown для {user.id}, осталось {int(actual_delay - (now - last_reply))} сек")
            return

        # Ждём задержку
        if actual_delay > 0:
            await asyncio.sleep(actual_delay)

        # Проверяем ещё раз после задержки (могло измениться)
        now2 = time.time()
        last_reply2 = auto_reply_cooldown.get(user.id, 0)
        if now2 - last_reply2 < actual_delay:
            return

        # Отвечаем и ставим cooldown
        auto_reply_cooldown[user.id] = time.time()

        response_text = fill_template(
            await get_setting("autoresponder_text", DEFAULT_AUTORESPONDER_TEXT),
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            username=user.username or "",
            user_id=user.id
        )

        bot = get_bot()
        if bot:
            await bot.send_message(
                chat_id=message.chat.id,
                text=response_text,
                business_connection_id=biz_conn
            )
            await update_stats("auto_replies_sent")
            log_action("AUTOREPLY", f"Пользователю {user.id} (@{user.username or '?'})")

    except Exception as e:
        log_error(e, "Ошибка автоответчика")


# ==================== MAIN ====================

async def main() -> None:
    global _bot

    Path("data").mkdir(exist_ok=True)

    try:
        validate_config()
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    _bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    dp.include_router(owner_router)
    dp.include_router(business_router)

    @dp.error()
    async def on_error(event, exception: Exception) -> None:
        log_error(exception, "Необработанная ошибка")

    logger.info("Запуск бота...")

    try:
        me = await _bot.get_me()
        await set_setting("bot_username", me.username)
        logger.info(f"Бот: @{me.username} (ID: {me.id})")

        await _bot.send_message(
            chat_id=OWNER_ID,
            text="✅ <b>Бот запущен!</b>\n\nОтправьте /start",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        log_error(e, "Ошибка при запуске")

    logger.info("Начинаем polling...")
    try:
        await dp.start_polling(_bot)
    except Exception as e:
        log_error(e, "Критическая ошибка в polling")
    finally:
        await _bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
