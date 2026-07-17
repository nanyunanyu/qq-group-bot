import asyncio
from collections.abc import Callable
import time
from uuid import uuid4

from .domain import (
    Member,
    RoomRecord,
    RoomRegistration,
    create_record,
    to_public_room,
    update_players,
)


class RoomNotFoundError(KeyError):
    pass


class RoomOwnershipError(PermissionError):
    pass


class RoomStore:
    def __init__(
        self,
        ttl_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._rooms: dict[str, RoomRecord] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        *,
        owner: str,
        address: str,
        registration: RoomRegistration,
    ) -> RoomRecord:
        now = self._clock()
        room_id = str(uuid4())
        record = create_record(
            room_id=room_id,
            external_guid=str(uuid4()),
            owner=owner,
            address=address,
            registration=registration,
            now=now,
        )
        async with self._lock:
            self._prune(now)
            self._rooms[room_id] = record
        return record

    async def update(
        self,
        *,
        room_id: str,
        owner: str,
        players: list[Member],
    ) -> RoomRecord:
        now = self._clock()
        async with self._lock:
            self._prune(now)
            record = self._get_owned(room_id, owner)
            updated = update_players(record, players, now)
            self._rooms[room_id] = updated
            return updated

    async def delete(self, *, room_id: str, owner: str) -> None:
        async with self._lock:
            record = self._rooms.get(room_id)
            if record is None:
                raise RoomNotFoundError(room_id)
            if record.owner != owner:
                raise RoomOwnershipError(room_id)
            del self._rooms[room_id]

    async def list_rooms(self) -> list:
        now = self._clock()
        async with self._lock:
            self._prune(now)
            records = sorted(
                self._rooms.values(),
                key=lambda record: (record.registration.netVersion, record.registration.port),
            )
            return [to_public_room(record) for record in records]

    def _get_owned(self, room_id: str, owner: str) -> RoomRecord:
        record = self._rooms.get(room_id)
        if record is None:
            raise RoomNotFoundError(room_id)
        if record.owner != owner:
            raise RoomOwnershipError(room_id)
        return record

    def _prune(self, now: float) -> None:
        expired = [
            room_id
            for room_id, record in self._rooms.items()
            if now - record.updated_at > self._ttl_seconds
        ]
        for room_id in expired:
            del self._rooms[room_id]