"""Режим «Свободный расклад»: тема → 1/3/5 карт → вопрос → толкование + обсуждение без новых карт."""

from __future__ import annotations

import logging
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from app.keyboards import (
    back_cancel_keyboard,
    free_session_actions_keyboard,
    main_menu,
)
from app.llm.exceptions import ConfigurationError, ProviderRequestError
from app.services.reading_service import run_free_discussion_reading, run_free_session_reading
from app.services.session_service import (
    append_free_discussion_turn,
    append_free_sliding_pair,
    clear_free_session,
    deserialize_cards,
    ensure_defaults,
    get_free_sliding_memory,
    get_reading_mode,
    get_reading_style,
    get_model_name,
    go_idle,
    serialize_cards,
    start_free_session,
)
from app.services.storage_service import StorageService
from app.services.user_persistence import (
    persist_free_if_active,
    register_free_session_row,
    save_free_snapshot,
)
from app.services.tarot import draw_free_spread
from app.states import (
    KEY_FREE_CURRENT_CARDS,
    KEY_FREE_CURRENT_SPREAD_SIZE,
    KEY_FREE_PENDING_STEP_SIZE,
    KEY_FREE_DISCUSSION_HISTORY,
    KEY_FREE_FSM,
    KEY_FREE_SESSION_ACTIVE,
    KEY_FREE_SESSION_HISTORY,
    KEY_FREE_SESSION_TOPIC,
    KEY_FREE_SESSION_TURN_COUNT,
    KEY_MODEL,
    KEY_PROVIDER,
    KEY_READING_MODE,
    KEY_READING_STYLE,
    KEY_SESSION_MODE,
    KEY_STATE,
    SESSION_MODE_FREE,
    STATE_FREE_SESSION_CHOOSE,
    STATE_FREE_SESSION_LAUNCH,
    STATE_FREE_SESSION_WAITING_QUESTION,
)
from app.utils.interpretation_reply import send_interpretation_reply
from app.utils.typing_indicator import chat_id_for_typing, typing_while_generating
from app.utils.llm_response import is_valid_model_text, normalize_model_text
from app.utils.text import format_cards_list_html
from app.utils.validators import UserMessageContext, validate_user_message

_log = logging.getLogger(__name__)

_INVALID_MODEL_REPLY = (
    "Не удалось получить корректный ответ от модели. Попробуйте ещё раз или смените ИИ."
)


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
        ok, err = validate_user_message(text, context=UserMessageContext.FREE_TOPIC_LAUNCH)
        if not ok:
            await update.message.reply_text(err or "")
            return
        start_free_session(ud, text)
        ud[KEY_STATE] = STATE_FREE_SESSION_CHOOSE
        user = update.effective_user
        if user:
            storage = StorageService()
            storage.init_db()
            register_free_session_row(
                storage,
                ud,
                user_id=user.id,
                username=user.username,
                topic=text,
            )
        await update.message.reply_text(
            "Тема контекста принята. Выберите, сколько карт выпасть на этот шаг:",
            reply_markup=free_session_actions_keyboard(),
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
            ok, err = validate_user_message(text, context=UserMessageContext.FREE_DISCUSSION)
            if not ok:
                await update.message.reply_text(err or "")
                return
            last = hist[-1]
            drawn = deserialize_cards(cards_raw)  # type: ignore[arg-type]
            topic = str(ud.get(KEY_FREE_SESSION_TOPIC) or "")
            prior_steps = hist[:-1] if len(hist) > 1 else []
            cid = chat_id_for_typing(update)
            if cid is None:
                if update.message:
                    await update.message.reply_text("Не удалось определить чат.")
                return
            try:
                async with typing_while_generating(context.bot, cid):
                    result = await run_free_discussion_reading(
                        provider_name=str(ud.get(KEY_PROVIDER)),
                        model_name=get_model_name(ud),
                        session_topic=topic,
                        session_history=list(prior_steps),
                        current_cards=drawn,
                        last_step_interpretation=str(last.get("interpretation", "")),
                        last_step_question=str(last.get("question", "")),
                        sliding_memory=get_free_sliding_memory(ud),
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
            append_free_sliding_pair(ud, text, text_out)
            user = update.effective_user
            if user:
                storage = StorageService()
                storage.init_db()
                save_free_snapshot(
                    storage,
                    ud,
                    user_id=user.id,
                    username=user.username,
                )
            await send_interpretation_reply(
                update.message,
                text_out,
                free_session_actions_keyboard(),
            )
            return

        await update.message.reply_text(
            "Выберите число карт кнопками ниже, начните новый контекст или откройте главное меню.",
            reply_markup=free_session_actions_keyboard(),
        )
        return

    if state == STATE_FREE_SESSION_WAITING_QUESTION:
        ok, err = validate_user_message(text, context=UserMessageContext.FREE_STEP_QUESTION)
        if not ok:
            await update.message.reply_text(err or "")
            return

        pending_sz = ud.get(KEY_FREE_PENDING_STEP_SIZE)
        if pending_sz is not None:
            size = int(pending_sz)
            ud.pop(KEY_FREE_PENDING_STEP_SIZE, None)
            drawn = draw_free_spread(size)
            cards_ser = serialize_cards(drawn)
            ud[KEY_FREE_CURRENT_CARDS] = cards_ser
            ud[KEY_FREE_CURRENT_SPREAD_SIZE] = size
            body = format_cards_list_html(drawn)
            await update.message.reply_html(f"<b>Выпали карты:</b>\n{body}")
        else:
            cards_raw = ud.get(KEY_FREE_CURRENT_CARDS)
            if not isinstance(cards_raw, list) or not cards_raw:
                await update.message.reply_text(
                    "Сначала выберите число карт кнопками 1 / 3 / 5.",
                )
                ud[KEY_STATE] = STATE_FREE_SESSION_CHOOSE
                return
            drawn = deserialize_cards(cards_raw)  # type: ignore[arg-type]
            cards_ser = cards_raw
        topic = str(ud.get(KEY_FREE_SESSION_TOPIC) or "")
        hist = ud.get(KEY_FREE_SESSION_HISTORY)
        if not isinstance(hist, list):
            hist = []

        cid = chat_id_for_typing(update)
        if cid is None:
            if update.message:
                await update.message.reply_text("Не удалось определить чат.")
            return
        try:
            async with typing_while_generating(context.bot, cid):
                result = await run_free_session_reading(
                    provider_name=str(ud.get(KEY_PROVIDER)),
                    model_name=get_model_name(ud),
                    session_topic=topic,
                    history=hist,
                    sliding_memory=get_free_sliding_memory(ud),
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

        completed = int(ud.get(KEY_FREE_SESSION_TURN_COUNT) or 0)
        new_turn = completed + 1
        spread_size = int(ud.get(KEY_FREE_CURRENT_SPREAD_SIZE) or len(drawn))
        step: dict[str, Any] = {
            "turn": new_turn,
            "spread_size": spread_size,
            "cards": list(cards_ser),
            "question": text,
            "interpretation": text_out,
        }
        hist.append(step)
        ud[KEY_FREE_SESSION_HISTORY] = hist
        ud[KEY_FREE_SESSION_TURN_COUNT] = new_turn
        ud[KEY_FREE_DISCUSSION_HISTORY] = []
        ud[KEY_STATE] = STATE_FREE_SESSION_CHOOSE

        append_free_sliding_pair(ud, text, text_out)

        user = update.effective_user
        if user:
            storage = StorageService()
            storage.init_db()
            save_free_snapshot(
                storage,
                ud,
                user_id=user.id,
                username=user.username,
            )

        await send_interpretation_reply(
            update.message,
            text_out,
            free_session_actions_keyboard(),
        )
        return

    await update.message.reply_text(
        "Свободная сессия в неожиданном состоянии. Откройте /start.",
        reply_markup=main_menu(),
    )


async def callback_free(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопки fr:* — карты, завершение контекста, возобновление сессии."""

    q = update.callback_query
    if not q or not q.data or not q.data.startswith("fr:"):
        return
    await q.answer()
    ensure_defaults(context.user_data)
    ud = context.user_data
    data = q.data

    if data == "fr:end":
        eu = update.effective_user
        if eu:
            storage = StorageService()
            storage.init_db()
            persist_free_if_active(storage, ud, user_id=eu.id, username=eu.username)
        clear_free_session(ud)
        go_idle(ud)
        await q.message.edit_text(
            "Контекст свободного расклада завершён.",
            reply_markup=main_menu(),
        )
        return

    if data == "fr:resume":
        if not ud.get(KEY_FREE_SESSION_ACTIVE):
            await q.message.edit_text(
                "Активной свободной сессии нет. Задайте тему нового расклада.",
                reply_markup=back_cancel_keyboard("m:main", "x:cancel"),
            )
            ud[KEY_STATE] = STATE_FREE_SESSION_LAUNCH
            return

        saved = ud.get(KEY_FREE_FSM) or STATE_FREE_SESSION_CHOOSE
        ud[KEY_STATE] = saved
        ud[KEY_SESSION_MODE] = SESSION_MODE_FREE
        ud.pop(KEY_FREE_FSM, None)
        topic = str(ud.get(KEY_FREE_SESSION_TOPIC) or "")
        short_topic = topic[:200] + ("…" if len(topic) > 200 else "")
        await q.message.edit_text(
            f"Продолжаем свободный расклад.\nТема: {short_topic}\n\n"
            "Вы можете продолжить обсуждение текущего расклада текстом или выбрать 1 / 3 / 5 карт "
            "для следующего шага.",
            reply_markup=free_session_actions_keyboard(),
        )
        if saved == STATE_FREE_SESSION_WAITING_QUESTION:
            if ud.get(KEY_FREE_PENDING_STEP_SIZE) is not None:
                sz = int(ud.get(KEY_FREE_PENDING_STEP_SIZE) or 1)
                word = "карту" if sz == 1 else "карты" if sz == 3 else "карт"
                await q.message.reply_text(
                    f"Вы уже выбрали шаг на {sz} {word}. Напишите вопрос — затем я вытяну карты.",
                )
            elif isinstance(ud.get(KEY_FREE_CURRENT_CARDS), list) and ud.get(KEY_FREE_CURRENT_CARDS):
                cards_raw = ud.get(KEY_FREE_CURRENT_CARDS)
                drawn = deserialize_cards(cards_raw)  # type: ignore[arg-type]
                cards_html = format_cards_list_html(drawn)
                sz = int(ud.get(KEY_FREE_CURRENT_SPREAD_SIZE) or len(drawn))
                await q.message.reply_html(
                    f"<b>Карты на столе ({sz}):</b>\n{cards_html}\n\n"
                    "Напишите вопрос к этому шагу одним сообщением.",
                )
        return

    if data == "fr:newctx":
        clear_free_session(ud)
        ud[KEY_STATE] = STATE_FREE_SESSION_LAUNCH
        await q.message.edit_text(
            "Новый свободный расклад. Опишите главную тему или вопрос контекста одним сообщением "
            "(одна линия смысла для всех следующих мини-раскладов в этой сессии).",
            reply_markup=back_cancel_keyboard("m:main", "x:cancel"),
        )
        return

    if data not in {"fr:1", "fr:3", "fr:5"}:
        return

    if str(ud.get(KEY_STATE)) != STATE_FREE_SESSION_CHOOSE:
        await q.message.reply_text("Сначала задайте тему контекста через меню «Свободный расклад».")
        return

    size = int(data.split(":")[1])
    ud[KEY_FREE_DISCUSSION_HISTORY] = []
    ud[KEY_FREE_PENDING_STEP_SIZE] = size
    ud.pop(KEY_FREE_CURRENT_CARDS, None)
    ud.pop(KEY_FREE_CURRENT_SPREAD_SIZE, None)
    ud[KEY_STATE] = STATE_FREE_SESSION_WAITING_QUESTION

    word = "карту" if size == 1 else "карты" if size == 3 else "карт"
    await q.message.reply_text(
        f"Вы выбрали расклад на {size} {word} для следующего шага. "
        "Напишите вопрос — после этого я вытяну карты и сделаю толкование.",
    )
