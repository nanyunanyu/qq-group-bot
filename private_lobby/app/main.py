from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from .auth import TokenService
from .config import Settings, load_settings
from .domain import LobbyResponse, PlayerUpdate, PublicRoom, RoomRegistration, to_public_room
from .store import RoomNotFoundError, RoomOwnershipError, RoomStore


def create_app(settings: Settings | None = None) -> FastAPI:
    current_settings = settings or load_settings()
    token_service = TokenService(
        key_directory=current_settings.key_directory,
        shared_token=current_settings.shared_token,
        token_ttl_seconds=current_settings.jwt_ttl_seconds,
    )
    store = RoomStore(ttl_seconds=current_settings.room_ttl_seconds)
    app = FastAPI(
        title="Private Citra/Yuzu Lobby",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.store = store
    app.state.token_service = token_service

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/jwt/internal", response_class=PlainTextResponse)
    async def issue_internal_jwt(
        x_username: str = Header(default="", alias="x-username"),
        x_token: str = Header(default="", alias="x-token"),
    ) -> PlainTextResponse:
        encoded = token_service.authenticate_credentials(x_username, x_token)
        return PlainTextResponse(encoded, media_type="text/html")

    @app.get("/jwt/external/key.pem", response_class=PlainTextResponse)
    async def external_public_key() -> PlainTextResponse:
        return PlainTextResponse(token_service.public_key, media_type="text/plain")

    @app.get("/lobby", response_model=LobbyResponse)
    async def list_lobbies() -> LobbyResponse:
        return LobbyResponse(rooms=await store.list_rooms())

    @app.post("/lobby", response_model=PublicRoom)
    async def register_lobby(
        registration: RoomRegistration,
        request: Request,
    ) -> PublicRoom:
        owner = token_service.require_identity(request)
        address = request.client.host if request.client else ""
        record = await store.register(
            owner=owner,
            address=address,
            registration=registration,
        )
        return to_public_room(record)

    @app.post("/lobby/{room_id}")
    async def update_lobby(
        room_id: str,
        update: PlayerUpdate,
        request: Request,
    ) -> dict[str, str]:
        owner = token_service.require_identity(request)
        try:
            await store.update(room_id=room_id, owner=owner, players=update.players)
        except RoomNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found") from error
        except RoomOwnershipError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action forbidden") from error
        return {"message": "Lobby updated successfully"}

    @app.delete("/lobby/{room_id}")
    async def delete_lobby(room_id: str, request: Request) -> dict[str, str]:
        owner = token_service.require_identity(request)
        try:
            await store.delete(room_id=room_id, owner=owner)
        except RoomNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found") from error
        except RoomOwnershipError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action forbidden") from error
        return {"message": "Lobby deleted successfully"}

    return app


app = create_app()