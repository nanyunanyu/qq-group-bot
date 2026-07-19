from dataclasses import dataclass
from datetime import datetime
import json
import os
from typing import Any
from urllib.request import urlopen
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class ManagedRoom:
    platform: str
    label: str
    name: str
    port: int
    max_players: int


@dataclass(frozen=True)
class RoomSnapshot:
    platform: str
    label: str
    port: int
    max_players: int
    player_count: int
    player_names: tuple[str, ...]
    is_online: bool


@dataclass(frozen=True)
class LobbySnapshot:
    rooms: tuple[RoomSnapshot, ...]
    updated_at: datetime


MANAGED_ROOMS = (
    ManagedRoom("Yuzu", "GU房间1", "怪物猎人GU房间1 | 联机请加群：1032631393", 9001, 4),
    ManagedRoom("Yuzu", "GU房间2", "怪物猎人GU房间2 | 联机请加群：1032631393", 9002, 4),
    ManagedRoom("Citra", "XX房间1", "怪物猎人XX房间1 | 联机请加群：1032631393", 10001, 4),
    ManagedRoom("Citra", "XX房间2", "怪物猎人XX房间2 | 联机请加群：1032631393", 10002, 4),
    ManagedRoom("Citra", "4G房间1", "怪物猎人4G房间1 | 联机请加群：1032631393", 10003, 4),
    ManagedRoom("Citra", "4G房间2", "怪物猎人4G房间2 | 联机请加群：1032631393", 10004, 4),
    ManagedRoom("Citra", "3G房间", "怪物猎人3G | 联机请加群：1032631393", 10005, 4),
    ManagedRoom("Citra", "新手房间", "怪物猎人新手 | 联机请加群：1032631393", 10006, 8),
)


def fetch_lobby(url: str | None = None, timeout: float = 5.0) -> dict[str, Any]:
    lobby_url = url or os.getenv("PRIVATE_LOBBY_URL", "http://private-lobby:8080/lobby")
    with urlopen(lobby_url, timeout=timeout) as response:
        return json.load(response)


def project_lobby(
    payload: dict[str, Any],
    *,
    updated_at: datetime | None = None,
) -> LobbySnapshot:
    lobby_rooms = {
        (room.get("name"), room.get("port")): room
        for room in payload.get("rooms", [])
        if isinstance(room, dict)
    }
    snapshots = []
    for managed in MANAGED_ROOMS:
        room = lobby_rooms.get((managed.name, managed.port))
        raw_players = room.get("players", []) if room else []
        players = raw_players if isinstance(raw_players, list) else []
        player_names = tuple(
            nickname
            for player in players
            if isinstance(player, dict)
            and isinstance((nickname := player.get("nickname")), str)
            and nickname
        )
        raw_capacity = room.get("maxPlayers") if room else None
        capacity = (
            raw_capacity
            if isinstance(raw_capacity, int) and raw_capacity > 0
            else managed.max_players
        )
        snapshots.append(
            RoomSnapshot(
                platform=managed.platform,
                label=managed.label,
                port=managed.port,
                max_players=capacity,
                player_count=len(players),
                player_names=player_names,
                is_online=room is not None,
            )
        )

    timestamp = updated_at or datetime.now(
        ZoneInfo(os.getenv("ROOM_REPORT_TIMEZONE", "Asia/Shanghai"))
    )
    return LobbySnapshot(rooms=tuple(snapshots), updated_at=timestamp)


def render_room_report(snapshot: LobbySnapshot) -> str:
    empty_room_labels = [
        room.label for room in snapshot.rooms if room.player_count == 0
    ]
    sections = ["联机房间状态"]
    for platform in ("Yuzu", "Citra"):
        room_blocks = [
            "\n".join(
                (
                    room.label,
                    f"端口：{room.port}",
                    f"人数：{room.player_count}/{room.max_players}",
                    f"玩家：{'、'.join(room.player_names) or 'Nobody Here'}",
                )
            )
            for room in snapshot.rooms
            if room.platform == platform and room.player_count > 0
        ]
        if room_blocks:
            sections.append(f"【{platform}】\n" + "\n\n".join(room_blocks))

    if empty_room_labels:
        sections.append(f"【{'、'.join(empty_room_labels)}均无人】")
    sections.append(f"更新时间：{snapshot.updated_at:%Y-%m-%d %H:%M:%S}")
    return "\n\n".join(sections)


def build_room_report(
    payload: dict[str, Any],
    *,
    updated_at: datetime | None = None,
) -> str:
    return render_room_report(project_lobby(payload, updated_at=updated_at))


def build_ai_room_context(
    payload: dict[str, Any],
    *,
    updated_at: datetime | None = None,
) -> str:
    snapshot = project_lobby(payload, updated_at=updated_at)
    room_lines = []
    for room in snapshot.rooms:
        if not room.is_online:
            room_lines.append(
                f"- {room.platform} / {room.label}：当前未登记，状态未知"
            )
            continue
        availability = "已满" if room.player_count >= room.max_players else "有空位"
        room_lines.append(
            f"- {room.platform} / {room.label}：在线，"
            f"人数 {room.player_count}/{room.max_players}，{availability}"
        )
    room_lines.append(f"更新时间：{snapshot.updated_at:%Y-%m-%d %H:%M:%S}")
    return "\n".join(room_lines)


def handle_room_command(
    message: str,
    *,
    lobby_url: str | None = None,
) -> str | None:
    if message.strip() != "/房间":
        return None
    return build_room_report(fetch_lobby(lobby_url))