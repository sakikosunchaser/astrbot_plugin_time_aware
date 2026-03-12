from __future__ import annotations

from datetime import datetime

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest
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
        self.plugin_name = "astrbot_plugin_time_aware"
        self.timezone_name = "Asia/Shanghai"
        self.debug_log = True

    # =========================
    # 调试命令
    # =========================

    @filter.command("timeaware")
    async def timeaware_cmd(self, event: AstrMessageEvent):
        """
        /timeaware
        显示当前北京时间、时段和风格提示
        """
        now = self.get_now_in_beijing()
        period = self.get_time_period(now)
        period_zh = self.get_time_period_zh(period)
        style_hint = self.get_style_hint(period)

        text = (
            f"插件：时间感知\n"
            f"北京时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"时区：{self.timezone_name}\n"
            f"时间段：{period_zh}（{period}）\n"
            f"风格提示：{style_hint}"
        )
        yield event.plain_result(text)

    @filter.command("时间感知")
    async def timeaware_cmd_zh(self, event: AstrMessageEvent):
        """
        /时间感知
        中文别名
        """
        now = self.get_now_in_beijing()
        period = self.get_time_period(now)
        period_zh = self.get_time_period_zh(period)
        style_hint = self.get_style_hint(period)

        text = (
            f"插件：时间感知\n"
            f"北京时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"时区：{self.timezone_name}\n"
            f"时间段：{period_zh}（{period}）\n"
            f"风格提示：{style_hint}"
        )
        yield event.plain_result(text)

    @filter.command("timeaware_prompt")
    async def timeaware_prompt_cmd(self, event: AstrMessageEvent):
        """
        /timeaware_prompt
        查看当前将注入给 LLM 的 prompt
        """
        prompt = self.build_time_context_prompt("")
        yield event.plain_result(prompt)

    # =========================
    # LLM 请求前注入时间上下文
    # =========================

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """
        在进入 LLM 前向 system_prompt 追加时间感知信息。
        """
        user_message = self.extract_user_message(event, req)
        time_prompt = self.build_time_context_prompt(user_message)

        original_system_prompt = getattr(req, "system_prompt", "") or ""

        if original_system_prompt.strip():
            req.system_prompt = (
                original_system_prompt.rstrip()
                + "\n\n---\n"
                + "以下为运行时动态上下文，请在不覆盖上述人格设定的前提下参考：\n\n"
                + time_prompt
            )
        else:
            req.system_prompt = time_prompt

        if self.debug_log:
            print(f"[{self.plugin_name}] on_llm_request triggered")
            print(f"[{self.plugin_name}] user_message = {user_message!r}")
            print(f"[{self.plugin_name}] injected prompt:\n{time_prompt}")

    # =========================
    # 消息提取
    # =========================

    def extract_user_message(self, event, req) -> str:
        """
        尽量从 req 或 event 中提取用户原始消息。
        """
        text = getattr(req, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        msg = getattr(event, "message_str", None)
        if isinstance(msg, str) and msg.strip():
            return msg.strip()

        return ""

    # =========================
    # 时间处理
    # =========================

    def get_now_in_beijing(self) -> datetime:
        if ZoneInfo is None:
            return datetime.now()
        return datetime.now(ZoneInfo(self.timezone_name))

    def get_time_period(self, now: datetime) -> str:
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

    def get_time_period_zh(self, period: str) -> str:
        return {
            "morning": "清晨",
            "forenoon": "上午",
            "noon": "中午",
            "afternoon": "下午",
            "evening": "晚上",
            "late_night": "深夜",
            "dawn": "凌晨",
        }.get(period, period)

    def get_style_hint(self, period: str) -> str:
        return {
            "morning": "清爽、轻柔、自然开启新一天",
            "forenoon": "正常、明快、自然交流",
            "noon": "轻松、稍微放松、可自然提及吃饭",
            "afternoon": "平稳、自然、不过度兴奋",
            "evening": "放松、陪伴感稍强、温和",
            "late_night": "安静、克制、轻微关心、避免过度活跃",
            "dawn": "很轻、很收敛、偏关心休息状态",
        }.get(period, "自然交流")

    # =========================
    # 时间感知策略
    # =========================

    def should_emphasize_time(self, user_message: str, period: str) -> bool:
        """
        是否建议本轮更明显体现时间感。
        - 打招呼时：是
        - 深夜/凌晨：是
        - 技术/任务型问题：否
        """
        if not user_message:
            return True

        text = user_message.strip().lower()

        greeting_keywords = [
            "早", "早安", "早上好",
            "中午好", "下午好",
            "晚上好", "晚安",
            "你好", "在吗", "哈喽",
            "hello", "hi"
        ]

        task_keywords = [
            "报错", "代码", "python", "java", "sql",
            "帮我写", "写个", "总结", "翻译", "解释",
            "怎么做", "为什么", "error", "bug", "debug",
            "函数", "脚本", "接口", "日志", "部署"
        ]

        if any(k in text for k in greeting_keywords):
            return True

        if any(k in text for k in task_keywords):
            return False

        if period in ("late_night", "dawn"):
            return True

        return False

    def get_behavior_suggestions(self, period: str, emphasize: bool) -> list[str]:
        base = [
            "你必须优先遵守已有的人格设定，不得因为时间变化而改变角色身份、核心语气、世界观和价值观。",
            "时间只用于轻微调整问候方式、语气氛围、关心表达和回复节奏。",
            "不要每条消息都强行提及时间，只有在自然的时候才体现。",
            "如果用户正在提问任务型、技术型、事实型问题，应优先直接回答问题本身。",
        ]

        if not emphasize:
            base.append("本轮弱化时间感，仅允许在措辞细节中轻微体现时段氛围。")
            return base

        extra_map = {
            "morning": "可以自然体现早晨或新一天开始的感觉，但不要过度热情。",
            "forenoon": "可以使用自然的白天语气，保持轻松清晰。",
            "noon": "可以轻微体现中午语境，例如自然提及吃饭或午间状态。",
            "afternoon": "可以保持平稳自然的下午语气，不需要刻意强调时间。",
            "evening": "可以略带放松感和陪伴感，但仍要贴合原人格。",
            "late_night": "可以自然流露“这么晚了还没休息”的关心，但不要指责、说教或重复提醒。",
            "dawn": "整体表达应更轻、更安静、更克制，可以温和提醒注意休息。",
        }

        base.append(extra_map.get(period, "保持自然交流。"))
        return base

    def build_time_context_prompt(self, user_message: str) -> str:
        now = self.get_now_in_beijing()
        period = self.get_time_period(now)
        period_zh = self.get_time_period_zh(period)
        style_hint = self.get_style_hint(period)
        emphasize = self.should_emphasize_time(user_message, period)
        suggestions = self.get_behavior_suggestions(period, emphasize)

        lines = [
            "当前时间上下文（北京时间）：",
            f"- 当前本地时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 时区：{self.timezone_name}",
            f"- 当前时间段：{period_zh}（{period}）",
            f"- 风格提示：{style_hint}",
            f"- 是否建议明显体现时间感：{'是' if emphasize else '否'}",
            "",
            "行为约束："
        ]

        for i, item in enumerate(suggestions, start=1):
            lines.append(f"{i}. {item}")

        lines.extend([
            "",
            "补充要求：",
            "你可以结合当前时段微调表达，但不得覆盖、篡改或弱化原有人格设定。",
            "如果用户消息本身是任务、问答、技术求助或信息检索，则优先完成任务。",
            "时间感知应体现在自然度上，而不是模板化问候复读。",
        ])

        return "\n".join(lines)
