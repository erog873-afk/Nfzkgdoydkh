"""
Обработчик информации о боте.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import OWNER_ID

router = Router(name="info")


@router.callback_query(F.data == "menu:info")
async def callback_info(callback_query: CallbackQuery) -> None:
    """Показывает информацию о боте."""
    if callback_query.from_user.id != OWNER_ID:
        return

    text = (
        "ℹ <b>Информация о боте</b>\n\n"
        "Бот для мониторинга переписок через Telegram Business.\n\n"
        "<b>Возможности:</b>\n"
        "• Отслеживание удалённых сообщений\n"
        "• Отслеживание изменённых сообщений\n"
        "• Автоответчик с настройками\n"
        "• Панель управления\n\n"
        "<b>Ограничения Telegram Business API:</b>\n"
        "• Бот должен быть подключён как Business Bot\n"
        "• Доступны только сообщения, которые бот получает как Business Bot\n"
        "• Уведомления об удалении/изменении доступны через Business Events API\n"
        "• Не все типы контента доступны для пересылки\n\n"
        "<b>Версия:</b> 1.0.0"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")],
    ])

    await callback_query.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback_query.answer()
