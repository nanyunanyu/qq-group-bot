from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from room_bot import build_ai_room_context, build_room_report, fetch_lobby

from qq_bot.config import BotSettings

LobbyFetcher = Callable[..., dict[str, Any]]


class RoomReportUnavailable(RuntimeError):
    pass


_ROOM_CONTEXT_KEYWORDS = (
    "房间",
    "空位",
    "满人",
    "几个人",
    "几人",
    "yuzu",
    "citra",
    "gu",
    "xx",
    "4g",
    "3g",
)


def needs_room_context(question: str) -> bool:
    normalized = question.casefold()
    return any(keyword in normalized for keyword in _ROOM_CONTEXT_KEYWORDS)


def render_room_report(
    settings: BotSettings,
    *,
    fetcher: LobbyFetcher = fetch_lobby,
) -> str:
    payload = fetcher(
        settings.lobby_url,
        timeout=settings.report_timeout_seconds,
    )
    return build_room_report(payload)


def render_ai_room_context(
    settings: BotSettings,
    *,
    fetcher: LobbyFetcher = fetch_lobby,
) -> str:
    payload = fetcher(
        settings.lobby_url,
        timeout=settings.report_timeout_seconds,
    )
    return build_ai_room_context(payload)


async def load_ai_room_context(
    settings: BotSettings,
    *,
    fetcher: LobbyFetcher = fetch_lobby,
) -> str:
    try:
        return await asyncio.to_thread(
            render_ai_room_context,
            settings,
            fetcher=fetcher,
        )
    except Exception as error:
        raise RoomReportUnavailable from error


async def load_room_report(
    settings: BotSettings,
    *,
    fetcher: LobbyFetcher = fetch_lobby,
) -> str:
    try:
        return await asyncio.to_thread(
            render_room_report,
            settings,
            fetcher=fetcher,
        )
    except Exception as error:
        raise RoomReportUnavailable from error