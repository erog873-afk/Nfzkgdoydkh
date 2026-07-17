"""
Обработчик настроек бота.
"""

from aiogram import Router, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)

from config import OWNER_ID
from database import get_setting, set_setting, clear_all_logs
from logger import log_action

router = Router(name="settings")


# ==================== КЛАВИАТУРА ====================

def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Создаёт клавиатуру настроек."""
    buttons = [
        [
            InlineKeyboardButton(text="📝 Текст автоответчика", callback_data="set:ar_text"),
            InlineKeyboardButton(text="⏱ Задержка ответа", callback_data="set:delay"),
        ],
        [
            InlineKeyboardButton(text="🔔 Уведомления", callback_data="set:notifications"),
            InlineKeyboardButton(text="🕐 Часовой пояс", callback_data="set:timezone"),
        ],
        [
            InlineKeyboardButton(text="🗑 Очистить логи", callback_data="set:clear_logs"),
            InlineKeyboardButton(text="🗑 Очистить удалённые", callback_data="set:clear_deleted"),
        ],
        [
            InlineKeyboardButton(text="🗑 Очистить изменённые", callback_data="set:clear_edited"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== ОБРАБОТЧИКИ ====================

@router.callback_query(F.data == "menu:settings")
async def callback_settings_menu(callback_query: CallbackQuery) -> None:
    """Показывает меню настроек."""
    if callback_query.from_user.id != OWNER_ID:
        return

    notifications = await get_setting("notifications_enabled", True)
    tz = await get_setting("timezone", "Europe/Moscow")

    notif_text = "✅ Включены" if notifications else "❌ Выключены"

    text = (
        "⚙ <b>Настройки</b>\n\n"
        f"Часовой пояс: <b>{tz}</b>\n"
        f"Уведомления: <b>{notif_text}</b>\n\n"
        "Выберите параметр для изменения:"
    )

    await callback_query.message.edit_text(
        text,
        reply_markup=get_settings_keyboard(),
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.callback_query(F.data == "set:notifications")
async def callback_toggle_notifications(callback_query: CallbackQuery) -> None:
    """Переключает уведомления."""
    if callback_query.from_user.id != OWNER_ID:
        return

    current = await get_setting("notifications_enabled", True)
    await set_setting("notifications_enabled", not current)

    status = "включены" if not current else "выключены"
    log_action("SETTINGS", f"Уведомления {status}")

    await callback_query.message.edit_text(
        f"✅ Уведомления <b>{status}</b>!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:settings")]
        ]),
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.callback_query(F.data == "set:timezone")
async def callback_set_timezone(callback_query: CallbackQuery) -> None:
    """Запрашивает часовой пояс."""
    if callback_query.from_user.id != OWNER_ID:
        return

    buttons = [
        [InlineKeyboardButton(text="Europe/Moscow", callback_data="set:tz:Europe/Moscow")],
        [InlineKeyboardButton(text="Europe/Kiev", callback_data="set:tz:Europe/Kiev")],
        [InlineKeyboardButton(text="Asia/Almaty", callback_data="set:tz:Asia/Almaty")],
        [InlineKeyboardButton(text="Asia/Tashkent", callback_data="set:tz:Asia/Tashkent")],
        [InlineKeyboardButton(text="Asia/Bishkek", callback_data="set:tz:Asia/Bishkek")],
        [InlineKeyboardButton(text="Europe/London", callback_data="set:tz:Europe/London")],
        [InlineKeyboardButton(text="America/New_York", callback_data="set:tz:America/New_York")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:settings")],
    ]

    await callback_query.message.edit_text(
        "🕐 <b>Выберите часовой пояс:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("set:tz:"))
async def callback_apply_timezone(callback_query: CallbackQuery) -> None:
    """Применяет часовой пояс."""
    if callback_query.from_user.id != OWNER_ID:
        return

    tz = callback_query.data.split(":", 2)[2]
    await set_setting("timezone", tz)
    log_action("SETTINGS", f"Часовой пояс изменён на {tz}")

    await callback_query.message.edit_text(
        f"✅ Часовой пояс установлен: <b>{tz}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:settings")]
        ]),
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.callback_query(F.data == "set:ar_text")
async def callback_view_ar_text(callback_query: CallbackQuery) -> None:
    """Показывает текущий текст автоответчика."""
    if callback_query.from_user.id != OWNER_ID:
        return

    from config import DEFAULT_AUTORESPONDER_TEXT
    text = await get_setting("autoresponder_text", DEFAULT_AUTORESPONDER_TEXT)

    await callback_query.message.edit_text(
        f"📝 <b>Текст автоответчика:</b>\n\n<code>{text}</code>\n\n"
        "Для изменения текста перейдите в раздел «Автоответчик».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:settings")]
        ]),
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.callback_query(F.data == "set:delay")
async def callback_view_delay(callback_query: CallbackQuery) -> None:
    """Показывает текущую задержку."""
    if callback_query.from_user.id != OWNER_ID:
        return

    delay = await get_setting("autoresponder_delay", 0)
    random_delay = await get_setting("autoresponder_random_delay", False)

    delay_text = f"Случайная {delay}-{delay+5} сек" if random_delay else f"{delay} сек"

    await callback_query.message.edit_text(
        f"⏱ <b>Текущая задержка:</b> {delay_text}\n\n"
        "Для изменения задержки перейдите в раздел «Автоответчик».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:settings")]
        ]),
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.callback_query(F.data == "set:clear_logs")
async def callback_clear_logs(callback_query: CallbackQuery) -> None:
    """Очищает все логи."""
    if callback_query.from_user.id != OWNER_ID:
        return

    await clear_all_logs()
    log_action("SETTINGS", "Все логи очищены")

    await callback_query.message.edit_text(
        "🗑 Все логи и история сообщений очищены!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:settings")]
        ])
    )
    await callback_query.answer()


@router.callback_query(F.data == "set:clear_deleted")
async def callback_clear_deleted(callback_query: CallbackQuery) -> None:
    """Очищает историю удалённых сообщений."""
    if callback_query.from_user.id != OWNER_ID:
        return

    from database import clear_deleted_messages
    await clear_deleted_messages()
    log_action("SETTINGS", "История удалённых сообщений очищена")

    await callback_query.message.edit_text(
        "🗑 История удалённых сообщений очищена!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:settings")]
        ])
    )
    await callback_query.answer()


@router.callback_query(F.data == "set:clear_edited")
async def callback_clear_edited(callback_query: CallbackQuery) -> None:
    """Очищает историю изменённых сообщений."""
    if callback_query.from_user.id != OWNER_ID:
        return

    from database import clear_edited_messages
    await clear_edited_messages()
    log_action("SETTINGS", "История изменённых сообщений очищена")

    await callback_query.message.edit_text(
        "🗑 История изменённых сообщений очищена!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:settings")]
        ])
    )
    await callback_query.answer()
