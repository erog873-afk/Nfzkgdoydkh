"""
Обработчик автоответчика.
Управление настройками автоответчика и отправка ответов.
"""

import asyncio
import random
from datetime import datetime

from aiogram import Router, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import Command

from config import OWNER_ID, DEFAULT_AUTORESPONDER_TEXT
from database import (
    get_setting, set_setting,
    update_stats, is_user_ignored
)
from utils.helpers import fill_template
from logger import log_action, log_error

router = Router(name="autoresponder")


# ==================== КЛАВИАТУРА ====================

def get_autoresponder_keyboard() -> InlineKeyboardMarkup:
    """Создаёт клавиатуру меню автоответчика."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Включить", callback_data="ar:enable"),
            InlineKeyboardButton(text="❌ Выключить", callback_data="ar:disable"),
        ],
        [
            InlineKeyboardButton(text="📝 Изменить текст", callback_data="ar:edit_text"),
            InlineKeyboardButton(text="⏱ Настроить задержку", callback_data="ar:delay"),
        ],
        [
            InlineKeyboardButton(text="🚫 Игнорировать пользователя", callback_data="ar:add_ignore"),
            InlineKeyboardButton(text="✅ Убрать из игнора", callback_data="ar:remove_ignore"),
        ],
        [
            InlineKeyboardButton(text="📋 Список игнора", callback_data="ar:list_ignore"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== ОБРАБОТЧИКИ ====================

@router.callback_query(F.data == "menu:autoresponder")
async def callback_autoresponder_menu(callback_query: CallbackQuery) -> None:
    """Показывает меню автоответчика."""
    if callback_query.from_user.id != OWNER_ID:
        return

    enabled = await get_setting("autoresponder_enabled", False)
    text = await get_setting("autoresponder_text", DEFAULT_AUTORESPONDER_TEXT)
    delay = await get_setting("autoresponder_delay", 0)
    random_delay = await get_setting("autoresponder_random_delay", False)

    status = "✅ Включён" if enabled else "❌ Выключен"
    delay_text = f"Случайная {delay}-{delay+5} сек" if random_delay else f"{delay} сек"

    response = (
        "📨 <b>Автоответчик</b>\n\n"
        f"Статус: <b>{status}</b>\n"
        f"Задержка: <b>{delay_text}</b>\n\n"
        f"Текущий текст:\n<code>{text}</code>\n\n"
        "Выберите действие:"
    )

    await callback_query.message.edit_text(
        response,
        reply_markup=get_autoresponder_keyboard(),
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.callback_query(F.data == "ar:enable")
async def callback_enable_autoresponder(callback_query: CallbackQuery) -> None:
    """Включает автоответчик."""
    if callback_query.from_user.id != OWNER_ID:
        return

    await set_setting("autoresponder_enabled", True)
    log_action("AUTORESPONDER", "Автоответчик включён")

    await callback_query.message.edit_text(
        "✅ Автоответчик включён!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:autoresponder")]
        ])
    )
    await callback_query.answer()


@router.callback_query(F.data == "ar:disable")
async def callback_disable_autoresponder(callback_query: CallbackQuery) -> None:
    """Выключает автоответчик."""
    if callback_query.from_user.id != OWNER_ID:
        return

    await set_setting("autoresponder_enabled", False)
    log_action("AUTORESPONDER", "Автоответчик выключен")

    await callback_query.message.edit_text(
        "❌ Автоответчик выключен!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:autoresponder")]
        ])
    )
    await callback_query.answer()


@router.callback_query(F.data == "ar:edit_text")
async def callback_edit_text(callback_query: CallbackQuery) -> None:
    """Запрашивает новый текст автоответчика."""
    if callback_query.from_user.id != OWNER_ID:
        return

    await callback_query.message.edit_text(
        "📝 <b>Введите новый текст автоответчика</b>\n\n"
        "Поддерживаемые переменные:\n"
        "{name} — имя + фамилия\n"
        "{username} — @username\n"
        "{first_name} — имя\n"
        "{last_name} — фамилия\n"
        "{time} — текущее время\n"
        "{date} — текущая дата\n\n"
        "Отправьте текст сообщением:",
        parse_mode="HTML"
    )
    await callback_query.answer()

    # Устанавливаем флаг ожидания ввода текста
    await set_setting("waiting_ar_text", True)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_input(message: Message) -> None:
    """Обрабатывает текстовый ввод (текст автоответчика)."""
    if message.from_user.id != OWNER_ID:
        return

    waiting = await get_setting("waiting_ar_text", False)
    if not waiting:
        return

    new_text = message.text
    await set_setting("autoresponder_text", new_text)
    await set_setting("waiting_ar_text", False)

    log_action("AUTORESPONDER", f"Текст автоответчика изменён: {new_text[:50]}...")

    await message.answer(
        "✅ Текст автоответчика обновлён!\n\n"
        f"Новый текст:\n<code>{new_text}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:autoresponder")]
        ])
    )


@router.callback_query(F.data == "ar:delay")
async def callback_set_delay(callback_query: CallbackQuery) -> None:
    """Показывает варианты задержки."""
    if callback_query.from_user.id != OWNER_ID:
        return

    buttons = [
        [
            InlineKeyboardButton(text="0 сек (мгновенно)", callback_data="ar:delay:0"),
            InlineKeyboardButton(text="1-2 сек (случайная)", callback_data="ar:delay:1:random"),
        ],
        [
            InlineKeyboardButton(text="3-5 сек (случайная)", callback_data="ar:delay:3:random"),
            InlineKeyboardButton(text="5-10 сек (случайная)", callback_data="ar:delay:5:random"),
        ],
        [
            InlineKeyboardButton(text="10-30 сек (случайная)", callback_data="ar:delay:10:random"),
            InlineKeyboardButton(text="固定 30 сек", callback_data="ar:delay:30:fixed"),
        ],
        [
            InlineKeyboardButton(text="固定 60 сек", callback_data="ar:delay:60:fixed"),
            InlineKeyboardButton(text="固定 300 сек (5 мин)", callback_data="ar:delay:300:fixed"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="menu:autoresponder"),
        ],
    ]

    await callback_query.message.edit_text(
        "⏱ <b>Настройка задержки ответа</b>\n\n"
        "Выберите вариант задержки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("ar:delay:"))
async def callback_apply_delay(callback_query: CallbackQuery) -> None:
    """Применяет выбранную задержку."""
    if callback_query.from_user.id != OWNER_ID:
        return

    parts = callback_query.data.split(":")
    delay = int(parts[2])
    random_delay = len(parts) > 3 and parts[3] == "random"

    await set_setting("autoresponder_delay", delay)
    await set_setting("autoresponder_random_delay", random_delay)

    delay_text = f"случайная {delay}-{delay+5} сек" if random_delay else f"{delay} сек"
    log_action("AUTORESPONDER", f"Задержка установлена: {delay_text}")

    await callback_query.message.edit_text(
        f"✅ Задержка установлена: <b>{delay_text}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:autoresponder")]
        ]),
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.callback_query(F.data == "ar:add_ignore")
async def callback_add_ignore(callback_query: CallbackQuery) -> None:
    """Запрашивает ID пользователя для игнорирования."""
    if callback_query.from_user.id != OWNER_ID:
        return

    await callback_query.message.edit_text(
        "🚫 <b>Добавление в игнор-лист</b>\n\n"
        "Отправьте Telegram ID пользователя, которого нужно игнорировать.\n"
        "Формат: <code>123456789</code>",
        parse_mode="HTML"
    )
    await callback_query.answer()

    await set_setting("waiting_ignore_add", True)


@router.callback_query(F.data == "ar:remove_ignore")
async def callback_remove_ignore(callback_query: CallbackQuery) -> None:
    """Запрашивает ID пользователя для удаления из игнора."""
    if callback_query.from_user.id != OWNER_ID:
        return

    from database import get_ignored_users
    ignored = await get_ignored_users()

    if not ignored:
        await callback_query.message.edit_text(
            "📋 Список игнора пуст.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:autoresponder")]
            ])
        )
        await callback_query.answer()
        return

    users_list = "\n".join(f"  • <code>{uid}</code>" for uid in ignored)

    await callback_query.message.edit_text(
        "✅ <b>Удаление из игнора</b>\n\n"
        f"Текущий список игнора:\n{users_list}\n\n"
        "Отправьте ID пользователя для удаления:",
        parse_mode="HTML"
    )
    await callback_query.answer()

    await set_setting("waiting_ignore_remove", True)


@router.callback_query(F.data == "ar:list_ignore")
async def callback_list_ignore(callback_query: CallbackQuery) -> None:
    """Показывает список игнорируемых пользователей."""
    if callback_query.from_user.id != OWNER_ID:
        return

    from database import get_ignored_users
    ignored = await get_ignored_users()

    if not ignored:
        users_text = "Пусто"
    else:
        users_text = "\n".join(f"  • <code>{uid}</code>" for uid in ignored)

    await callback_query.message.edit_text(
        f"📋 <b>Игнор-лист</b>\n\n{users_text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:autoresponder")]
        ]),
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.message(F.text & ~F.text.startswith("/"))
async def handle_ignore_input(message: Message) -> None:
    """Обрабатывает ввод ID для игнора."""
    if message.from_user.id != OWNER_ID:
        return

    waiting_add = await get_setting("waiting_ignore_add", False)
    waiting_remove = await get_setting("waiting_ignore_remove", False)

    if not waiting_add and not waiting_remove:
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат. Введите числовой ID.")
        return

    if waiting_add:
        from database import add_ignored_user
        await add_ignored_user(user_id)
        await set_setting("waiting_ignore_add", False)
        log_action("AUTORESPONDER", f"Пользователь {user_id} добавлен в игнор")
        await message.answer(
            f"✅ Пользователь <code>{user_id}</code> добавлен в игнор-лист.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:autoresponder")]
            ])
        )

    elif waiting_remove:
        from database import remove_ignored_user
        await remove_ignored_user(user_id)
        await set_setting("waiting_ignore_remove", False)
        log_action("AUTORESPONDER", f"Пользователь {user_id} удалён из игнора")
        await message.answer(
            f"✅ Пользователь <code>{user_id}</code> удалён из игнор-листа.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:autoresponder")]
            ])
        )


# ==================== АВТООТВЕТЧИК ====================

async def handle_auto_reply(message: Message) -> None:
    """
    Обрабатывает входящее сообщение и отправляет автоответ при необходимости.
    Вызывается из обработчика мониторинга.

    ВАЖНО: Автоответчик работает ТОЛЬКО через Telegram Business Bot.
    Бот должен быть подключён как Business Bot к аккаунту Владельца.
    Ответ отправляется через send_business_message в чат Владельца с пользователем.
    """
    try:
        # Проверяем, включён ли автоответчик
        enabled = await get_setting("autoresponder_enabled", False)
        if not enabled:
            return

        # Проверяем, что сообщение от другого пользователя (не от владельца)
        user = message.from_user
        if not user or user.id == OWNER_ID:
            return

        # Проверяем, что есть business_connection_id (без него автоответ не работает)
        business_connection_id = getattr(message, "business_connection_id", None)
        if not business_connection_id:
            # Нет Business подключения — автоответчик не может работать
            log_action(
                "AUTOREPLY",
                f"Пропущен ответ: нет business_connection_id "
                f"(чат {message.chat.id}, пользователь {user.id})"
            )
            return

        # Проверяем, что сообщение из личного чата (не группы)
        chat = message.chat
        if chat.type != "private":
            ignore_groups = await get_setting("autoresponder_ignore_groups", True)
            if ignore_groups:
                return

        # Проверяем игнор-лист
        if await is_user_ignored(user.id):
            return

        # Получаем настройки
        ar_text = await get_setting("autoresponder_text", DEFAULT_AUTORESPONDER_TEXT)
        delay = await get_setting("autoresponder_delay", 0)
        random_delay = await get_setting("autoresponder_random_delay", False)

        # Вычисляем задержку
        if random_delay:
            actual_delay = random.randint(delay, delay + 5)
        else:
            actual_delay = delay

        # Ждём задержку
        if actual_delay > 0:
            await asyncio.sleep(actual_delay)

        # Заполняем шаблон
        response_text = fill_template(
            ar_text,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            username=user.username or "",
            user_id=user.id
        )

        # Отправляем ответ через Telegram Business API
        # Используем send_business_message для ответа в чат Владельца с пользователем
        bot = message.bot
        await bot.send_business_message(
            business_connection_id=business_connection_id,
            text=response_text,
            parse_mode="HTML"
        )

        await update_stats("auto_replies_sent")

        log_action(
            "AUTOREPLY",
            f"Ответ отправлен (Business) пользователю {user.id} "
            f"(@{user.username or 'нет'}) с задержкой {actual_delay} сек, "
            f"business_connection={business_connection_id}"
        )

    except Exception as e:
        log_error(e, "Ошибка в handle_auto_reply")
