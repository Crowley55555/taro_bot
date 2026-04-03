"""История раскладов."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.keyboards import main_menu
from app.services.storage_service import StorageService
from app.utils.text import chunk_html_record_messages, escape_html


def _format_history_record_block(r) -> str:
    title = escape_html(r.spread_title)
    q = escape_html(r.user_question[:200] + ("…" if len(r.user_question) > 200 else ""))
    interp = escape_html(r.interpretation[:400] + ("…" if len(r.interpretation) > 400 else ""))
    return (
        f"<b>{title}</b> ({escape_html(r.provider)}/{escape_html(r.model)})\n"
        f"<i>Вопрос:</i> {q}\n"
        f"<i>Фрагмент ответа:</i> {interp}\n"
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает последние сохранённые расклады пользователя."""

    if not update.effective_user:
        return

    storage = StorageService()
    storage.init_db()
    rows = storage.list_user_readings(update.effective_user.id, limit=8)
    if not rows:
        text = (
            "<b>История</b>\n\nПока нет сохранённых раскладов. "
            "После интерпретации нажмите «Сохранить расклад»."
        )
        if update.message:
            await update.message.reply_html(text, reply_markup=main_menu())
        elif update.callback_query and update.callback_query.message:
            await update.callback_query.answer()
            await update.callback_query.message.edit_text(
                text, parse_mode="HTML", reply_markup=main_menu()
            )
        return

    header = "<b>Последние расклады</b>\n\n"
    blocks = [_format_history_record_block(r) for r in rows]
    chunks = chunk_html_record_messages(header, blocks, limit=3500)

    if update.callback_query:
        await update.callback_query.answer()
        chat_id = update.callback_query.message.chat_id
        n = len(chunks)
        for i, ch in enumerate(chunks):
            await context.bot.send_message(
                chat_id=chat_id,
                text=ch,
                parse_mode="HTML",
                reply_markup=main_menu() if i == n - 1 else None,
            )
        return

    if update.message:
        n = len(chunks)
        for i, ch in enumerate(chunks):
            await update.message.reply_html(
                ch,
                reply_markup=main_menu() if i == n - 1 else None,
            )
