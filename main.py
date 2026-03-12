from datetime import datetime

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


@register(
    "astrbot_plugin_time_aware",
    "sakikosunchaser",
    "为 LLM 注入北京时间上下文，在不破坏原有人格设定的前提下动态微调回复语气。",
    "0.1.0"
)
class TimeAwarePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("timeaware")
    async def timeaware_cmd(self, event: AstrMessageEvent):
        now = self.get_now_in_beijing()
        period = self.get_time_period(now)
        period_zh = self.get_time_period_zh(period)
        style_hint = self.get_style_hint(period)

        text = (
            f"插件：时间感知\n"
            f"北京时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"时间段：{period_zh}（{period}）\n"
            f"风格提示：{style_hint}"
        )
        yield event.plain_result(text)

    def get_now_in_beijing(self):
        if ZoneInfo is None:
            return datetime.now()
        return datetime.now(ZoneInfo("Asia/Shanghai"))

    def get_time_period(self, now):
        total_minutes = now.hour * 60 + now.minute

        if 5 * 60 <= total_minutes <= 8 * 60 + 59:
            return "morning"
        elif 9 * 60 <= total_minutes <= 11 * 60 + 29:
            return "forenoon"
        elif 11 * 60 + 30 <= total_minutes <= 13 * 60 + 59:
            return "noon"
        elif 14 * 60 <= total_minutes <= 17 * 60 + 59:
            return "afternoon"
        elif 18 * 60 <= total_minutes <= 22 * 60 + 59:
            return "evening"
        elif total_minutes >= 23 * 60 or total_minutes <= 1 * 60 + 59:
            return "late_night"
        else:
            return "dawn"

    def get_time_period_zh(self, period):
        return {
            "morning": "清晨",
            "forenoon": "上午",
            "noon": "中午",
            "afternoon": "下午",
            "evening": "晚上",
            "late_night": "深夜",
            "dawn": "凌晨",
        }.get(period, period)

    def get_style_hint(self, period):
        return {
            "morning": "清爽、轻柔、自然开启新一天",
            "forenoon": "正常、明快、自然交流",
            "noon": "轻松、稍微放松、可自然提及吃饭",
            "afternoon": "平稳、自然、不过度兴奋",
            "evening": "放松、陪伴感稍强、温和",
            "late_night": "安静、克制、轻微关心、避免过度活跃",
            "dawn": "很轻、很收敛、偏关心休息状态",
        }.get(period, "自然交流")
