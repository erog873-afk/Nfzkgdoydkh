"""
Обработчик статуса бота.
Показывает информацию о работе бота и подключении Telegram Business.
"""

from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import OWNER_ID
from database import get_stats, get_setting
from logger import log_action

router = Router(name="status")


def format_uptime(started_at: str) -> str:
    """Форматирует время работы бота."""
    try:
        start = datetime.fromisoformat(started_at)
        delta = datetime.now() - start
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days} дн")
        if hours > 0:
            parts.append(f"{hours} ч")
        parts.append(f"{minutes} мин")

        return " ".join(parts)
    except (ValueError, TypeError):
        return "неизвестно"


@router.callback_query(F.data == "menu:status")
async def callback_status(callback_query: CallbackQuery) -> None:
    """Показывает статус бота."""
    if callback_query.from_user.id != OWNER_ID:
        return

    stats = await get_stats()
    ar_enabled = await get_setting("autoresponder_enabled", False)
    monitor_deleted = await get_setting("monitor_deleted", True)
    monitor_edited = await get_setting("monitor_edited", True)

    # Проверяем Telegram Business
    business_status = "❓ Неизвестно"
    try:
        bot = callback_query.bot
        # Пытаемся получить информацию о бизнесе
        me = await bot.get_me()
        if me.can_join_groups:
            business_status = "✅ Бот активен"
        else:
            business_status = "⚠️ Бот не может присоединяться к группам"
    except Exception:
        business_status = "❌ Ошибка проверки"

    # Формируем статусы
    ar_status = "✅ Автоответчик" if ar_enabled else "❌ Автоответчик"
    del_status = "✅ Мониторинг удалений" if monitor_deleted else "❌ Мониторинг удалений"
    edit_status = "✅ Мониторинг изменений" if monitor_edited else "❌ Мониторинг изменений"

    messages_count = stats.get("messages_processed", 0)
    auto_replies = stats.get("auto_replies_sent", 0)
    deleted_detected = stats.get("messages_deleted_detected", 0)
    edited_detected = stats.get("messages_edited_detected", 0)
    started_at = stats.get("bot_started_at", "")
    uptime = format_uptime(started_at)

    text = (
        "📊 <b>Статус бота</b>\n\n"
        f"🏢 Бизнес: {business_status}\n\n"
        f"📨 {ar_status}\n"
        f"🗑 {del_status}\n"
        f"✏ {edit_status}\n\n"
        f"⏱ Время работы: <b>{uptime}</b>\n\n"
        f"📈 <b>Статистика:</b>\n"
        f"  Сообщений обработано: {messages_count}\n"
        f"  Автоответов отправлено: {auto_replies}\n"
        f"  Удалений обнаружено: {deleted_detected}\n"
        f"  Изменений обнаружено: {edited_detected}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="menu:status")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")],
    ])

    await callback_query.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback_query.answer()
