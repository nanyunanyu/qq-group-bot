from datetime import datetime
import json

from room_bot.room_report import (
    build_ai_room_context,
    build_room_report,
    handle_room_command,
)


def room(name: str, port: int, maximum: int = 4, players: list | None = None) -> dict:
    return {
        "name": name,
        "port": port,
        "maxPlayers": maximum,
        "address": "172.20.0.3",
        "players": players or [],
    }


def test_report_maps_managed_rooms_and_players():
    payload = {
        "rooms": [
            room(
                "怪物猎人GU房间1 | 联机请加群：1032631393",
                9001,
                players=[{"nickname": "Hunter"}],
            ),
            room("怪物猎人XX房间1 | 联机请加群：1032631393", 10001),
        ]
    }

    report = build_room_report(payload, updated_at=datetime(2026, 7, 16, 18, 0, 0))

    assert "【Yuzu】\nGU房间1\n端口：9001\n人数：1/4\n玩家：Hunter" in report
    assert "GU房间2\n端口：9002\n人数：0/4\n玩家：Nobody Here" in report
    assert "【Citra】\nXX房间1\n端口：10001\n人数：0/4\n玩家：Nobody Here" in report
    assert "更新时间：2026-07-16 18:00:00" in report


def test_report_counts_players_even_when_nickname_is_empty():
    payload = {
        "rooms": [
            room(
                "怪物猎人GU房间1 | 联机请加群：1032631393",
                9001,
                players=[{"nickname": ""}],
            )
        ]
    }

    report = build_room_report(payload, updated_at=datetime(2026, 7, 16, 18, 0, 0))

    assert "GU房间1\n端口：9001\n人数：1/4\n玩家：Nobody Here" in report


def test_ai_room_context_only_contains_allowlisted_fields():
    payload = {
        "rooms": [
            room(
                "怪物猎人GU房间1 | 联机请加群：1032631393",
                9001,
                players=[{"nickname": "PrivateHunter"}],
            )
        ]
    }

    context = build_ai_room_context(
        payload,
        updated_at=datetime(2026, 7, 16, 18, 0, 0),
    )

    assert "Yuzu / GU房间1：在线，人数 1/4，有空位" in context
    assert "PrivateHunter" not in context
    assert "9001" not in context
    assert "172.20.0.3" not in context
    assert "1032631393" not in context


def test_non_room_command_is_ignored():
    assert handle_room_command("/其他") is None


def test_exact_name_and_port_are_required():
    payload = {
        "rooms": [
            room("怪物猎人GU房间1 | 联机请加群：1032631393", 9999),
            room("伪造房间 | 联机请加群：1032631393", 9001),
        ]
    }
    report = build_room_report(payload, updated_at=datetime(2026, 7, 16, 18, 0, 0))
    assert "GU房间1\n端口：9001\n人数：0/4\n玩家：Nobody Here" in report