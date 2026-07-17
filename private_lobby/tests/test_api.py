import os
import time

os.environ.setdefault("LOBBY_SHARED_TOKEN", "module-test-token")
os.environ.setdefault("LOBBY_KEY_DIRECTORY", "/tmp/private-lobby-module-keys")

from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(
        Settings(
            shared_token="test-token",
            key_directory=tmp_path / "keys",
            room_ttl_seconds=60,
            jwt_ttl_seconds=300,
        )
    )
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(client: TestClient, username: str = "room-host") -> dict[str, str]:
    response = client.post(
        "/jwt/internal",
        headers={"x-username": username, "x-token": "test-token"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    return {"Authorization": f"Bearer {response.text}"}


def room_payload(net_version: int = 1) -> dict:
    return {
        "port": 9001 if net_version == 1 else 10001,
        "name": "测试房间",
        "description": "内部大厅测试",
        "preferredGameName": "Monster Hunter",
        "preferredGameId": 72188436070367232,
        "maxPlayers": 4,
        "netVersion": net_version,
        "hasPassword": False,
    }


def test_registration_update_listing_and_delete(client: TestClient):
    headers = auth_headers(client)

    registered = client.post("/lobby", headers=headers, json=room_payload())
    assert registered.status_code == 200
    room = registered.json()
    assert room["id"]
    assert room["externalGuid"]
    assert room["owner"] == "room-host"
    assert room["players"] == []

    update = client.post(
        f"/lobby/{room['id']}",
        headers=headers,
        json={
            "players": [
                {
                    "nickname": "Hunter",
                    "gameName": "MONSTER HUNTER GENERATIONS ULTIMATE",
                    "gameId": 72188436070367232,
                }
            ]
        },
    )
    assert update.status_code == 200

    listed = client.get("/lobby")
    assert listed.status_code == 200
    players = listed.json()["rooms"][0]["players"]
    assert players == [
        {
            "nickname": "Hunter",
            "username": "",
            "gameName": "MONSTER HUNTER GENERATIONS ULTIMATE",
            "avatarUrl": "",
            "gameId": 72188436070367232,
        }
    ]

    deleted = client.delete(f"/lobby/{room['id']}", headers=headers)
    assert deleted.status_code == 200
    assert client.get("/lobby").json() == {"rooms": []}


def test_citra_net_version_is_preserved(client: TestClient):
    response = client.post(
        "/lobby",
        headers=auth_headers(client, "citra-host"),
        json=room_payload(net_version=4),
    )
    assert response.status_code == 200
    assert response.json()["netVersion"] == 4
    assert response.json()["port"] == 10001


def test_invalid_credentials_and_owner_are_rejected(client: TestClient):
    invalid = client.post(
        "/jwt/internal",
        headers={"x-username": "room-host", "x-token": "wrong"},
    )
    assert invalid.status_code == 401

    registered = client.post(
        "/lobby",
        headers=auth_headers(client, "owner-a"),
        json=room_payload(),
    ).json()
    forbidden = client.post(
        f"/lobby/{registered['id']}",
        headers=auth_headers(client, "owner-b"),
        json={"players": []},
    )
    assert forbidden.status_code == 403


def test_public_key_is_pem(client: TestClient):
    response = client.get("/jwt/external/key.pem")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.startswith("-----BEGIN PUBLIC KEY-----")


def test_stale_rooms_are_pruned(tmp_path):
    app = create_app(
        Settings(
            shared_token="test-token",
            key_directory=tmp_path / "keys",
            room_ttl_seconds=0,
            jwt_ttl_seconds=300,
        )
    )
    with TestClient(app) as test_client:
        response = test_client.post(
            "/lobby",
            headers=auth_headers(test_client),
            json=room_payload(),
        )
        assert response.status_code == 200
        time.sleep(0.01)
        assert test_client.get("/lobby").json() == {"rooms": []}


def test_health(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}