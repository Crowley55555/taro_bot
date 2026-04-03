"""Выбор категории, расклада и выпадение карт."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.keyboards import categories_keyboard, spread_confirm_keyboard, spread_list_keyboard
from app.models.entities import DrawnCard
from app.services.session_service import ensure_defaults, reset_for_new_spread, serialize_cards
from app.services.spread_catalog_service import get_spread, spreads_for_category
from app.services.tarot import draw_spread
from app.config import CONFIG
from app.states import (
    KEY_CURRENT_CARDS,
    KEY_CURRENT_SPREAD_DESCRIPTION,
    KEY_CURRENT_SPREAD_KEY,
    KEY_CURRENT_SPREAD_TITLE,
    KEY_SPREAD_CATEGORY,
    KEY_STATE,
    STATE_CHOOSING_SPREAD,
    STATE_WAITING_QUESTION,
    STATE_CHOOSING_CATEGORY,
)
from app.utils.text import escape_html, format_cards_list_html, short_spread_summary

_log = logging.getLogger(__name__)


async def callback_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Пользователь выбрал категорию раскладов."""

    q = update.callback_query
    if not q or not q.data or not q.data.startswith("c:"):
        return
    await q.answer()
    ensure_defaults(context.user_data)
    cat = q.data.split(":", 1)[1]
    context.user_data[KEY_SPREAD_CATEGORY] = cat
    context.user_data[KEY_STATE] = STATE_CHOOSING_SPREAD

    spreads = spreads_for_category(cat)
    keys = [(s.key, s.title) for s in spreads]
    if not keys:
        await q.message.edit_text("В этой категории пока нет раскладов.", reply_markup=categories_keyboard())
        return

    await q.message.edit_text("Выберите расклад:", reply_markup=spread_list_keyboard(keys))


async def callback_back_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Назад к списку раскладов категории."""

    q = update.callback_query
    if not q or not q.data or not q.data.startswith("bc:"):
        return
    await q.answer()
    ensure_defaults(context.user_data)
    cat = q.data.split(":", 1)[1]
    context.user_data[KEY_SPREAD_CATEGORY] = cat
    context.user_data[KEY_STATE] = STATE_CHOOSING_SPREAD
    spreads = spreads_for_category(cat)
    keys = [(s.key, s.title) for s in spreads]
    await q.message.edit_text("Выберите расклад:", reply_markup=spread_list_keyboard(keys))


async def callback_spread_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать описание расклада и кнопку подтверждения."""

    q = update.callback_query
    if not q or not q.data or not q.data.startswith("s:"):
        return
    await q.answer()
    ensure_defaults(context.user_data)
    key = q.data.split(":", 1)[1]
    sp = get_spread(key)
    cat = context.user_data.get(KEY_SPREAD_CATEGORY) or sp.category

    text = (
        f"<b>{escape_html(sp.title)}</b>\n\n"
        f"{escape_html(sp.short_description)}\n\n"
        f"Карт: {sp.cards_count}\n"
        f"Подходит для вопросов: {escape_html('; '.join(sp.suggested_questions[:2]))}"
    )
    await q.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=spread_confirm_keyboard(sp.key, cat),
    )


async def callback_spread_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Подтверждение расклада: тянем карты и просим вопрос."""

    q = update.callback_query
    if not q or not q.data or not q.data.startswith("sc:"):
        return
    await q.answer()
    ensure_defaults(context.user_data)
    key = q.data.split(":", 1)[1]
    sp = get_spread(key)

    reset_for_new_spread(context.user_data)
    context.user_data[KEY_SPREAD_CATEGORY] = sp.category

    cards = draw_spread(key)
    context.user_data[KEY_CURRENT_SPREAD_KEY] = sp.key
    context.user_data[KEY_CURRENT_SPREAD_TITLE] = sp.title
    context.user_data[KEY_CURRENT_SPREAD_DESCRIPTION] = sp.short_description
    context.user_data[KEY_CURRENT_CARDS] = serialize_cards(cards)
    context.user_data[KEY_STATE] = STATE_WAITING_QUESTION

    drawn: list[DrawnCard] = [
        DrawnCard(position_name=c["position_name"], card=c["card"], orientation=c["orientation"])  # type: ignore[arg-type]
        for c in context.user_data[KEY_CURRENT_CARDS]
    ]

    cards_html = format_cards_list_html(drawn)
    summary = short_spread_summary(sp.title, sp.short_description, sp.cards_count)

    await q.message.edit_text(
        f"<b>Расклад выбран.</b>\n{escape_html(summary)}\n\n"
        f"<b>Выпавшие карты:</b>\n{cards_html}\n\n"
        f"Теперь одним сообщением сформулируйте вопрос к раскладу "
        f"({CONFIG.question_min_len}–"
        f"{CONFIG.question_max_len} символов).",
        parse_mode="HTML",
    )


async def callback_change_spread(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сменить расклад: возврат к категориям."""

    q = update.callback_query
    if not q or q.data != "f:chg_spread":
        return
    await q.answer()
    ensure_defaults(context.user_data)
    reset_for_new_spread(context.user_data)
    context.user_data[KEY_STATE] = STATE_CHOOSING_CATEGORY
    await q.message.edit_text("Выберите категорию расклада:", reply_markup=categories_keyboard())