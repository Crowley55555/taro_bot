"""Режим «Свободный расклад»: тема → 1/3/5 карт → вопрос → толкование (до N шагов) + обсуждение без новых карт."""

from __future__ import annotations

import logging
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from app.config import CONFIG
from app.keyboards import free_session_actions_keyboard, main_menu
from app.llm.exceptions import ConfigurationError, ProviderRequestError
from app.models.entities import DrawnCard
from app.services.reading_service import run_free_discussion_reading, run_free_session_reading
from app.services.session_service import (
    append_free_discussion_turn,
    deserialize_cards,
    ensure_defaults,
    get_free_discussion_history,
    get_reading_mode,
    get_reading_style,
    get_model_name,
    go_idle,
    serialize_cards,
    start_free_session,
)
from app.services.storage_service import StorageService
from app.services.tarot import draw_free_spread
from app.states import (
    KEY_FREE_CURRENT_CARDS,
    KEY_FREE_CURRENT_SPREAD_SIZE,
    KEY_FREE_DISCUSSION_HISTORY,
    KEY_FREE_SESSION_HISTORY,
    KEY_FREE_SESSION_TOPIC,
    KEY_FREE_SESSION_TURN_COUNT,
    KEY_MODEL,
    KEY_PROVIDER,
    KEY_READING_MODE,
    KEY_READING_STYLE,
    KEY_STATE,
    STATE_FREE_SESSION_CHOOSE,
    STATE_FREE_SESSION_LAUNCH,
    STATE_FREE_SESSION_WAITING_QUESTION,
)
from app.utils.interpretation_reply import send_interpretation_reply
from app.utils.llm_response import is_valid_model_text, normalize_model_text
from app.utils.text import format_cards_list_html
from app.utils.validators import validate_question_length

_log = logging.getLogger(__name__)

_INVALID_MODEL_REPLY = (
    "Не удалось получить корректный ответ от модели. Попробуйте ещё раз или смените ИИ."
)


def _max_turns() -> int:
    return max(1, int(CONFIG.max_free_session_turns))


async def handle_free_session_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
) -> None:
    """Текст в свободной сессии: тема, вопрос к шагу или обсуждение текущих карт."""

    if not update.message:
        return
    ensure_defaults(context.user_data)
    ud = context.user_data
    state = str(ud.get(KEY_STATE))

    if state == STATE_FREE_SESSION_LAUNCH:
        ok, err = validate_question_length(text)
        if not ok:
            await update.message.reply_text(err or "Некорректный текст.")
            return
        start_free_session(ud, text)
        ud[KEY_STATE] = STATE_FREE_SESSION_CHOOSE
        await update.message.reply_text(
            "Тема контекста принята. Выберите, сколько карт выпасть на этот шаг:",
            reply_markup=free_session_actions_keyboard(
                int(ud.get(KEY_FREE_SESSION_TURN_COUNT) or 0),
                _max_turns(),
            ),
        )
        return

    if state == STATE_FREE_SESSION_CHOOSE:
        cards_raw = ud.get(KEY_FREE_CURRENT_CARDS)
        hist = ud.get(KEY_FREE_SESSION_HISTORY)
        if (
            isinstance(cards_raw, list)
            and cards_raw
            and isinstance(hist, list)
            and len(hist) >= 1
        ):
            ok, err = validate_question_length(text)
            if not ok:
                await update.message.reply_text(err or "Некорректный текст.")
                return
            last = hist[-1]
            drawn = deserialize_cards(cards_raw)  # type: ignore[arg-type]
            topic = str(ud.get(KEY_FREE_SESSION_TOPIC) or "")
            prior_steps = hist[:-1] if len(hist) > 1 else []
            try:
                result = await run_free_discussion_reading(
                    provider_name=str(ud.get(KEY_PROVIDER)),
                    model_name=get_model_name(ud),
                    session_topic=topic,
                    session_history=list(prior_steps),
                    current_cards=drawn,
                    last_step_interpretation=str(last.get("interpretation", "")),
                    last_step_question=str(last.get("question", "")),
                    discussion_history=get_free_discussion_history(ud),
                    new_message=text,
                    reading_mode=get_reading_mode(ud),
                    reading_style=get_reading_style(ud),
                )
            except ConfigurationError as exc:
                await update.message.reply_text(f"Настройка ИИ: {exc}")
                return
            except ProviderRequestError as exc:
                await update.message.reply_text(str(exc))
                return
            except Exception:
                _log.exception("Ошибка обсуждения в свободной сессии")
                await update.message.reply_text(
                    "Не удалось получить ответ ИИ. Проверьте ключи и попробуйте позже.",
                )
                return

            text_out = normalize_model_text(result.content)
            if not is_valid_model_text(text_out):
                await update.message.reply_text(_INVALID_MODEL_REPLY)
                return

            append_free_discussion_turn(ud, text, text_out)
            await send_interpretation_reply(
                update.message,
                text_out,
                free_session_actions_keyboard(
                    int(ud.get(KEY_FREE_SESSION_TURN_COUNT) or 0),
                    _max_turns(),
                ),
            )
            return

        await update.message.reply_text(
            "Выберите число карт кнопками ниже или завершите контекст.",
            reply_markup=free_session_actions_keyboard(
                int(ud.get(KEY_FREE_SESSION_TURN_COUNT) or 0),
                _max_turns(),
            ),
        )
        return

    if state == STATE_FREE_SESSION_WAITING_QUESTION:
        completed = int(ud.get(KEY_FREE_SESSION_TURN_COUNT) or 0)
        if completed >= _max_turns():
            await update.message.reply_text(
                f"Достигнут лимит шагов в одном контексте ({_max_turns()}). "
                "Начните новый свободный расклад из меню или откройте главное меню.",
                reply_markup=main_menu(),
            )
            return
        ok, err = validate_question_length(text)
        if not ok:
            await update.message.reply_text(err or "Некорректный текст.")
            return

        cards_raw = ud.get(KEY_FREE_CURRENT_CARDS)
        if not isinstance(cards_raw, list) or not cards_raw:
            await update.message.reply_text("Сначала выберите число карт.")
            ud[KEY_STATE] = STATE_FREE_SESSION_CHOOSE
            return

        drawn = deserialize_cards(cards_raw)  # type: ignore[arg-type]
        topic = str(ud.get(KEY_FREE_SESSION_TOPIC) or "")
        hist = ud.get(KEY_FREE_SESSION_HISTORY)
        if not isinstance(hist, list):
            hist = []

        try:
            result = await run_free_session_reading(
                provider_name=str(ud.get(KEY_PROVIDER)),
                model_name=get_model_name(ud),
                session_topic=topic,
                history=hist,
                current_cards=drawn,
                current_question=text,
                reading_mode=get_reading_mode(ud),
                reading_style=get_reading_style(ud),
            )
        except ConfigurationError as exc:
            await update.message.reply_text(f"Настройка ИИ: {exc}")
            return
        except ProviderRequestError as exc:
            await update.message.reply_text(str(exc))
            return
        except Exception:
            _log.exception("Ошибка свободной сессии (текст)")
            await update.message.reply_text(
                "Не удалось получить ответ ИИ. Проверьте ключи и попробуйте позже.",
            )
            return

        text_out = normalize_model_text(result.content)
        if not is_valid_model_text(text_out):
            _log.warning("Свободная сессия: пустой или некорректный content после ответа API")
            await update.message.reply_text(_INVALID_MODEL_REPLY)
            return

        new_turn = completed + 1
        spread_size = int(ud.get(KEY_FREE_CURRENT_SPREAD_SIZE) or len(drawn))
        step: dict[str, Any] = {
            "turn": new_turn,
            "spread_size": spread_size,
            "cards": list(cards_raw),
            "question": text,
            "interpretation": text_out,
        }
        hist.append(step)
        ud[KEY_FREE_SESSION_HISTORY] = hist
        ud[KEY_FREE_SESSION_TURN_COUNT] = new_turn
        ud[KEY_FREE_DISCUSSION_HISTORY] = []
        ud[KEY_STATE] = STATE_FREE_SESSION_CHOOSE

        user = update.effective_user
        if user:
            storage = StorageService()
            storage.init_db()
            storage.save_free_session_step(
                user_id=user.id,
                username=user.username,
                session_topic=topic,
                turn_number=new_turn,
                spread_size=spread_size,
                cards=list(cards_raw),
                question=text,
                interpretation=text_out,
                provider=str(ud.get(KEY_PROVIDER) or ""),
                model=str(ud.get(KEY_MODEL) or ""),
                reading_mode=str(ud.get(KEY_READING_MODE) or "medium"),
                reading_style=str(ud.get(KEY_READING_STYLE) or "soft"),
            )

        await send_interpretation_reply(
            update.message,
            text_out,
            free_session_actions_keyboard(new_turn, _max_turns()),
        )
        return

    await update.message.reply_text(
        "Свободная сессия в неожиданном состоянии. Откройте /start.",
        reply_markup=main_menu(),
    )


async def callback_free(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопки fr:1 | fr:3 | fr:5 | fr:end."""

    q = update.callback_query
    if not q or not q.data or not q.data.startswith("fr:"):
        return
    await q.answer()
    ensure_defaults(context.user_data)
    ud = context.user_data
    data = q.data

    if data == "fr:end":
        go_idle(ud)
        await q.message.edit_text(
            "Контекст свободного расклада завершён.",
            reply_markup=main_menu(),
        )
        return

    if data not in {"fr:1", "fr:3", "fr:5"}:
        return

    if str(ud.get(KEY_STATE)) != STATE_FREE_SESSION_CHOOSE:
        await q.message.reply_text("Сначала задайте тему контекста через меню «Свободный расклад».")
        return

    completed = int(ud.get(KEY_FREE_SESSION_TURN_COUNT) or 0)
    if completed >= _max_turns():
        await q.message.reply_text(
            f"Лимит шагов ({_max_turns()}) уже достигнут. Начните новый контекст из меню.",
            reply_markup=main_menu(),
        )
        return

    size = int(data.split(":")[1])
    ud[KEY_FREE_DISCUSSION_HISTORY] = []
    drawn = draw_free_spread(size)
    cards_ser = serialize_cards(drawn)
    ud[KEY_FREE_CURRENT_CARDS] = cards_ser
    ud[KEY_FREE_CURRENT_SPREAD_SIZE] = size
    ud[KEY_STATE] = STATE_FREE_SESSION_WAITING_QUESTION

    cards_html = format_cards_list_html(drawn)
    await q.message.reply_html(
        f"<b>Выпало карт: {size}</b>\n{cards_html}\n\n"
        "Напишите вопрос к этому шагу одним сообщением.",
    )
