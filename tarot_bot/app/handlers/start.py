"""Команда /start и приветствие."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.keyboards import main_menu
from app.logging_config import get_logger
from app.services.session_service import ensure_defaults, go_idle

_log = get_logger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствие и главное меню."""

    if update.effective_user:
        ensure_defaults(context.user_data)
        go_idle(context.user_data)

    text = (
        "Здравствуйте! Я бот для символических раскладов Таро с ИИ-интерпретацией.\n\n"
        "Выберите действие в меню ниже. Карты не предсказывают неизбежное будущее — "
        "это инструмент для рефлексии и ясности.\n\n"
        "Команды: /help, /settings, /history, /cancel"
    )
    if update.message:
        await update.message.reply_html(text, reply_markup=main_menu())
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu())