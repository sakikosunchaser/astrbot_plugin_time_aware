from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


class TimeAwarePlugin:
    """
    AstrBot 时间感知插件

    功能：
    1. 在 on_llm_request 阶段自动注入北京时间上下文
    2. 保持“人格优先，时间次之，任务优先”
    3. 提供简单命令用于调试当前时间感知 prompt
    """

    def __init__(self, context: Any = None):
        self.context = context
        self.plugin_name = "astrbot_plugin_time_aware"
        self.display_name = "时间感知"
        self.base_dir = Path(__file__).resolve().parent

        self.default_config = {
            "enabled": True,
            "timezone": "Asia/Shanghai",
            "strict_persona_preservation": True,
            "task_mode_suppress_time_hint": True,
            "debug_log": False,
            "apply_in_private": True,
            "apply_in_group": True,
            "enabled_groups": [],
            "disabled_groups": [],
            "enabled_users": [],
            "disabled_users": [],
            "merge_separator": (
                "---\n"
                "以下为运行时动态上下文，请在不覆盖上述人格设定的前提下参考："
            ),
            "time_ranges": {
                "morning": ["05:00", "08:59"],
                "forenoon": ["09:00", "11:29"],
                "noon": ["11:30", "13:59"],
                "afternoon": ["14:00", "17:59"],
                "evening": ["18:00", "22:59"],
                "late_night": ["23:00", "01:59"],
                "dawn": ["02:00", "04:59"],
            },
        }

        self.config = self.load_config()

        if self.config.get("debug_log", False):
            print(f"[{self.plugin_name}] loaded config: {self.config}")

    # =========================
    # 配置
    # =========================

    def load_config(self) -> dict:
        """
        从插件目录读取 config.json。
        若不存在则使用默认配置。
        """
        config_path = self.base_dir / "config.json"
        if not config_path.exists():
            return dict(self.default_config)

        try:
            with config_path.open("r", encoding="utf-8") as f:
                user_config = json.load(f)
        except Exception as e:
            print(f"[{self.plugin_name}] failed to load config.json: {e}")
            return dict(self.default_config)

        merged = dict(self.default_config)
        for k, v in user_config.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                temp = dict(merged[k])
                temp.update(v)
                merged[k] = temp
            else:
                merged[k] = v
        return merged

    # =========================
    # 调试命令
    # =========================

    @filter.command("timeaware")
    async def timeaware_cmd(self, event: AstrMessageEvent):
        """
        调试命令：
        /timeaware
        /timeaware prompt
        """
        message = (getattr(event, "message_str", "") or "").strip()
        user_text = self.extract_command_tail(message)

        if user_text.lower() == "prompt":
            prompt = self.build_time_context_prompt(user_message="")
            yield event.plain_result(prompt)
            return

        summary = self.render_debug_summary("")
        yield event.plain_result(summary)

    @filter.command("时间感知")
    async def timeaware_cmd_zh(self, event: AstrMessageEvent):
        message = (getattr(event, "message_str", "") or "").strip()
        user_text = self.extract_command_tail(message)

        if user_text.lower() == "prompt" or user_text == "提示词":
            prompt = self.build_time_context_prompt(user_message="")
            yield event.plain_result(prompt)
            return

        summary = self.render_debug_summary("")
        yield event.plain_result(summary)

    # =========================
    # LLM 请求注入
    # =========================

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """
        在调用 LLM 前自动注入时间感知 prompt。
        官方插件文档说明可在这里修改 ProviderRequest。([docs.astrbot.app](https://docs.astrbot.app/dev/star/plugin.html?utm_source=openai))
        """
        if not self.config.get("enabled", True):
            return

        if not self.should_apply_to_event(event):
            return

        user_message = self._extract_user_message(event, req)
        time_prompt = self.build_time_context_prompt(user_message=user_message)

        original_system_prompt = getattr(req, "system_prompt", "") or ""
        req.system_prompt = self.merge_system_prompt(original_system_prompt, time_prompt)

        if self.config.get("debug_log", False):
            print(f"[{self.plugin_name}] on_llm_request triggered")
            print(f"[{self.plugin_name}] user_message={user_message!r}")
            print(f"[{self.plugin_name}] injected_prompt=\n{time_prompt}")

    # =========================
    # 生效范围判断
    # =========================

    def should_apply_to_event(self, event: AstrMessageEvent) -> bool:
        group_id = getattr(event, "group_id", None)
        user_id = getattr(event, "user_id", None)

        enabled_groups = {str(x) for x in self.config.get("enabled_groups", [])}
        disabled_groups = {str(x) for x in self.config.get("disabled_groups", [])}
        enabled_users = {str(x) for x in self.config.get("enabled_users", [])}
        disabled_users = {str(x) for x in self.config.get("disabled_users", [])}

        is_group = group_id not in (None, "", 0, "0")
        is_private = not is_group

        if is_group and not self.config.get("apply_in_group", True):
            return False
        if is_private and not self.config.get("apply_in_private", True):
            return False

        if group_id is not None:
            sgid = str(group_id)
            if enabled_groups and sgid not in enabled_groups:
                return False
            if sgid in disabled_groups:
                return False

        if user_id is not None:
            suid = str(user_id)
            if enabled_users and suid not in enabled_users:
                return False
            if suid in disabled_users:
                return False

        return True

    # =========================
    # Prompt 拼接
    # =========================

    def merge_system_prompt(self, original_system_prompt: str, time_prompt: str) -> str:
        sep = self.config.get("merge_separator", "").strip()
        if not original_system_prompt.strip():
            return time_prompt

        if sep:
            return (
                original_system_prompt.rstrip()
                + "\n\n"
                + sep
                + "\n\n"
                + time_prompt
            )
        return original_system_prompt.rstrip() + "\n\n" + time_prompt

    # =========================
    # 时间上下文构建
    # =========================

    def build_time_context_prompt(self, user_message: str) -> str:
        now = self.get_now_in_beijing()
        period = self.get_time_period(now)
        period_zh = self.get_time_period_zh(period)
        style_hint = self.get_style_hint(period)
        emphasize = self.should_emphasize_time(user_message=user_message, period=period)
        suggestions = self.get_behavior_suggestions(period=period, emphasize=emphasize)

        lines = [
            "当前时间上下文（北京时间）：",
            f"- 当前本地时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 时区：{self.config.get('timezone', 'Asia/Shanghai')}",
            f"- 当前时间段：{period_zh}（{period}）",
            f"- 风格提示：{style_hint}",
            f"- 是否建议明显体现时间感：{'是' if emphasize else '否'}",
            "",
            "行为约束：",
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

    def get_now_in_beijing(self) -> datetime:
        tz = self.config.get("timezone", "Asia/Shanghai")
        if ZoneInfo is None:
            return datetime.now()
        return datetime.now(ZoneInfo(tz))

    def get_time_period(self, now: datetime) -> str:
        total_minutes = now.hour * 60 + now.minute
        ranges = self.config.get("time_ranges", {})

        for period, pair in ranges.items():
            if not isinstance(pair, list) or len(pair) != 2:
                continue
            start, end = pair
            if self.time_in_range(total_minutes, start, end):
                return period

        return "forenoon"

    def time_in_range(self, current_minutes: int, start_hm: str, end_hm: str) -> bool:
        start = self.hm_to_minutes(start_hm)
        end = self.hm_to_minutes(end_hm)

        if start <= end:
            return start <= current_minutes <= end
        else:
            # 跨天，如 23:00 - 01:59
            return current_minutes >= start or current_minutes <= end

    def hm_to_minutes(self, hm: str) -> int:
        hour, minute = hm.split(":")
        return int(hour) * 60 + int(minute)

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

    def should_emphasize_time(self, user_message: str, period: str) -> bool:
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
            "帮我写", "总结", "翻译", "解释",
            "怎么做", "为什么", "error", "bug", "debug"
        ]

        if any(k in text for k in greeting_keywords):
            return True

        if self.config.get("task_mode_suppress_time_hint", True):
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

    # =========================
    # 工具方法
    # =========================

    def _extract_user_message(self, event: AstrMessageEvent, req: ProviderRequest) -> str:
        text = getattr(req, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        msg = getattr(event, "message_str", None)
        if isinstance(msg, str) and msg.strip():
            return msg.strip()

        return ""

    def extract_command_tail(self, raw_message: str) -> str:
        parts = raw_message.strip().split(maxsplit=1)
        if len(parts) < 2:
            return ""
        return parts[1].strip()

    def render_debug_summary(self, user_message: str) -> str:
        now = self.get_now_in_beijing()
        period = self.get_time_period(now)
        period_zh = self.get_time_period_zh(period)
        style_hint = self.get_style_hint(period)
        emphasize = self.should_emphasize_time(user_message=user_message, period=period)

        return (
            f"插件：{self.display_name}\n"
            f"北京时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"时区：{self.config.get('timezone', 'Asia/Shanghai')}\n"
            f"时间段：{period_zh}（{period}）\n"
            f"风格提示：{style_hint}\n"
            f"是否建议明显体现时间感：{'是' if emphasize else '否'}\n"
        )
