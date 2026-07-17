from datetime import datetime, timedelta, timezone
import hmac
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException, Request, status


class TokenService:
    def __init__(self, key_directory: Path, shared_token: str, token_ttl_seconds: int) -> None:
        self._shared_token = shared_token
        self._token_ttl_seconds = token_ttl_seconds
        self._private_key, self._public_key = self._load_or_create_keys(key_directory)

    @property
    def public_key(self) -> str:
        return self._public_key.decode("ascii")

    def authenticate_credentials(self, username: str, token: str) -> str:
        if not username or not hmac.compare_digest(token, self._shared_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        return self.issue(username)

    def issue(self, username: str) -> str:
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "username": username,
                "displayName": username,
                "avatarUrl": "",
                "roles": ["user"],
                "iat": now,
                "exp": now + timedelta(seconds=self._token_ttl_seconds),
            },
            self._private_key,
            algorithm="RS256",
        )

    def require_identity(self, request: Request) -> str:
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token required",
            )
        try:
            payload = jwt.decode(token, self._public_key, algorithms=["RS256"])
        except jwt.PyJWTError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token",
            ) from error

        username = payload.get("username", "")
        if not isinstance(username, str) or not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has no username",
            )
        return username

    @staticmethod
    def _load_or_create_keys(key_directory: Path) -> tuple[bytes, bytes]:
        private_path = key_directory / "private_key.pem"
        public_path = key_directory / "public_key.pem"
        key_directory.mkdir(parents=True, exist_ok=True)

        if private_path.exists() and public_path.exists():
            return private_path.read_bytes(), public_path.read_bytes()

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        private_path.write_bytes(private_bytes)
        private_path.chmod(0o600)
        public_path.write_bytes(public_bytes)
        return private_bytes, public_bytes