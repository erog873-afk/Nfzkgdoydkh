"""
Модуль работы с базой данных SQLite.
Управляет настройками, статистикой и историей сообщений.
"""

import aiosqlite
import json
from datetime import datetime
from typing import Optional, Any

from config import DATABASE_PATH


# ==================== ИНИЦИАЛИЗАЦИЯ ====================

async def init_database() -> None:
    """Создаёт таблицы, если они не существуют."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS deleted_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                username TEXT,
                message_type TEXT,
                content TEXT,
                attachment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS edited_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                username TEXT,
                message_type TEXT,
                old_content TEXT,
                new_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                messages_processed INTEGER DEFAULT 0,
                auto_replies_sent INTEGER DEFAULT 0,
                messages_deleted_detected INTEGER DEFAULT 0,
                messages_edited_detected INTEGER DEFAULT 0,
                bot_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS ignored_users (
                user_id INTEGER PRIMARY KEY
            )
        """)

        await db.commit()

        # Инициализируем статистику, если её нет
        cursor = await db.execute("SELECT COUNT(*) FROM stats")
        count = await cursor.fetchone()
        if count and count[0] == 0:
            await db.execute(
                "INSERT INTO stats (messages_processed, bot_started_at) VALUES (0, ?)",
                (datetime.now().isoformat(),)
            )
            await db.commit()


# ==================== НАСТРОЙКИ ====================

async def get_setting(key: str, default: Any = None) -> Any:
    """Получает значение настройки по ключу."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                return row[0]
        return default


async def set_setting(key: str, value: Any) -> None:
    """Устанавливает значение настройки."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, json.dumps(value))
        )
        await db.commit()


async def get_all_settings() -> dict[str, Any]:
    """Получает все настройки."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        settings: dict[str, Any] = {}
        for key, value in rows:
            try:
                settings[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                settings[key] = value
        return settings


# ==================== СТАТИСТИКА ====================

async def update_stats(field: str, value: int = 1) -> None:
    """Обновляет статистику бота."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE stats SET {field} = {field} + ? WHERE id = 1",
            (value,)
        )
        await db.commit()


async def get_stats() -> dict[str, Any]:
    """Получает статистику бота."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT * FROM stats WHERE id = 1")
        row = await cursor.fetchone()
        if row:
            return {
                "messages_processed": row[1],
                "auto_replies_sent": row[2],
                "messages_deleted_detected": row[3],
                "messages_edited_detected": row[4],
                "bot_started_at": row[5],
            }
        return {}


# ==================== УДАЛЁННЫЕ СООБЩЕНИЯ ====================

async def save_deleted_message(
    chat_id: int,
    user_id: int,
    user_name: str,
    username: str,
    message_type: str,
    content: str,
    attachment: Optional[str] = None
) -> None:
    """Сохраняет удалённое сообщение."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO deleted_messages
               (chat_id, user_id, user_name, username, message_type, content, attachment)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (chat_id, user_id, user_name, username, message_type, content, attachment)
        )
        await db.commit()
        await update_stats("messages_deleted_detected")


async def get_deleted_messages(limit: int = 10) -> list[dict[str, Any]]:
    """Получает последние удалённые сообщения."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """SELECT chat_id, user_id, user_name, username,
                      message_type, content, attachment, created_at
               FROM deleted_messages ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [
            {
                "chat_id": r[0],
                "user_id": r[1],
                "user_name": r[2],
                "username": r[3],
                "message_type": r[4],
                "content": r[5],
                "attachment": r[6],
                "created_at": r[7],
            }
            for r in rows
        ]


async def clear_deleted_messages() -> None:
    """Очищает историю удалённых сообщений."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM deleted_messages")
        await db.commit()


# ==================== ИЗМЕНЁННЫЕ СООБЩЕНИЯ ====================

async def save_edited_message(
    chat_id: int,
    user_id: int,
    user_name: str,
    username: str,
    message_type: str,
    old_content: str,
    new_content: str
) -> None:
    """Сохраняет изменённое сообщение."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO edited_messages
               (chat_id, user_id, user_name, username, message_type, old_content, new_content)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (chat_id, user_id, user_name, username, message_type, old_content, new_content)
        )
        await db.commit()
        await update_stats("messages_edited_detected")


async def get_edited_messages(limit: int = 10) -> list[dict[str, Any]]:
    """Получает последние изменённые сообщения."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """SELECT chat_id, user_id, user_name, username,
                      message_type, old_content, new_content, created_at
               FROM edited_messages ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [
            {
                "chat_id": r[0],
                "user_id": r[1],
                "user_name": r[2],
                "username": r[3],
                "message_type": r[4],
                "old_content": r[5],
                "new_content": r[6],
                "created_at": r[7],
            }
            for r in rows
        ]


async def clear_edited_messages() -> None:
    """Очищает историю изменённых сообщений."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM edited_messages")
        await db.commit()


# ==================== ИГНОРИРУЕМЫЕ ПОЛЬЗОВАТЕЛИ ====================

async def add_ignored_user(user_id: int) -> None:
    """Добавляет пользователя в список игнорируемых."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO ignored_users (user_id) VALUES (?)",
            (user_id,)
        )
        await db.commit()


async def remove_ignored_user(user_id: int) -> None:
    """Удаляет пользователя из списка игнорируемых."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM ignored_users WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def get_ignored_users() -> list[int]:
    """Получает список игнорируемых пользователей."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM ignored_users")
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def is_user_ignored(user_id: int) -> bool:
    """Проверяет, игнорируется ли пользователь."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM ignored_users WHERE user_id = ?",
            (user_id,)
        )
        return await cursor.fetchone() is not None


# ==================== ОЧИСТКА ====================

async def clear_all_logs() -> None:
    """Очищает все логи и историю."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM deleted_messages")
        await db.execute("DELETE FROM edited_messages")
        await db.commit()
