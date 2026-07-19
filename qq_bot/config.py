from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Mapping
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class BotSettings:
    allowed_group_ids: frozenset[int]
    lobby_url: str
    report_timeout_seconds: float
    report_timezone: str = "Asia/Shanghai"
    ai_base_url: str = ""
    ai_api_key: str = field(default="", repr=False)
    ai_model: str = ""
    ai_web_search_enabled: bool = False
    ai_persona_prompt: str = "你是群聊中的游戏助手，请使用简洁、友善的中文回答。"
    ai_timeout_seconds: float = 20.0
    ai_max_input_chars: int = 1000
    ai_max_output_chars: int = 2000
    ai_max_output_tokens: int = 512
    ai_rate_limit_requests: int = 5
    ai_rate_limit_window_seconds: float = 60.0
    ai_max_concurrency: int = 2
    ai_memory_enabled: bool = True
    ai_memory_ttl_seconds: float = 900.0
    ai_memory_max_turns: int = 6
    ai_memory_max_chars: int = 8000
    ai_memory_max_groups: int = 256

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_base_url and self.ai_api_key and self.ai_model)


def parse_group_ids(raw: str) -> frozenset[int]:
    values = (item.strip() for item in raw.split(","))
    return frozenset(int(value) for value in values if value)


def _positive_float(source: Mapping[str, str], name: str, default: str) -> float:
    value = float(source.get(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _positive_int(source: Mapping[str, str], name: str, default: str) -> int:
    value = int(source.get(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _boolean(source: Mapping[str, str], name: str, default: str) -> bool:
    value = source.get(name, default).strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _timezone(source: Mapping[str, str], name: str, default: str) -> str:
    value = source.get(name, default).strip()
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise ValueError(f"{name} must be a valid IANA timezone") from error
    return value


def _validate_ai_base_url(raw: str) -> str:
    url = raw.strip().rstrip("/")
    if not url:
        return ""

    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "AI_BASE_URL must be an HTTPS origin or path without credentials, query, or fragment"
        )
    return url


def _validate_ai_configuration(base_url: str, api_key: str, model: str) -> None:
    configured = (bool(base_url), bool(api_key), bool(model))
    if any(configured) and not all(configured):
        raise ValueError(
            "AI_BASE_URL, AI_API_KEY, and AI_MODEL must be configured together"
        )


def load_settings(environ: Mapping[str, str] | None = None) -> BotSettings:
    source = environ if environ is not None else os.environ
    report_timeout = _positive_float(
        source, "ROOM_REPORT_TIMEOUT_SECONDS", "5"
    )
    ai_base_url = _validate_ai_base_url(source.get("AI_BASE_URL", ""))
    ai_api_key = source.get("AI_API_KEY", "").strip()
    ai_model = source.get("AI_MODEL", "").strip()
    ai_persona_prompt = source.get(
        "AI_PERSONA_PROMPT",
        "你是群聊中的游戏助手，请使用简洁、友善的中文回答。",
    ).strip()
    _validate_ai_configuration(ai_base_url, ai_api_key, ai_model)
    if ai_api_key and ai_api_key in ai_persona_prompt:
        raise ValueError("AI_PERSONA_PROMPT must not contain AI_API_KEY")

    return BotSettings(
        allowed_group_ids=parse_group_ids(source.get("QQ_BOT_ALLOWED_GROUPS", "")),
        lobby_url=source.get(
            "PRIVATE_LOBBY_URL", "http://private-lobby:8080/lobby"
        ),
        report_timeout_seconds=report_timeout,
        report_timezone=_timezone(
            source, "ROOM_REPORT_TIMEZONE", "Asia/Shanghai"
        ),
        ai_base_url=ai_base_url,
        ai_api_key=ai_api_key,
        ai_model=ai_model,
        ai_web_search_enabled=_boolean(
            source, "AI_WEB_SEARCH_ENABLED", "false"
        ),
        ai_persona_prompt=ai_persona_prompt,
        ai_timeout_seconds=_positive_float(source, "AI_TIMEOUT_SECONDS", "20"),
        ai_max_input_chars=_positive_int(source, "AI_MAX_INPUT_CHARS", "1000"),
        ai_max_output_chars=_positive_int(source, "AI_MAX_OUTPUT_CHARS", "2000"),
        ai_max_output_tokens=_positive_int(source, "AI_MAX_OUTPUT_TOKENS", "512"),
        ai_rate_limit_requests=_positive_int(
            source, "AI_RATE_LIMIT_REQUESTS", "5"
        ),
        ai_rate_limit_window_seconds=_positive_float(
            source, "AI_RATE_LIMIT_WINDOW_SECONDS", "60"
        ),
        ai_max_concurrency=_positive_int(source, "AI_MAX_CONCURRENCY", "2"),
        ai_memory_enabled=_boolean(source, "AI_MEMORY_ENABLED", "true"),
        ai_memory_ttl_seconds=_positive_float(
            source, "AI_MEMORY_TTL_SECONDS", "900"
        ),
        ai_memory_max_turns=_positive_int(
            source, "AI_MEMORY_MAX_TURNS", "6"
        ),
        ai_memory_max_chars=_positive_int(
            source, "AI_MEMORY_MAX_CHARS", "8000"
        ),
        ai_memory_max_groups=_positive_int(
            source, "AI_MEMORY_MAX_GROUPS", "256"
        ),
    )


def is_group_allowed(group_id: int, allowed_group_ids: frozenset[int]) -> bool:
    return not allowed_group_ids or group_id in allowed_group_ids