"""Настройки длины и стиля ответа."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.keyboards import main_menu, reading_mode_keyboard, reading_style_keyboard, settings_keyboard
from app.services.session_service import ensure_defaults
from app.states import KEY_READING_MODE, KEY_READING_STYLE, KEY_STATE, STATE_CHANGING_SETTINGS, STATE_IDLE

_log = logging.getLogger(__name__)


async def callback_settings_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Подменю настроек."""

    q = update.callback_query
    if not q or not q.data or not q.data.startswith("st:"):
        return
    await q.answer()
    ensure_defaults(context.user_data)
    sub = q.data.split(":", 1)[1]
    context.user_data[KEY_STATE] = STATE_CHANGING_SETTINGS

    if sub == "mode":
        await q.message.edit_text("Длина ответа ИИ:", reply_markup=reading_mode_keyboard())
        return
    if sub == "style":
        await q.message.edit_text("Стиль ответа ИИ:", reply_markup=reading_style_keyboard())
        return


async def callback_reading_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Установка длины ответа."""

    q = update.callback_query
    if not q or not q.data or not q.data.startswith("rm:"):
        return
    await q.answer()
    ensure_defaults(context.user_data)
    mode = q.data.split(":", 1)[1]
    if mode in ("short", "medium", "deep"):
        context.user_data[KEY_READING_MODE] = mode
    context.user_data[KEY_STATE] = STATE_IDLE
    await q.message.edit_text("Длина ответа сохранена.", reply_markup=main_menu())


async def callback_reading_style(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Установка стиля ответа."""

    q = update.callback_query
    if not q or not q.data or not q.data.startswith("rs:"):
        return
    await q.answer()
    ensure_defaults(context.user_data)
    style = q.data.split(":", 1)[1]
    if style in ("soft", "psychological", "practical", "normal_ai", "predictor"):
        context.user_data[KEY_READING_STYLE] = style
    context.user_data[KEY_STATE] = STATE_IDLE
    await q.message.edit_text("Стиль ответа сохранён.", reply_markup=main_menu())


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /settings."""

    ensure_defaults(context.user_data)
    text = (
        "<b>Настройки</b>\n\n"
        "Здесь можно изменить длину и стиль ответа, а также провайдера ИИ."
    )
    if update.message:
        await update.message.reply_html(text, reply_markup=settings_keyboard())
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(
            text, parse_mode="HTML", reply_markup=settings_keyboard()
        )