"""Сборка Telegram Application и регистрация хендлеров."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

from app.config import CONFIG
from app.handlers import admin, free_session, help, history, menu, messages, providers, settings, spreads, start
from app.logging_config import setup_logging
from app.services.storage_service import StorageService

_log = logging.getLogger(__name__)


async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    _log.exception("Ошибка обработчика Telegram", exc_info=context.error)
    if context.error is None:
        return
    chat_id = None
    if isinstance(update, Update):
        if update.effective_chat:
            chat_id = update.effective_chat.id
    if chat_id is None:
        return
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Произошла ошибка. Попробуйте ещё раз или откройте /start.",
        )
    except Exception:
        _log.exception("Не удалось отправить пользователю сообщение об ошибке")


async def _post_init(application: Application) -> None:
    _log.info("Бот запущен (polling).")


def build_application() -> Application:
    """Создаёт и настраивает python-telegram-bot Application."""

    if not CONFIG.telegram_bot_token:
        msg = "TELEGRAM_BOT_TOKEN не задан в .env"
        raise RuntimeError(msg)

    storage = StorageService()
    storage.init_db()

    t = max(5.0, float(CONFIG.telegram_http_timeout_seconds))
    telegram_request = HTTPXRequest(
        connect_timeout=t,
        read_timeout=t,
        write_timeout=t,
        pool_timeout=t,
    )

    # concurrent_updates=False: сценарии опираются на context.user_data (расклад, FSM).
    application = (
        Application.builder()
        .token(CONFIG.telegram_bot_token)
        .request(telegram_request)
        .concurrent_updates(False)
        .post_init(_post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start.cmd_start))
    application.add_handler(CommandHandler("help", help.cmd_help))
    application.add_handler(CommandHandler("cancel", messages.cmd_cancel))
    application.add_handler(CommandHandler("settings", settings.cmd_settings))
    application.add_handler(CommandHandler("history", history.cmd_history))
    application.add_handler(CommandHandler("stats", admin.cmd_stats))

    application.add_handler(CallbackQueryHandler(menu.callback_main_menu, pattern=r"^m:"))
    application.add_handler(CallbackQueryHandler(free_session.callback_free, pattern=r"^fr:"))
    application.add_handler(CallbackQueryHandler(messages.callback_post_reading_pick, pattern=r"^pr:"))
    application.add_handler(CallbackQueryHandler(spreads.callback_category, pattern=r"^c:"))
    application.add_handler(CallbackQueryHandler(spreads.callback_back_category, pattern=r"^bc:"))
    application.add_handler(CallbackQueryHandler(spreads.callback_spread_info, pattern=r"^s:"))
    application.add_handler(CallbackQueryHandler(spreads.callback_spread_confirm, pattern=r"^sc:"))
    application.add_handler(CallbackQueryHandler(spreads.callback_change_spread, pattern=r"^f:chg_spread$"))

    application.add_handler(CallbackQueryHandler(messages.callback_new_spread, pattern=r"^f:new$"))
    application.add_handler(CallbackQueryHandler(messages.callback_save_reading, pattern=r"^f:save$"))
    application.add_handler(CallbackQueryHandler(providers.callback_change_ai, pattern=r"^f:chg_ai$"))

    application.add_handler(CallbackQueryHandler(providers.callback_pick_provider, pattern=r"^p:"))
    application.add_handler(CallbackQueryHandler(providers.callback_pick_model, pattern=r"^md:"))

    application.add_handler(CallbackQueryHandler(settings.callback_settings_entry, pattern=r"^st:"))
    application.add_handler(CallbackQueryHandler(settings.callback_reading_mode, pattern=r"^rm:"))
    application.add_handler(CallbackQueryHandler(settings.callback_reading_style, pattern=r"^rs:"))

    application.add_handler(CallbackQueryHandler(messages.callback_cancel, pattern=r"^x:cancel$"))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, messages.handle_user_text)
    )

    application.add_error_handler(_on_error)

    return application


def main() -> None:
    """Точка входа: логирование и polling."""

    setup_logging()
    _log.info("Инициализация приложения")
    app = build_application()
    app.run_polling(allowed_updates=["message", "callback_query"])
