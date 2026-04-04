"""Выбор провайдера и модели."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.config import CONFIG
from app.keyboards import main_menu, model_choice_keyboard, providers_keyboard
from app.services.session_service import ensure_defaults, set_provider_and_model
from app.states import (
    KEY_MODEL,
    KEY_PENDING_REINTERPRET,
    KEY_PROVIDER,
    KEY_STATE,
    STATE_CHOOSING_MODEL,
    STATE_CHOOSING_PROVIDER,
    STATE_IDLE,
)

_log = logging.getLogger(__name__)


async def callback_pick_provider(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выбор LLM-провайдера."""

    q = update.callback_query
    if not q or not q.data or not q.data.startswith("p:"):
        return
    await q.answer()
    ensure_defaults(context.user_data)
    prov = q.data.split(":", 1)[1]
    context.user_data[KEY_PROVIDER] = prov
    context.user_data[KEY_STATE] = STATE_CHOOSING_MODEL
    await q.message.edit_text(
        f"Провайдер: <b>{prov}</b>. Выберите модель:",
        parse_mode="HTML",
        reply_markup=model_choice_keyboard(),
    )


async def callback_pick_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выбор модели: по умолчанию или ручной ввод."""

    q = update.callback_query
    if not q or not q.data or not q.data.startswith("md:"):
        return
    await q.answer()
    ensure_defaults(context.user_data)
    mode = q.data.split(":", 1)[1]
    prov = str(context.user_data.get(KEY_PROVIDER, CONFIG.default_llm_provider))

    if mode == "def":
        set_provider_and_model(context.user_data, prov, None)
        context.user_data[KEY_STATE] = STATE_IDLE
        await q.message.edit_text(
            f"Сохранено: {prov} / {context.user_data[KEY_MODEL]}",
            reply_markup=main_menu(),
        )
        if context.user_data.pop(KEY_PENDING_REINTERPRET, False):
            from app.handlers.messages import interpret_same_spread_after_ai_change

            await interpret_same_spread_after_ai_change(update, context)
        return

    if mode == "manual":
        context.user_data[KEY_STATE] = STATE_CHOOSING_MODEL
        await q.message.edit_text(
            "Отправьте название модели одним сообщением (как в API провайдера)."
        )
        return


async def callback_change_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопка «Сменить ИИ» после расклада."""

    q = update.callback_query
    if not q or q.data != "f:chg_ai":
        return
    await q.answer()
    ensure_defaults(context.user_data)
    context.user_data[KEY_PENDING_REINTERPRET] = True
    context.user_data[KEY_STATE] = STATE_CHOOSING_PROVIDER
    await q.message.edit_text(
        "Выберите другого провайдера. Текущие карты сохранены.",
        reply_markup=providers_keyboard(),
    )