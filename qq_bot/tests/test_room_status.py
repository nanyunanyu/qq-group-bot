import asyncio

import pytest

from qq_bot.config import BotSettings
from qq_bot.services.room_status import (
    RoomReportUnavailable,
    load_ai_room_context,
    load_room_report,
    needs_room_context,
    render_ai_room_context,
    render_room_report,
)


SETTINGS = BotSettings(
    allowed_group_ids=frozenset({1032631393}),
    lobby_url="http://private-lobby:8080/lobby",
    report_timeout_seconds=2.5,
)


def test_render_room_report_fetches_lobby_data():
    calls = []

    def fetcher(url: str, *, timeout: float):
        calls.append((url, timeout))
        return {
            "rooms": [
                {
                    "name": "怪物猎人GU房间1 | 联机请加群：1032631393",
                    "port": 9001,
                    "maxPlayers": 4,
                    "players": [{"nickname": "Hunter"}],
                }
            ]
        }

    report = render_room_report(SETTINGS, fetcher=fetcher)

    assert calls == [("http://private-lobby:8080/lobby", 2.5)]
    assert "GU房间1\n端口：9001\n人数：1/4\n玩家：Hunter" in report


def test_render_ai_room_context_uses_fixed_settings_and_redacts_private_fields():
    calls = []

    def fetcher(url: str, *, timeout: float):
        calls.append((url, timeout))
        return {
            "rooms": [
                {
                    "name": "怪物猎人GU房间1 | 联机请加群：1032631393",
                    "port": 9001,
                    "maxPlayers": 4,
                    "address": "172.20.0.3",
                    "players": [{"nickname": "PrivateHunter"}],
                }
            ]
        }

    context = render_ai_room_context(SETTINGS, fetcher=fetcher)

    assert calls == [(SETTINGS.lobby_url, SETTINGS.report_timeout_seconds)]
    assert "Yuzu / GU房间1：在线，人数 1/4，有空位" in context
    assert "PrivateHunter" not in context
    assert "9001" not in context
    assert "172.20.0.3" not in context


def test_room_context_intent_is_deterministic():
    assert needs_room_context("GU 房间现在有空位吗？")
    assert needs_room_context("Citra 在线人数")
    assert not needs_room_context("查询网站在线人数统计")
    assert not needs_room_context("推荐一套太刀配装")


def test_load_ai_room_context_wraps_fetch_failures():
    def failing_fetcher(url: str, *, timeout: float):
        raise TimeoutError

    with pytest.raises(RoomReportUnavailable):
        asyncio.run(load_ai_room_context(SETTINGS, fetcher=failing_fetcher))


def test_load_room_report_wraps_fetch_failures():
    def failing_fetcher(url: str, *, timeout: float):
        raise TimeoutError

    with pytest.raises(RoomReportUnavailable):
        asyncio.run(load_room_report(SETTINGS, fetcher=failing_fetcher))