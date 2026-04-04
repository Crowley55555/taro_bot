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
        "получите интерпретацию. Активная свободная сессия сохраняется при выходе в главное меню и при /start / /cancel; "
        "новый контекст только по кнопке «Новый расклад» или «Сделать расклад» (каталог). "
        "Краткосрочная память для ИИ — последние FREE_SESSION_MEMORY_LIMIT сообщений (см. .env). "
        "Полный сброс свободного режима: «Завершить контекст» или явный новый контекст.\n"
        "3) После классического расклада можно уточнять его без новых карт (лимит уточнений в настройках бота).\n"
        "4) Раздел «История» (/history) показывает <i>автоматически сохранённые</i> классические расклады и свободные сессии "
        "(обновление после толкований и обсуждений). Откройте запись, чтобы продолжить с того же места.\n\n"
        "<b>Команды</b>\n"
        "/start и /cancel — сбрасывают <i>классический</i> расклад и возвращают в меню; "
        "<i>свободный расклад</i> при этом не сбрасывается (он хранится до «Завершить контекст», «Новый расклад» или «Сделать расклад»). "
        "Провайдер, модель, длина и стиль ответа сохраняются.\n"
        "/settings — настройки ответа и переход к выбору ИИ.\n"
        "/history — список сохранённых раскладов и свободных сессий; кнопка «×» удаляет запись.\n\n"
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
