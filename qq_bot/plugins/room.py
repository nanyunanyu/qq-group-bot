from nonebot import logger, on_command
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment
from nonebot.rule import Rule

from qq_bot.config import is_group_allowed, load_settings
from qq_bot.services.room_status import RoomReportUnavailable, load_room_report

settings = load_settings()


def allowed_group(event: Event) -> bool:
    return isinstance(event, GroupMessageEvent) and is_group_allowed(
        event.group_id,
        settings.allowed_group_ids,
    )


room_command = on_command(
    "房间",
    rule=Rule(allowed_group),
    priority=10,
    block=True,
)


@room_command.handle()
async def handle_room_command() -> None:
    try:
        report = await load_room_report(settings)
    except RoomReportUnavailable:
        logger.exception("Failed to load private lobby room report")
        await room_command.finish("房间状态暂时无法获取，请稍后重试。")

    await room_command.finish(MessageSegment.text(report))