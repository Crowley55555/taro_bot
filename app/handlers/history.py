"""История: список сохранённых раскладов и свободных сессий, открытие и продолжение."""

from __future__ import annotations

from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.keyboards import after_reading_keyboard, free_session_actions_keyboard, history_pagination_keyboard, main_menu
from app.services.session_service import deserialize_cards, ensure_defaults
from app.services.storage_service import StorageService
from app.services.user_persistence import (
    migrate_legacy_reading_to_persisted,
    restore_classic_from_persisted,
    restore_free_from_persisted_row,
)
from app.states import KEY_FREE_CURRENT_SPREAD_SIZE, KEY_FREE_CURRENT_CARDS, KEY_STATE, STATE_FREE_SESSION_WAITING_QUESTION
from app.utils.text import format_cards_list_html

PAGE_SIZE = 8
_KIND_FROM_CB = {"c": "classic", "f": "free", "l": "legacy"}
_KIND_TO_CB = {"classic": "c", "free": "f", "legacy": "l"}


def _fmt_ts(dt: datetime) -> str:
    try:
        return dt.strftime("%d.%m %H:%M")
    except (TypeError, ValueError, OSError):
        return ""


def _kind_title(kind: str) -> str:
    return {"classic": "Классика", "free": "Свободный", "legacy": "Сохр."}.get(kind, "Запись")


def _build_list_view(user_id: int, page: int) -> tuple[str, InlineKeyboardMarkup]:
    storage = StorageService()
    storage.init_db()
    offset = page * PAGE_SIZE
    items = storage.list_user_history_merged(user_id, limit=PAGE_SIZE + 1, offset=offset)
    has_next = len(items) > PAGE_SIZE
    items = items[:PAGE_SIZE]
    total = storage.count_history_rows_for_user(user_id)

    if not items:
        text = (
            "<b>История</b>\n\nПока нет записей. Сделайте расклад или свободную сессию — "
            "состояние сохраняется автоматически после толкования и обсуждений."
        )
        return text, InlineKeyboardMarkup([[InlineKeyboardButton("Главное меню", callback_data="m:main")]])

    header = f"<b>История</b> <i>(всего {total})</i>\nВыберите запись:\n"
    rows: list[list[InlineKeyboardButton]] = []
    for it in items:
        k = _KIND_TO_CB.get(it.kind, "c")
        ts = _fmt_ts(it.updated_at)
        short = it.label if len(it.label) <= 40 else it.label[:37] + "…"
        label_btn = f"{_kind_title(it.kind)}: {short} · {ts}"
        if len(label_btn) > 58:
            label_btn = label_btn[:55] + "…"
        rows.append(
            [
                InlineKeyboardButton(label_btn, callback_data=f"hist:o:{k}:{it.record_id}"),
                InlineKeyboardButton("×", callback_data=f"hist:d:{k}:{it.record_id}"),
            ]
        )

    nav_kb = history_pagination_keyboard(page=page, has_next=has_next)
    markup_rows = rows + list(nav_kb.inline_keyboard)
    return header, InlineKeyboardMarkup(markup_rows)


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список истории."""

    if not update.effective_user:
        return

    ensure_defaults(context.user_data)
    uid = update.effective_user.id
    text, kb = _build_list_view(uid, page=0)

    if update.message:
        await update.message.reply_html(text, reply_markup=kb)
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


async def callback_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """hist:l:page | hist:o:k:id | hist:d:k:id"""

    q = update.callback_query
    if not q or not q.data or not q.data.startswith("hist:"):
        return
    await q.answer()
    ensure_defaults(context.user_data)
    user = update.effective_user
    if not user:
        return

    parts = q.data.split(":")
    if len(parts) < 2:
        return

    action = parts[1]
    storage = StorageService()
    storage.init_db()

    if action == "l":
        page = int(parts[2]) if len(parts) > 2 else 0
        text, kb = _build_list_view(user.id, page=page)
        await q.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        return

    if action == "d" and len(parts) >= 4:
        k = parts[2]
        rid = int(parts[3])
        hkind = _KIND_FROM_CB.get(k)
        if hkind == "classic":
            storage.delete_classic_persisted(rid, user.id)
        elif hkind == "free":
            storage.delete_free_persisted(rid, user.id)
        elif hkind == "legacy":
            storage.delete_legacy_reading(rid, user.id)
        text, kb = _build_list_view(user.id, page=0)
        await q.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        return

    if action == "o" and len(parts) >= 4:
        k = parts[2]
        rid = int(parts[3])
        kind = _KIND_FROM_CB.get(k)
        ud = context.user_data

        if kind == "legacy":
            legacy = storage.get_legacy_reading(rid, user.id)
            if not legacy:
                await q.message.reply_text("Запись не найдена.", reply_markup=main_menu())
                return
            new_id = migrate_legacy_reading_to_persisted(
                storage, legacy, user_id=user.id, username=user.username
            )
            row = storage.get_classic_persisted(new_id, user.id)
            if not row:
                await q.message.reply_text("Не удалось восстановить запись.", reply_markup=main_menu())
                return
            restore_classic_from_persisted(ud, row)
            await q.message.edit_text(
                "<b>Расклад восстановлен.</b>\n\n"
                "Можете написать уточняющий вопрос по текущим картам или выбрать новый шаг (1 / 3 / 5 карт).",
                parse_mode="HTML",
                reply_markup=after_reading_keyboard(),
            )
            return

        if kind == "classic":
            row = storage.get_classic_persisted(rid, user.id)
            if not row:
                await q.message.reply_text("Запись не найдена.", reply_markup=main_menu())
                return
            restore_classic_from_persisted(ud, row)
            await q.message.edit_text(
                "<b>Расклад восстановлен.</b>\n\n"
                "Можете написать уточняющий вопрос по текущим картам или выбрать новый шаг (1 / 3 / 5 карт).",
                parse_mode="HTML",
                reply_markup=after_reading_keyboard(),
            )
            return

        if kind == "free":
            row = storage.get_free_persisted(rid, user.id)
            if not row:
                await q.message.reply_text("Запись не найдена.", reply_markup=main_menu())
                return
            restore_free_from_persisted_row(ud, row)
            await q.message.edit_text(
                "<b>Свободный расклад восстановлен.</b>\n\n"
                "Можете продолжить обсуждение текущего шага текстом или выбрать 1 / 3 / 5 карт для следующего шага.",
                parse_mode="HTML",
                reply_markup=free_session_actions_keyboard(),
            )
            if str(ud.get(KEY_STATE)) == STATE_FREE_SESSION_WAITING_QUESTION:
                cards_raw = ud.get(KEY_FREE_CURRENT_CARDS)
                if isinstance(cards_raw, list) and cards_raw:
                    drawn = deserialize_cards(cards_raw)  # type: ignore[arg-type]
                    body = format_cards_list_html(drawn)
                    sz = int(ud.get(KEY_FREE_CURRENT_SPREAD_SIZE) or len(drawn))
                    await q.message.reply_html(
                        f"<b>Карты на столе ({sz}):</b>\n{body}\n\n"
                        "Напишите вопрос к этому шагу одним сообщением.",
                    )
            return
