from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register


@register(
    "astrbot_plugin_time_aware",
    "sakikosunchaser",
    "时间感知插件",
    "0.1.0"
)
class TimeAwarePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("timeaware")
    async def timeaware_cmd(self, event: AstrMessageEvent):
        yield event.plain_result("时间感知插件已加载")
