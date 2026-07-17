from dataclasses import dataclass
from pathlib import Path
import os


def _read_secret(value_name: str, file_name: str) -> str:
    value = os.getenv(value_name, "").strip()
    secret_path = os.getenv(file_name, "").strip()
    if value:
        return value
    if secret_path:
        return Path(secret_path).read_text(encoding="utf-8").strip()
    return ""


@dataclass(frozen=True)
class Settings:
    shared_token: str
    key_directory: Path
    room_ttl_seconds: int = 60
    jwt_ttl_seconds: int = 3600


def load_settings() -> Settings:
    shared_token = _read_secret("LOBBY_SHARED_TOKEN", "LOBBY_SHARED_TOKEN_FILE")
    if not shared_token:
        raise RuntimeError("LOBBY_SHARED_TOKEN or LOBBY_SHARED_TOKEN_FILE is required")

    return Settings(
        shared_token=shared_token,
        key_directory=Path(os.getenv("LOBBY_KEY_DIRECTORY", "/data/keys")),
        room_ttl_seconds=int(os.getenv("LOBBY_ROOM_TTL_SECONDS", "60")),
        jwt_ttl_seconds=int(os.getenv("LOBBY_JWT_TTL_SECONDS", "3600")),
    )