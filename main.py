    def extract_user_message(self, event, req):
        text = getattr(req, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        msg = getattr(event, "message_str", None)
        if isinstance(msg, str) and msg.strip():
            return msg.strip()

        return ""

    def build_time_context_prompt(self, user_message):
        now = self.get_now_in_beijing()
        period = self.get_time_period(now)
        period_zh = self.get_time_period_zh(period)
        style_hint = self.get_style_hint(period)
        emphasize = self.should_emphasize_time(user_message, period)

        suggestions = [
            "你必须优先遵守已有的人格设定，不得因为时间变化而改变角色身份、核心语气、世界观和价值观。",
            "时间只用于轻微调整问候方式、语气氛围、关心表达和回复节奏。",
            "不要每条消息都强行提及时间，只有在自然的时候才体现。",
            "如果用户正在提问任务型、技术型、事实型问题，应优先直接回答问题本身。"
        ]

        if emphasize:
            extra_map = {
                "morning": "可以自然体现早晨或新一天开始的感觉，但不要过度热情。",
                "forenoon": "可以使用自然的白天语气，保持轻松清晰。",
                "noon": "可以轻微体现中午语境，例如自然提及吃饭或午间状态。",
                "afternoon": "可以保持平稳自然的下午语气，不需要刻意强调时间。",
                "evening": "可以略带放松感和陪伴感，但仍要贴合原人格。",
                "late_night": "可以自然流露“这么晚了还没休息”的关心，但不要指责、说教或重复提醒。",
                "dawn": "整体表达应更轻、更安静、更克制，可以温和提醒注意休息。",
            }
            suggestions.append(extra_map.get(period, "保持自然交流。"))
        else:
            suggestions.append("本轮弱化时间感，仅允许在措辞细节中轻微体现时段氛围。")

        lines = [
            "当前时间上下文（北京时间）：",
            f"- 当前本地时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
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
            "时间感知应体现在自然度上，而不是模板化问候复读。"
        ])

        return "\n".join(lines)

    def should_emphasize_time(self, user_message, period):
        if not user_message:
            return True

        text = user_message.strip().lower()

        greeting_keywords = [
            "早", "早安", "早上好", "中午好", "下午好", "晚上好", "晚安",
            "你好", "在吗", "哈喽", "hello", "hi"
        ]
        task_keywords = [
            "报错", "代码", "python", "java", "sql",
            "帮我写", "总结", "翻译", "解释",
            "怎么做", "为什么", "error", "bug", "debug"
        ]

        if any(k in text for k in greeting_keywords):
            return True

        if any(k in text for k in task_keywords):
            return False

        if period in ("late_night", "dawn"):
            return True

        return False
