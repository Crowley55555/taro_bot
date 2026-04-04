"""Тесты индикатора печати."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.utils.typing_indicator import typing_while_generating


def test_typing_while_generating_sends_and_stops() -> None:
    async def run() -> None:
        bot = MagicMock()
        bot.send_chat_action = AsyncMock()

        async with typing_while_generating(bot, 42, interval_sec=0.08):
            await asyncio.sleep(0.02)

        assert bot.send_chat_action.await_count >= 1

    asyncio.run(run())
