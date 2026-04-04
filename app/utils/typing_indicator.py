"""Индикатор «печатает…» на время генерации ответа LLM (sendChatAction + периодическое обновление)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from telegram import Bot, Update
from telegram.constants import ChatAction

_log = logging.getLogger(__name__)

_DEFAULT_INTERVAL_SEC = 4.5


def chat_id_for_typing(update: Update) -> int | None:
    """Chat id для send_chat_action (сообщение, callback или channel post)."""

    if update.effective_chat:
        return update.effective_chat.id
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message.chat.id
    if update.message:
        return update.message.chat.id
    if update.edited_message:
        return update.edited_message.chat.id
    return None


@asynccontextmanager
async def typing_while_generating(
    bot: Bot,
    chat_id: int,
    *,
    interval_sec: float = _DEFAULT_INTERVAL_SEC,
) -> AsyncIterator[None]:
    """
    Пока выполняется блок `async with`, фоновая задача каждые ~interval_sec секунд
    шлёт ChatAction.TYPING. После выхода из блока (успех, ошибка, исключение) цикл останавливается.
    """

    stop = asyncio.Event()

    async def _typing_loop() -> None:
        while not stop.is_set():
            try:
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except Exception as exc:
                _log.debug("send_chat_action(typing) failed: %s", exc)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_sec)
            except asyncio.TimeoutError:
                continue

    task = asyncio.create_task(_typing_loop())
    try:
        yield
    finally:
        stop.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
