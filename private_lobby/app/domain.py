from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class Member(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nickname: str
    username: str = ""
    gameName: str = ""
    avatarUrl: str = ""
    gameId: int = 0


class RoomRegistration(BaseModel):
    model_config = ConfigDict(extra="ignore")

    port: int = Field(ge=1, le=65535)
    name: str = Field(min_length=1)
    description: str = ""
    preferredGameName: str
    preferredGameId: int = 0
    maxPlayers: int = Field(ge=2, le=16)
    netVersion: int = Field(ge=1)
    hasPassword: bool = False
    players: list[Member] = Field(default_factory=list)


class PlayerUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    players: list[Member] = Field(default_factory=list)


class PublicRoom(RoomRegistration):
    externalGuid: str
    id: str
    address: str
    owner: str


class LobbyResponse(BaseModel):
    rooms: list[PublicRoom]


@dataclass(frozen=True)
class RoomRecord:
    room_id: str
    external_guid: str
    owner: str
    address: str
    registration: RoomRegistration
    players: tuple[Member, ...]
    updated_at: float
    created_at: datetime


def create_record(
    *,
    room_id: str,
    external_guid: str,
    owner: str,
    address: str,
    registration: RoomRegistration,
    now: float,
) -> RoomRecord:
    return RoomRecord(
        room_id=room_id,
        external_guid=external_guid,
        owner=owner,
        address=address,
        registration=registration,
        players=tuple(registration.players),
        updated_at=now,
        created_at=datetime.now(timezone.utc),
    )


def update_players(record: RoomRecord, players: list[Member], now: float) -> RoomRecord:
    return replace(record, players=tuple(players), updated_at=now)


def to_public_room(record: RoomRecord) -> PublicRoom:
    room = record.registration.model_dump(exclude={"players"})
    return PublicRoom(
        **room,
        externalGuid=record.external_guid,
        id=record.room_id,
        address=record.address,
        owner=record.owner,
        players=list(record.players),
    )