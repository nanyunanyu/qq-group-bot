import nonebot
from nonebot.adapters.onebot.v11 import Adapter


def bootstrap() -> None:
    nonebot.init()
    nonebot.get_driver().register_adapter(Adapter)
    nonebot.load_plugin("qq_bot.plugins.room")
    nonebot.load_plugin("qq_bot.plugins.ai")


def main() -> None:
    bootstrap()
    nonebot.run()