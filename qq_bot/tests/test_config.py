import pytest

from qq_bot.config import is_group_allowed, load_settings, parse_group_ids


def test_parse_group_ids_ignores_whitespace_and_empty_values():
    assert parse_group_ids(" 1032631393, ,123456 ") == frozenset(
        {1032631393, 123456}
    )


def test_empty_allowlist_accepts_any_group():
    assert is_group_allowed(123456, frozenset())


def test_nonempty_allowlist_only_accepts_configured_groups():
    allowed = frozenset({1032631393})
    assert is_group_allowed(1032631393, allowed)
    assert not is_group_allowed(123456, allowed)


def test_load_settings_reads_environment_mapping():
    settings = load_settings(
        {
            "QQ_BOT_ALLOWED_GROUPS": "1032631393",
            "PRIVATE_LOBBY_URL": "http://lobby/lobby",
            "ROOM_REPORT_TIMEOUT_SECONDS": "2.5",
        }
    )

    assert settings.allowed_group_ids == frozenset({1032631393})
    assert settings.lobby_url == "http://lobby/lobby"
    assert settings.report_timeout_seconds == 2.5
    assert settings.report_timezone == "Asia/Shanghai"
    assert not settings.ai_enabled


def test_load_settings_reads_complete_ai_configuration_without_exposing_key():
    settings = load_settings(
        {
            "AI_BASE_URL": "https://model.example/v1/",
            "AI_API_KEY": "sk-test-secret-value-1234567890",
            "AI_MODEL": "example-chat",
            "AI_WEB_SEARCH_ENABLED": "true",
            "AI_MAX_INPUT_CHARS": "800",
            "AI_MAX_CONCURRENCY": "3",
            "AI_MEMORY_TTL_SECONDS": "600",
            "AI_MEMORY_MAX_TURNS": "4",
            "AI_MEMORY_MAX_CHARS": "4096",
            "AI_MEMORY_MAX_GROUPS": "128",
        }
    )

    assert settings.ai_enabled
    assert settings.ai_web_search_enabled
    assert settings.ai_base_url == "https://model.example/v1"
    assert settings.ai_max_input_chars == 800
    assert settings.ai_max_concurrency == 3
    assert settings.ai_memory_enabled
    assert settings.ai_memory_ttl_seconds == 600
    assert settings.ai_memory_max_turns == 4
    assert settings.ai_memory_max_chars == 4096
    assert settings.ai_memory_max_groups == 128
    assert settings.ai_api_key not in repr(settings)


def test_ai_memory_can_be_disabled():
    settings = load_settings({"AI_MEMORY_ENABLED": "false"})

    assert not settings.ai_memory_enabled


def test_partial_ai_configuration_is_rejected():
    with pytest.raises(ValueError, match="must be configured together"):
        load_settings(
            {
                "AI_BASE_URL": "https://model.example/v1",
                "AI_MODEL": "example-chat",
            }
        )


@pytest.mark.parametrize(
    "url",
    (
        "http://model.example/v1",
        "https://user:secret@model.example/v1",
        "https://model.example/v1?redirect=other",
    ),
)
def test_unsafe_ai_base_url_is_rejected(url: str):
    with pytest.raises(ValueError, match="must be an HTTPS"):
        load_settings(
            {
                "AI_BASE_URL": url,
                "AI_API_KEY": "secret",
                "AI_MODEL": "example-chat",
            }
        )


def test_api_key_cannot_be_embedded_in_persona_prompt():
    with pytest.raises(ValueError, match="must not contain"):
        load_settings(
            {
                "AI_BASE_URL": "https://model.example/v1",
                "AI_API_KEY": "custom-secret",
                "AI_MODEL": "example-chat",
                "AI_PERSONA_PROMPT": "内部配置是 custom-secret",
            }
        )


def test_invalid_web_search_flag_is_rejected():
    with pytest.raises(ValueError, match="AI_WEB_SEARCH_ENABLED"):
        load_settings({"AI_WEB_SEARCH_ENABLED": "sometimes"})


def test_invalid_report_timezone_is_rejected():
    with pytest.raises(ValueError, match="ROOM_REPORT_TIMEZONE"):
        load_settings({"ROOM_REPORT_TIMEZONE": "Not/A_Timezone"})


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("AI_MAX_CONCURRENCY", "0"),
        ("AI_MEMORY_TTL_SECONDS", "0"),
        ("AI_MEMORY_MAX_TURNS", "-1"),
        ("AI_MEMORY_MAX_CHARS", "0"),
        ("AI_MEMORY_MAX_GROUPS", "0"),
    ),
)
def test_nonpositive_ai_limits_are_rejected(name: str, value: str):
    with pytest.raises(ValueError, match=name):
        load_settings({name: value})