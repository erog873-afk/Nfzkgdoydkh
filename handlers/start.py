"""
Обработчик команды /start и главное меню.
"""

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command

from config import OWNER_ID
from database import get_stats, get_setting
from logger import log_action

router = Router(name="start")


# ==================== КЛАВИАТУРА ====================

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создаёт клавиатуру главного меню."""
    buttons = [
        [
            InlineKeyboardButton(text="📨 Автоответчик", callback_data="menu:autoresponder"),
            InlineKeyboardButton(text="🗑 Удалённые сообщения", callback_data="menu:deleted"),
        ],
        [
            InlineKeyboardButton(text="✏ Изменённые сообщения", callback_data="menu:edited"),
            InlineKeyboardButton(text="⚙ Настройки", callback_data="menu:settings"),
        ],
        [
            InlineKeyboardButton(text="📊 Статус", callback_data="menu:status"),
            InlineKeyboardButton(text="ℹ Информация", callback_data="menu:info"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== ОБРАБОТЧИКИ ====================

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Обрабатывает команду /start и показывает главное меню."""
    if message.from_user and message.from_user.id != OWNER_ID:
        return

    log_action("START", f"Пользователь {message.from_user.id} открыл меню")

    stats = await get_stats()
    messages_count = stats.get("messages_processed", 0)

    text = (
        "🏠 <b>Главное меню</b>\n\n"
        "Добро пожаловать в панель управления ботом!\n\n"
        f"📨 Обработано сообщений: <b>{messages_count}</b>\n\n"
        "Выберите раздел:"
    )

    await message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "menu:main")
async def callback_main_menu(callback_query) -> None:
    """Возврат в главное меню по кнопке."""
    if callback_query.from_user.id != OWNER_ID:
        return

    stats = await get_stats()
    messages_count = stats.get("messages_processed", 0)

    text = (
        "🏠 <b>Главное меню</b>\n\n"
        "Добро пожаловать в панель управления ботом!\n\n"
        f"📨 Обработано сообщений: <b>{messages_count}</b>\n\n"
        "Выберите раздел:"
    )

    await callback_query.message.edit_text(
        text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback_query.answer()
