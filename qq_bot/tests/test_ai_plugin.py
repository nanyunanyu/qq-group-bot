import asyncio
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import nonebot
import pytest
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
from nonebot.adapters.onebot.v11.event import Sender

nonebot.init()

from qq_bot.plugins import ai as ai_plugin
from qq_bot.services.ai_chat import AiServiceUnavailable
from qq_bot.services.conversation_memory import GroupConversationMemory


def group_event(*, group_id: int, to_me: bool) -> GroupMessageEvent:
    message = Message("你好")
    return GroupMessageEvent(
        time=0,
        self_id=10000,
        post_type="message",
        sub_type="normal",
        user_id=20000,
        message_type="group",
        message_id=1,
        message=message,
        original_message=message,
        raw_message="你好",
        font=0,
        sender=Sender(user_id=20000),
        to_me=to_me,
        group_id=group_id,
    )


def test_ai_rule_requires_mention_and_allowed_group(monkeypatch):
    monkeypatch.setattr(
        ai_plugin,
        "settings",
        replace(ai_plugin.settings, allowed_group_ids=frozenset({100})),
    )

    assert ai_plugin.allowed_group_mention(group_event(group_id=100, to_me=True))
    assert not ai_plugin.allowed_group_mention(
        group_event(group_id=100, to_me=False)
    )
    assert not ai_plugin.allowed_group_mention(
        group_event(group_id=200, to_me=True)
    )


def test_format_timed_answer_appends_elapsed_and_answered_time():
    answered_at = datetime(
        2026,
        7,
        18,
        17,
        30,
        45,
        tzinfo=ZoneInfo("Asia/Shanghai"),
    )

    result = ai_plugin.format_timed_answer(
        "这是模型回答。",
        elapsed_seconds=1.236,
        answered_at=answered_at,
    )

    assert result == (
        "这是模型回答。\n\n"
        "响应时间：1.24 秒 | 回答时间：2026-07-18 17:30:45"
    )


def test_format_timed_answer_never_displays_negative_elapsed_time():
    answered_at = datetime(2026, 7, 18, tzinfo=ZoneInfo("Asia/Shanghai"))

    result = ai_plugin.format_timed_answer(
        "回答",
        elapsed_seconds=-0.1,
        answered_at=answered_at,
    )

    assert "响应时间：0.00 秒" in result


def test_request_group_answer_includes_only_its_own_group_history(monkeypatch):
    monkeypatch.setattr(
        ai_plugin,
        "settings",
        replace(ai_plugin.settings, ai_memory_enabled=True),
    )
    monkeypatch.setattr(
        ai_plugin,
        "conversation_memory",
        GroupConversationMemory(
            ttl_seconds=900,
            max_turns=6,
            max_chars=1000,
            max_groups=16,
        ),
    )
    contexts = []

    async def fake_request(
        question: str,
        *,
        conversation_context: str | None = None,
    ) -> str:
        contexts.append(conversation_context)
        return f"回答：{question}"

    monkeypatch.setattr(ai_plugin, "request_sanitized_answer", fake_request)

    async def scenario():
        first_answer = await ai_plugin.request_group_answer(1, "第一问")
        second_answer = await ai_plugin.request_group_answer(1, "第二问")
        other_group_answer = await ai_plugin.request_group_answer(2, "另一群问题")
        return first_answer, second_answer, other_group_answer

    assert asyncio.run(scenario()) == (
        "回答：第一问",
        "回答：第二问",
        "回答：另一群问题",
    )
    assert contexts[0] is None
    assert contexts[1] is not None
    assert "群成员：第一问" in contexts[1]
    assert "机器人：回答：第一问" in contexts[1]
    assert contexts[2] is None


def test_failed_group_answer_is_not_added_to_memory(monkeypatch):
    monkeypatch.setattr(
        ai_plugin,
        "settings",
        replace(ai_plugin.settings, ai_memory_enabled=True),
    )
    monkeypatch.setattr(
        ai_plugin,
        "conversation_memory",
        GroupConversationMemory(
            ttl_seconds=900,
            max_turns=6,
            max_chars=1000,
            max_groups=16,
        ),
    )

    async def failing_request(
        question: str,
        *,
        conversation_context: str | None = None,
    ) -> str:
        raise AiServiceUnavailable("unavailable")

    monkeypatch.setattr(ai_plugin, "request_sanitized_answer", failing_request)

    with pytest.raises(AiServiceUnavailable, match="unavailable"):
        asyncio.run(ai_plugin.request_group_answer(1, "失败的问题"))

    contexts = []

    async def successful_request(
        question: str,
        *,
        conversation_context: str | None = None,
    ) -> str:
        contexts.append(conversation_context)
        return "成功回答"

    monkeypatch.setattr(ai_plugin, "request_sanitized_answer", successful_request)

    assert asyncio.run(ai_plugin.request_group_answer(1, "新问题")) == "成功回答"
    assert contexts == [None]
