"""Текстовые сообщения: вопрос, уточнение, ручная модель."""

from __future__ import annotations

import logging
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from app.config import CONFIG
from app.llm.exceptions import ConfigurationError, ProviderRequestError
from app.keyboards import after_reading_keyboard, main_menu
from app.models.entities import DrawnCard
from app.services.reading_service import (
    run_primary_reading,
    run_reading_discussion_reading,
)
from app.services.session_service import (
    append_discussion_turn,
    ensure_defaults,
    get_discussion_history,
    get_reading_mode,
    get_reading_style,
    get_model_name,
    go_idle,
    replace_message_history,
    restore_after_failed_reinterpret,
    serialize_cards,
    set_provider_and_model,
)
from app.services.tarot import draw_free_spread, draw_spread
from app.services.storage_service import StorageService
from app.services.user_persistence import persist_free_if_active, save_classic_snapshot
from app.states import (
    KEY_CURRENT_CARDS,
    KEY_CURRENT_REASONING_DETAILS,
    KEY_CURRENT_SPREAD_DESCRIPTION,
    KEY_CURRENT_SPREAD_KEY,
    KEY_CURRENT_SPREAD_TITLE,
    KEY_DISCUSSION_HISTORY,
    KEY_FOLLOWUP_COUNT,
    KEY_LAST_INTERPRETATION,
    KEY_SPREAD_ANCHOR_INTERPRETATION,
    KEY_LAST_QUESTION,
    KEY_MODEL,
    KEY_PENDING_CARDS_BEFORE_DRAW,
    KEY_PENDING_MINI_SPREAD_SIZE,
    KEY_PENDING_REINTERPRET,
    KEY_PROVIDER,
    KEY_READING_MODE,
    KEY_READING_STYLE,
    KEY_STATE,
    STATE_CHOOSING_CATEGORY,
    STATE_CHOOSING_MODEL,
    STATE_FOLLOWUP_MODE,
    STATE_FREE_SESSION_CHOOSE,
    STATE_FREE_SESSION_LAUNCH,
    STATE_FREE_SESSION_WAITING_QUESTION,
    STATE_IDLE,
    STATE_WAITING_QUESTION,
)
from app.handlers.free_session import handle_free_session_text
from app.utils.interpretation_reply import send_interpretation_reply
from app.utils.typing_indicator import chat_id_for_typing, typing_while_generating
from app.utils.llm_response import is_valid_model_text, normalize_model_text
from app.utils.text import format_cards_list_html
from app.utils.validators import UserMessageContext, validate_user_message

_log = logging.getLogger(__name__)

_INVALID_MODEL_REPLY = (
    "Не удалось получить корректный ответ от модели. Попробуйте ещё раз или смените ИИ."
)


def _autosave_classic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    storage = StorageService()
    storage.init_db()
    save_classic_snapshot(
        storage,
        context.user_data,
        user_id=user.id,
        username=user.username,
    )


def _keyboard_after_failed_reinterpret(user_data: dict[str, Any]) -> Any:
    """Клавиатура после сбоя переинтерпретации: follow-up или главное меню."""

    if user_data.get(KEY_STATE) == STATE_FOLLOWUP_MODE:
        return after_reading_keyboard()
    return main_menu()


async def interpret_same_spread_after_ai_change(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Повторная интерпретация того же расклада после смены провайдера/модели."""

    ensure_defaults(context.user_data)
    qtext = str(context.user_data.get(KEY_LAST_QUESTION) or "").strip()
    if not qtext:
        msg = update.callback_query.message if update.callback_query else update.message
        if msg:
            await msg.reply_text("Нет сохранённого вопроса. Сначала сделайте расклад.")
        return

    cards_raw = context.user_data.get(KEY_CURRENT_CARDS)
    if not isinstance(cards_raw, list):
        return

    drawn = [
        DrawnCard(position_name=str(c["position_name"]), card=str(c["card"]), orientation=str(c["orientation"]))  # type: ignore[arg-type]
        for c in cards_raw
    ]
    title = str(context.user_data.get(KEY_CURRENT_SPREAD_TITLE) or "")
    desc = str(context.user_data.get(KEY_CURRENT_SPREAD_DESCRIPTION) or "")

    msg_err = update.callback_query.message if update.callback_query else update.message
    cid = chat_id_for_typing(update)
    if cid is None:
        if msg_err:
            await msg_err.reply_text("Не удалось определить чат.")
        return
    try:
        async with typing_while_generating(context.bot, cid):
            result = await run_primary_reading(
                provider_name=str(context.user_data.get(KEY_PROVIDER)),
                model_name=get_model_name(context.user_data),
                spread_title=title,
                spread_description=desc,
                cards=drawn,
                user_question=qtext,
                reading_mode=get_reading_mode(context.user_data),
                reading_style=get_reading_style(context.user_data),
            )
    except ConfigurationError as exc:
        restore_after_failed_reinterpret(context.user_data)
        if msg_err:
            await msg_err.reply_text(
                f"Настройка ИИ: {exc}",
                reply_markup=_keyboard_after_failed_reinterpret(context.user_data),
            )
        return
    except ProviderRequestError as exc:
        restore_after_failed_reinterpret(context.user_data)
        if msg_err:
            await msg_err.reply_text(
                str(exc),
                reply_markup=_keyboard_after_failed_reinterpret(context.user_data),
            )
        return
    except Exception:
        _log.exception("Ошибка повторной интерпретации")
        restore_after_failed_reinterpret(context.user_data)
        if msg_err:
            await msg_err.reply_text(
                "Не удалось получить ответ ИИ. Попробуйте позже.",
                reply_markup=_keyboard_after_failed_reinterpret(context.user_data),
            )
        return

    text_out = normalize_model_text(result.content)
    if not is_valid_model_text(text_out):
        _log.warning("Повторная интерпретация: пустой или некорректный content после ответа API")
        restore_after_failed_reinterpret(context.user_data)
        if msg_err:
            await msg_err.reply_text(
                _INVALID_MODEL_REPLY,
                reply_markup=_keyboard_after_failed_reinterpret(context.user_data),
            )
        return

    context.user_data[KEY_LAST_INTERPRETATION] = text_out
    context.user_data[KEY_SPREAD_ANCHOR_INTERPRETATION] = text_out
    context.user_data[KEY_CURRENT_REASONING_DETAILS] = result.reasoning_details
    replace_message_history(
        context.user_data,
        [
            {"role": "user", "content": qtext},
            {"role": "assistant", "content": text_out},
        ],
    )
    context.user_data[KEY_FOLLOWUP_COUNT] = 0
    context.user_data[KEY_STATE] = STATE_FOLLOWUP_MODE
    context.user_data[KEY_DISCUSSION_HISTORY] = []

    _autosave_classic(update, context)

    msg = update.callback_query.message if update.callback_query else update.message
    if not msg:
        return
    await send_interpretation_reply(msg, text_out, after_reading_keyboard())


async def handle_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает пользовательский текст в зависимости от состояния."""

    if not update.message or not update.message.text:
        return
    ensure_defaults(context.user_data)
    state = str(context.user_data.get(KEY_STATE, STATE_IDLE))
    text = update.message.text.strip()

    if state in (
        STATE_FREE_SESSION_LAUNCH,
        STATE_FREE_SESSION_CHOOSE,
        STATE_FREE_SESSION_WAITING_QUESTION,
    ):
        await handle_free_session_text(update, context, text)
        return

    if state == STATE_IDLE:
        await update.message.reply_text(
            "Сначала выберите действие в меню или отправьте /start.",
            reply_markup=main_menu(),
        )
        return

    if state == STATE_CHOOSING_MODEL:
        prov = str(context.user_data.get(KEY_PROVIDER, CONFIG.default_llm_provider))
        set_provider_and_model(context.user_data, prov, text)
        context.user_data[KEY_STATE] = STATE_IDLE
        await update.message.reply_text(
            f"Модель сохранена: {context.user_data[KEY_MODEL]}",
            reply_markup=main_menu(),
        )
        if context.user_data.pop(KEY_PENDING_REINTERPRET, False):
            await interpret_same_spread_after_ai_change(update, context)
        return

    if state == STATE_WAITING_QUESTION:
        ok, err = validate_user_message(text, context=UserMessageContext.PRIMARY_FIRST_QUESTION)
        if not ok:
            await update.message.reply_text(err or "")
            return
        await _ensure_cards_drawn_before_primary(update, context)
        await _handle_primary(update, context, text)
        return

    if state == STATE_FOLLOWUP_MODE:
        ok, err = validate_user_message(text, context=UserMessageContext.FOLLOWUP_DISCUSSION)
        if not ok:
            await update.message.reply_text(err or "")
            return
        await _handle_discussion(update, context, text)
        return

    await update.message.reply_text(
        "Сейчас ожидается выбор в меню. Используйте кнопки или /start.",
        reply_markup=main_menu(),
    )


async def _ensure_cards_drawn_before_primary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """После вопроса: при необходимости вытягивает карты и показывает их пользователю."""

    ud = context.user_data
    if not ud.get(KEY_PENDING_CARDS_BEFORE_DRAW):
        return
    key = str(ud.get(KEY_CURRENT_SPREAD_KEY) or "")
    if key == "__mini_step__":
        size = int(ud.get(KEY_PENDING_MINI_SPREAD_SIZE) or 3)
        drawn = draw_free_spread(size)
    else:
        drawn = draw_spread(key)
    ud[KEY_CURRENT_CARDS] = serialize_cards(drawn)
    ud.pop(KEY_PENDING_CARDS_BEFORE_DRAW, None)
    ud.pop(KEY_PENDING_MINI_SPREAD_SIZE, None)
    body = format_cards_list_html(drawn)
    await update.message.reply_html(f"<b>Выпали карты:</b>\n{body}")


async def _handle_primary(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str) -> None:
    cards_raw = context.user_data.get(KEY_CURRENT_CARDS)
    if not isinstance(cards_raw, list) or not cards_raw:
        await update.message.reply_text("Сначала выберите расклад.")
        return

    drawn = [
        DrawnCard(position_name=str(c["position_name"]), card=str(c["card"]), orientation=str(c["orientation"]))  # type: ignore[arg-type]
        for c in cards_raw
    ]
    title = str(context.user_data.get(KEY_CURRENT_SPREAD_TITLE) or "")
    desc = str(context.user_data.get(KEY_CURRENT_SPREAD_DESCRIPTION) or "")

    cid = chat_id_for_typing(update)
    if cid is None:
        await update.message.reply_text("Не удалось определить чат.")
        return
    try:
        async with typing_while_generating(context.bot, cid):
            result = await run_primary_reading(
                provider_name=str(context.user_data.get(KEY_PROVIDER)),
                model_name=get_model_name(context.user_data),
                spread_title=title,
                spread_description=desc,
                cards=drawn,
                user_question=question,
                reading_mode=get_reading_mode(context.user_data),
                reading_style=get_reading_style(context.user_data),
            )
    except ConfigurationError as exc:
        await update.message.reply_text(f"Настройка ИИ: {exc}")
        return
    except ProviderRequestError as exc:
        await update.message.reply_text(str(exc))
        return
    except Exception:
        _log.exception("Ошибка первичного чтения")
        await update.message.reply_text("Не удалось получить ответ ИИ. Проверьте ключи и попробуйте позже.")
        return

    text_out = normalize_model_text(result.content)
    if not is_valid_model_text(text_out):
        _log.warning("Первичное чтение: пустой или некорректный content после ответа API")
        await update.message.reply_text(_INVALID_MODEL_REPLY)
        return

    context.user_data[KEY_LAST_QUESTION] = question
    context.user_data[KEY_LAST_INTERPRETATION] = text_out
    context.user_data[KEY_SPREAD_ANCHOR_INTERPRETATION] = text_out
    context.user_data[KEY_CURRENT_REASONING_DETAILS] = result.reasoning_details
    replace_message_history(
        context.user_data,
        [
            {"role": "user", "content": question},
            {"role": "assistant", "content": text_out},
        ],
    )
    context.user_data[KEY_FOLLOWUP_COUNT] = 0
    context.user_data[KEY_STATE] = STATE_FOLLOWUP_MODE
    context.user_data[KEY_DISCUSSION_HISTORY] = []

    _autosave_classic(update, context)

    await send_interpretation_reply(update.message, text_out, after_reading_keyboard())


async def _handle_discussion(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str) -> None:
    """Обсуждение текущего расклада без новых карт."""

    cards_raw = context.user_data.get(KEY_CURRENT_CARDS)
    if not isinstance(cards_raw, list) or not cards_raw:
        await update.message.reply_text("Нет активного расклада. Сделайте новый расклад из меню.")
        return

    drawn = [
        DrawnCard(position_name=str(c["position_name"]), card=str(c["card"]), orientation=str(c["orientation"]))  # type: ignore[arg-type]
        for c in cards_raw
    ]
    anchor_interp = normalize_model_text(context.user_data.get(KEY_SPREAD_ANCHOR_INTERPRETATION))
    if not is_valid_model_text(anchor_interp):
        anchor_interp = normalize_model_text(context.user_data.get(KEY_LAST_INTERPRETATION))
    if not is_valid_model_text(anchor_interp):
        await update.message.reply_text("Нет сохранённой интерпретации для обсуждения.")
        return

    anchor_q = str(context.user_data.get(KEY_LAST_QUESTION) or "").strip()
    disc_hist = get_discussion_history(context.user_data)

    cid = chat_id_for_typing(update)
    if cid is None:
        await update.message.reply_text("Не удалось определить чат.")
        return
    try:
        async with typing_while_generating(context.bot, cid):
            result = await run_reading_discussion_reading(
                provider_name=str(context.user_data.get(KEY_PROVIDER)),
                model_name=get_model_name(context.user_data),
                spread_title=str(context.user_data.get(KEY_CURRENT_SPREAD_TITLE) or ""),
                spread_description=str(context.user_data.get(KEY_CURRENT_SPREAD_DESCRIPTION) or ""),
                cards=drawn,
                original_question=anchor_q,
                last_interpretation=anchor_interp,
                discussion_history=disc_hist,
                new_message=question,
                reading_mode=get_reading_mode(context.user_data),
                reading_style=get_reading_style(context.user_data),
            )
    except ConfigurationError as exc:
        await update.message.reply_text(f"Настройка ИИ: {exc}")
        return
    except ProviderRequestError as exc:
        await update.message.reply_text(str(exc))
        return
    except Exception:
        _log.exception("Ошибка обсуждения")
        await update.message.reply_text("Не удалось получить ответ ИИ. Попробуйте позже.")
        return

    text_out = normalize_model_text(result.content)
    if not is_valid_model_text(text_out):
        await update.message.reply_text(_INVALID_MODEL_REPLY)
        return

    append_discussion_turn(context.user_data, question, text_out)
    context.user_data[KEY_LAST_INTERPRETATION] = text_out
    context.user_data[KEY_CURRENT_REASONING_DETAILS] = result.reasoning_details

    _autosave_classic(update, context)

    await send_interpretation_reply(update.message, text_out, after_reading_keyboard())


async def callback_post_reading_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопки pr:1 | pr:3 | pr:5 — новый шаг с новыми картами (классический режим)."""

    q = update.callback_query
    if not q or not q.data or not q.data.startswith("pr:"):
        return
    await q.answer()
    ensure_defaults(context.user_data)
    if str(context.user_data.get(KEY_STATE)) != STATE_FOLLOWUP_MODE:
        await q.message.reply_text("Сначала получите интерпретацию расклада.")
        return

    part = q.data.split(":")
    if len(part) != 2 or part[1] not in {"1", "3", "5"}:
        return
    size = int(part[1])

    context.user_data[KEY_DISCUSSION_HISTORY] = []
    context.user_data[KEY_PENDING_CARDS_BEFORE_DRAW] = True
    context.user_data[KEY_PENDING_MINI_SPREAD_SIZE] = size
    context.user_data.pop(KEY_CURRENT_CARDS, None)
    context.user_data[KEY_CURRENT_SPREAD_KEY] = "__mini_step__"
    context.user_data[KEY_CURRENT_SPREAD_TITLE] = f"Мини-расклад ({size} карт)"
    context.user_data[KEY_CURRENT_SPREAD_DESCRIPTION] = (
        "Случайные карты для следующего шага — вытянутся после вашего вопроса."
    )
    context.user_data[KEY_STATE] = STATE_WAITING_QUESTION

    _ux = (
        f"Вы выбрали расклад на {size} {'карту' if size == 1 else 'карты' if size == 3 else 'карт'}. "
        "Теперь напишите вопрос — после этого я вытяну карты и сделаю толкование."
    )
    await q.message.reply_text(_ux)


async def callback_new_spread(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Новый расклад."""

    from app.keyboards import categories_keyboard
    from app.services.session_service import clear_pending_reinterpret, reset_current_reading

    cb = update.callback_query
    if not cb or cb.data != "f:new":
        return
    await cb.answer()
    reset_current_reading(context.user_data)
    clear_pending_reinterpret(context.user_data)
    context.user_data[KEY_STATE] = STATE_CHOOSING_CATEGORY
    await cb.message.edit_text("Выберите категорию расклада:", reply_markup=categories_keyboard())


async def callback_save_reading(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сохранить расклад в SQLite."""

    q = update.callback_query
    if not q or q.data != "f:save":
        return
    await q.answer()
    ensure_defaults(context.user_data)

    user = update.effective_user
    if not user:
        return

    cards = context.user_data.get(KEY_CURRENT_CARDS)
    if not isinstance(cards, list):
        await q.message.reply_text("Нет данных расклада для сохранения.")
        return

    interp = normalize_model_text(context.user_data.get(KEY_LAST_INTERPRETATION))
    if not is_valid_model_text(interp):
        await q.message.reply_text("Нет корректной интерпретации для сохранения.")
        return

    storage = StorageService()
    storage.init_db()
    save_classic_snapshot(
        storage,
        context.user_data,
        user_id=user.id,
        username=user.username,
    )
    await q.message.reply_text("Запись в истории обновлена.", reply_markup=main_menu())


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сброс сценария."""

    ensure_defaults(context.user_data)
    u = update.effective_user
    go_idle(context.user_data)
    if u:
        storage = StorageService()
        storage.init_db()
        persist_free_if_active(storage, context.user_data, user_id=u.id, username=u.username)
    if update.message:
        await update.message.reply_text("Действие отменено.", reply_markup=main_menu())


async def callback_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline «Отмена»."""

    q = update.callback_query
    if not q or q.data != "x:cancel":
        return
    await q.answer()
    ensure_defaults(context.user_data)
    u = update.effective_user
    go_idle(context.user_data)
    if u:
        storage = StorageService()
        storage.init_db()
        persist_free_if_active(storage, context.user_data, user_id=u.id, username=u.username)
    await q.message.edit_text("Действие отменено.", reply_markup=main_menu())
