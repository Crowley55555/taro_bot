"""Справка."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.keyboards import main_menu


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "<b>Помощь</b>\n\n"
        "<b>Как пользоваться</b>\n"
        "1) «Сделать расклад» — категория → тип → подтверждение → карты → вопрос одним сообщением.\n"
        "2) «Свободный расклад» — одна тема контекста, затем циклы: выберите 1/3/5 карт, задайте вопрос шага, "
        "получите интерпретацию. Лимит шагов в одном контексте — MAX_FREE_SESSION_TURNS в .env (по умолчанию 20). "
        "Сброс: «Завершить контекст», /cancel, /start, «Сделать расклад» или главное меню.\n"
        "3) После классического расклада можно уточнять его без новых карт (лимит уточнений в настройках бота).\n"
        "4) «Сохранить расклад» записывает классический расклад в базу; раздел «История» показывает только "
        "<i>сохранённые</i> расклады.\n\n"
        "<b>Команды</b>\n"
        "/start и /cancel — сбрасывают <i>активный</i> классический расклад, свободный контекст и сценарий. "
        "Провайдер, модель, длина и стиль ответа при этом сохраняются.\n"
        "/settings — настройки ответа и переход к выбору ИИ.\n"
        "/history — последние сохранённые расклады из SQLite.\n\n"
        "<b>Ограничения</b>\n"
        "История диалога с моделью при уточнениях усечена (см. MAX_DIALOG_MESSAGES в .env). "
        "OpenRouter: опциональный режим reasoning — OPENROUTER_ENABLE_REASONING.\n\n"
        "Подробности запуска и Docker — в README проекта."
    )
    if update.message:
        await update.message.reply_html(text, reply_markup=main_menu())
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(
            text, parse_mode="HTML", reply_markup=main_menu()
        )
