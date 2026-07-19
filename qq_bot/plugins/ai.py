from __future__ import annotations

from datetime import datetime
from time import monotonic
from zoneinfo import ZoneInfo

from nonebot import logger, on_message
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment
from nonebot.rule import Rule

from qq_bot.config import is_group_allowed, load_settings
from qq_bot.security import (
    AiBusy,
    AiConcurrencyLimiter,
    AiInputRejected,
    AiOutputRejected,
    SlidingWindowRateLimiter,
    normalize_user_input,
    sanitize_model_output,
)
from qq_bot.services.ai_chat import AiServiceUnavailable, request_ai_response
from qq_bot.services.conversation_memory import (
    GroupConversationMemory,
    render_conversation_context,
)
from qq_bot.services.room_status import (
    RoomReportUnavailable,
    load_ai_room_context,
    needs_room_context,
)

settings = load_settings()
rate_limiter = SlidingWindowRateLimiter(
    max_requests=settings.ai_rate_limit_requests,
    window_seconds=settings.ai_rate_limit_window_seconds,
)
concurrency_limiter = AiConcurrencyLimiter(settings.ai_max_concurrency)
conversation_memory = GroupConversationMemory(
    ttl_seconds=settings.ai_memory_ttl_seconds,
    max_turns=settings.ai_memory_max_turns,
    max_chars=settings.ai_memory_max_chars,
    max_groups=settings.ai_memory_max_groups,
)


async def request_sanitized_answer(
    question: str,
    *,
    conversation_context: str | None = None,
) -> str:
    async with concurrency_limiter.slot():
        room_context = None
        if needs_room_context(question):
            room_context = await load_ai_room_context(settings)
        raw_answer = await request_ai_response(
            settings,
            question,
            room_context=room_context,
            conversation_context=conversation_context,
        )
    return sanitize_model_output(
        raw_answer,
        max_chars=settings.ai_max_output_chars,
        forbidden_values=(settings.ai_api_key,),
    )


async def request_group_answer(group_id: int, question: str) -> str:
    if not settings.ai_memory_enabled:
        return await request_sanitized_answer(question)

    async with conversation_memory.session(group_id) as session:
        answer = await request_sanitized_answer(
            question,
            conversation_context=render_conversation_context(session.history),
        )
        session.remember(question, answer)
        return answer


def allowed_group_mention(event: Event) -> bool:
    return (
        isinstance(event, GroupMessageEvent)
        and event.to_me
        and is_group_allowed(event.group_id, settings.allowed_group_ids)
    )


def format_timed_answer(
    answer: str,
    *,
    elapsed_seconds: float,
    answered_at: datetime,
) -> str:
    timing = (
        f"响应时间：{max(0.0, elapsed_seconds):.2f} 秒 | "
        f"回答时间：{answered_at:%Y-%m-%d %H:%M:%S}"
    )
    return f"{answer}\n\n{timing}"


if settings.ai_enabled:
    ai_message = on_message(
        rule=Rule(allowed_group_mention),
        priority=20,
        block=True,
    )

    @ai_message.handle()
    async def handle_ai_message(event: GroupMessageEvent) -> None:
        try:
            question = normalize_user_input(
                event.get_plaintext(),
                max_chars=settings.ai_max_input_chars,
                forbidden_values=(settings.ai_api_key,),
            )
        except AiInputRejected as error:
            responses = {
                "empty input": "请在 @机器人 后输入问题。",
                "input too long": "问题过长，请缩短后重试。",
                "input appears to contain a secret": (
                    "消息疑似包含密钥或令牌，为保护隐私未发送给模型。"
                ),
            }
            await ai_message.finish(
                responses.get(str(error), "该问题无法发送给模型。")
            )

        rate_key = (event.group_id, event.user_id)
        if not await rate_limiter.allow(rate_key):
            await ai_message.finish("请求过于频繁，请稍后再试。")

        started_at = monotonic()
        try:
            answer = await request_group_answer(event.group_id, question)
        except AiBusy:
            await ai_message.finish("当前请求较多，请稍后再试。")
        except RoomReportUnavailable:
            logger.warning("AI room context is temporarily unavailable")
            await ai_message.finish("房间状态暂时无法获取，请稍后重试。")
        except AiOutputRejected:
            logger.warning("AI response was blocked by the output guard")
            await ai_message.finish("模型回复可能包含敏感信息，已停止发送。")
        except AiServiceUnavailable:
            logger.warning("AI request failed")
            await ai_message.finish("AI 服务暂时不可用，请稍后重试。")

        answer = format_timed_answer(
            answer,
            elapsed_seconds=monotonic() - started_at,
            answered_at=datetime.now(ZoneInfo(settings.report_timezone)),
        )
        await ai_message.finish(MessageSegment.text(answer))
else:
    logger.info("AI plugin is disabled because no model is configured")