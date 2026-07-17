# Telegram Business Monitor Bot

Бот для мониторинга переписок через Telegram Business.

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

Создайте `.env` файл:

```
BOT_TOKEN=ваш_токен
OWNER_ID=ваш_telegram_id
DATABASE_PATH=data/bot_database.db
LOG_LEVEL=INFO
TIMEZONE=Europe/Moscow
```

## Запуск

```bash
python bot.py
```

## Деплой на Railway

1. Создайте проект на [Railway](https://railway.app)
2. Подключите GitHub репозиторий
3. Добавьте переменные окружения в Settings
4. Деплой произойдет автоматически

## Возможности

- Автоответчик с настройками
- Мониторинг удалённых сообщений
- Мониторинг изменённых сообщений
- Панель управления
- Статистика
