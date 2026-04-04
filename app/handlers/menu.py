"""Главное меню (callback)."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.keyboards import (
    back_cancel_keyboard,
    categories_keyboard,
    free_session_resume_keyboard,
    main_menu,
    providers_keyboard,
    settings_keyboard,
)
from app.services.session_service import clear_free_session, ensure_defaults, go_idle
from app.services.storage_service import StorageService
from app.services.user_persistence import persist_free_if_active
from app.states import (
    KEY_FREE_SESSION_ACTIVE,
    KEY_STATE,
    STATE_CHOOSING_CATEGORY,
    STATE_CHOOSING_PROVIDER,
    STATE_FREE_SESSION_LAUNCH,
)

_log = logging.getLogger(__name__)


async def callback_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Маршрутизация главного меню."""

    q = update.callback_query
    if not q or not q.data:
        return
    await q.answer()
    ensure_defaults(context.user_data)

    if q.data == "m:main":
        u = update.effective_user
        go_idle(context.user_data)
        if u:
            storage = StorageService()
            storage.init_db()
            persist_free_if_active(
                storage,
                context.user_data,
                user_id=u.id,
                username=u.username,
            )
        await q.message.edit_text(
            "Главное меню. Выберите действие:",
            reply_markup=main_menu(),
        )
        return

    if q.data in {"m:spread", "m:spread_cat"}:
        clear_free_session(context.user_data)
        context.user_data[KEY_STATE] = STATE_CHOOSING_CATEGORY
        await q.message.edit_text("Выберите категорию расклада:", reply_markup=categories_keyboard())
        return

    if q.data == "m:free":
        if context.user_data.get(KEY_FREE_SESSION_ACTIVE):
            await q.message.edit_text(
                "У вас уже есть активный свободный расклад. Вы можете продолжить его или начать новый.",
                reply_markup=free_session_resume_keyboard(),
            )
            return
        clear_free_session(context.user_data)
        context.user_data[KEY_STATE] = STATE_FREE_SESSION_LAUNCH
        await q.message.edit_text(
            "Опишите главную тему или вопрос контекста одним сообщением "
            "(одна линия смысла для всех следующих мини-раскладов в этой сессии).",
            reply_markup=back_cancel_keyboard("m:main", "x:cancel"),
        )
        return

    if q.data == "m:ai":
        context.user_data[KEY_STATE] = STATE_CHOOSING_PROVIDER
        await q.message.edit_text("Выберите провайдера ИИ:", reply_markup=providers_keyboard())
        return

    if q.data == "m:set":
        await q.message.edit_text("Настройки ответа:", reply_markup=settings_keyboard())
        return

    if q.data == "m:hist":
        from app.handlers.history import cmd_history

        await cmd_history(update, context)
        return

    if q.data == "m:help":
        from app.handlers.help import cmd_help

        await cmd_help(update, context)
        return