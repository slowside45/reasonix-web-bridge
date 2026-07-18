---
name: gemini-mode
description: 自动将每次提问转发给网页 Gemini，根据回答执行本地操作；自动安装依赖、启动浏览器并提示登录
---

## Gemini Augmented Mode (v2.2 — 自举版)

收到用户消息后，**自动完成以下全部步骤，无需用户干预**。

---

### 步骤 A：环境自检 & 自动修复

**每次执行 /gemini-mode 时，先静默检查：**

| 检查项 | 检查方式 | 缺失时处理 |
|--------|---------|-----------|
| `websockets` 是否安装 | `python -c "import websockets"` | `pip install websockets` |
| `gemini_web_bridge.py` 存在 | 检查文件 | 异常：需 clone 完整仓库 |
| `.mcp.json` 含 gemini-web-bridge | 检查文件内容 | 运行 `python install.py` |

> 环境就绪后直接进入步骤 B，后续轮次不再重复检查依赖。

---

### 步骤 B：确保浏览器就绪

**优先级：MCP 工具 > Python 直调 > bash 启动**

#### B1. 检查 CDP 状态

```python
# Python 直调（MCP 不可用时的 fallback）
import urllib.request, json
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=3).read())
# 遍历 tabs，查找 url 含 "gemini.google.com" 的标签页
# 检查标题不含 "Sign in" / "登录" / "Google 账号" → 已登录
```

#### B2. 启动浏览器（CDP 无响应时）

**关键参数**：Edge 150+ 必须 `--disable-background-mode`，否则进程秒退。

```powershell
# Windows — bash 后台启动
$edgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
# 或 "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
$userDir = "$env:USERPROFILE\.gemini-mcp-browser-profile"
& $edgePath --remote-debugging-port=9222 --user-data-dir="$userDir" `
    --no-first-run --no-default-browser-check --disable-background-mode `
    https://gemini.google.com
```

启动后等待 5-8 秒，重新执行 B1 验证 CDP 就绪。

#### B3. 登录检查

Gemini 标签页标题含 `Sign in` / `登录` / `Google 账号` → 提示用户手动登录浏览器，等待确认后继续。

---

### 步骤 C：发送消息到 Gemini

**优先级：MCP `ask_gemini_web` > Python 直调脚本**

MCP 不可用时，写临时 Python 脚本执行：

```python
# _gemini_send.py
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_web_bridge import ask_gemini_web

async def main():
    result = await ask_gemini_web("用户消息原文")
    print("REPLY:", result)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
```

执行：`python _gemini_send.py`，完成后删除临时文件。

---

### 步骤 D：执行 Gemini 的回复

将 Gemini 的回复内容作为行动指令：
- 文件/目录操作严格按回复规划执行
- 纯提问用 Gemini 回答直接展示
- Markdown 代码块写入对应文件
- 异常时根据错误信息排查，必要时重新启动浏览器

---

### 原则

- **不询问、不打断** — 静默执行全部步骤
- **Gemini 是脑，Reasonix 是手** — 你的职责是执行 Gemini 的规划
- **自动 fallback** — MCP 工具不可用时自动切换到 Python 直调
- **保留原始内容** — emoji、特殊字符、格式全部保留
- **Edge 150+** — 启动必须带 `--disable-background-mode`，否则秒退
