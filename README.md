# astrbot_plugin_time_aware

AstrBot 插件：**时间感知**

为 LLM 注入**北京时间上下文**，在**不破坏原有人格设定**的前提下，动态微调回复语气、问候方式和关心表达。

## 功能特点

- 在调用 LLM 前自动注入时间感知 prompt
- 默认使用 `Asia/Shanghai`
- 强调：
  - 人格优先
  - 时间次之
  - 任务优先
- 支持群聊 / 私聊开关
- 支持群、用户白名单 / 黑名单
- 支持调试命令查看当前时间感知状态

## 适用场景

例如：
- 12:00 左右可以自然说“中午好”“记得吃饭”
- 03:00 左右可以轻微体现“这么晚了还没休息”的关心
- 但不会因此偏离你为机器人设定的人格

## 安装方式

将插件仓库克隆到 AstrBot 插件目录，例如：

```bash
cd AstrBot/data/plugins
git clone https://github.com/sakikosunchaser/astrbot_plugin_time_aware.git
```

然后在 AstrBot WebUI 插件管理中重载插件。

## 配置

复制 `config.example.json` 为 `config.json`，按需修改。

建议同时在 AstrBot 主配置中关闭内置日期时间 system prompt，避免重复注入。

## 命令

### 查看当前状态
```text
/timeaware
```

或：

```text
/时间感知
```

### 查看当前注入 prompt
```text
/timeaware prompt
```

或：

```text
/时间感知 prompt
```

## 工作原理

本插件通过 AstrBot 的 `on_llm_request` 钩子，在调用模型前将时间上下文追加到 `req.system_prompt` 中。

注入逻辑遵循：

1. 保留原人格 system prompt
2. 追加运行时时间上下文
3. 明确要求“人格优先，时间只做轻微调制”

## 推荐配置

若你使用 NapCat + aiocqhttp：

- `support_platforms` 选择 `aiocqhttp`
- 时区保持 `Asia/Shanghai`
- 建议关闭 AstrBot 内置 `datetime_system_prompt`

## 许可证

MIT
