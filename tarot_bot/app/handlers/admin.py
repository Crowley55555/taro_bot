"""Админ-команды."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.config import CONFIG
from app.services.storage_service import StorageService

_log = logging.getLogger(__name__)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сводная статистика по SQLite (только для админов)."""

    uid = update.effective_user.id if update.effective_user else 0
    if uid not in CONFIG.admin_user_ids:
        if update.message:
            await update.message.reply_text("Команда недоступна.")
        return

    storage = StorageService()
    storage.init_db()
    stats = storage.count_stats()
    text = f"Всего сохранённых записей: {stats.total_readings}\nУникальных пользователей: {stats.unique_users}"
    if update.message:
        await update.message.reply_text(text)