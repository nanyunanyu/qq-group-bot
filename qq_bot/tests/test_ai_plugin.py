from dataclasses import replace

import nonebot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
from nonebot.adapters.onebot.v11.event import Sender

nonebot.init()

from qq_bot.plugins import ai as ai_plugin


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