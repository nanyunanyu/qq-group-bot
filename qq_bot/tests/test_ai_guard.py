import asyncio

import pytest

from qq_bot.security.ai_guard import (
    AiBusy,
    AiConcurrencyLimiter,
    AiInputRejected,
    AiOutputRejected,
    SlidingWindowRateLimiter,
    normalize_user_input,
    sanitize_model_output,
)


def test_user_input_is_normalized_and_limited():
    assert normalize_user_input("  你好\x00\n ", max_chars=10) == "你好"

    with pytest.raises(AiInputRejected, match="empty input"):
        normalize_user_input(" \x00 ", max_chars=10)
    with pytest.raises(AiInputRejected, match="input too long"):
        normalize_user_input("12345", max_chars=4)


def test_secrets_are_blocked_in_both_directions():
    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"

    with pytest.raises(AiInputRejected, match="contain a secret"):
        normalize_user_input(f"帮我检查 {secret}", max_chars=100)
    with pytest.raises(AiOutputRejected, match="contain a secret"):
        sanitize_model_output(f"服务密钥是 {secret}", max_chars=100)
    with pytest.raises(AiOutputRejected, match="contain a secret"):
        sanitize_model_output(
            "模型回显了 custom-secret",
            max_chars=100,
            forbidden_values=("custom-secret",),
        )


def test_model_output_is_plain_text_and_truncated():
    raw = "[CQ:image,file=https://example.invalid/a.png]abcdef"
    assert sanitize_model_output(raw, max_chars=20) == raw[:20] + "…"


def test_rate_limiter_is_scoped_by_key_and_recovers_after_window():
    now = [100.0]
    limiter = SlidingWindowRateLimiter(
        max_requests=2,
        window_seconds=10,
        clock=lambda: now[0],
    )

    async def scenario():
        assert await limiter.allow((1, 1))
        assert await limiter.allow((1, 1))
        assert not await limiter.allow((1, 1))
        assert await limiter.allow((1, 2))
        now[0] = 111.0
        assert await limiter.allow((1, 1))

    asyncio.run(scenario())


def test_concurrency_limiter_rejects_excess_work_without_queueing():
    limiter = AiConcurrencyLimiter(1)

    async def scenario():
        async with limiter.slot():
            with pytest.raises(AiBusy):
                async with limiter.slot():
                    pass
        async with limiter.slot():
            pass

    asyncio.run(scenario())