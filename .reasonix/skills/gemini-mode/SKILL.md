---
name: gemini-mode
description: 自动将每次提问转发给网页 Gemini，根据回答执行本地操作；自动安装依赖、启动浏览器并提示登录
---

## Gemini Augmented Mode (v3.11 最终版)

收到用户消息后，**自动完成以下全部步骤，无需用户干预**。

---

### 步骤 A：环境自检 & 自动修复

首次使用自动执行 `python install.py`，安装：
- `pip install websockets pyautogui pyperclip`
- 生成 `.mcp.json`
- 安装 Skill

后续轮次跳过。

---

### 步骤 B：确保浏览器就绪

1. 检查 CDP `http://127.0.0.1:9222/json`
2. 无响应 → 启动 Edge（`--disable-background-mode`）：
   ```powershell
   & "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir="$env:USERPROFILE\.gemini-mcp-browser-profile" --no-first-run --no-default-browser-check --disable-background-mode https://gemini.google.com
   ```
3. 标题含 `Sign in`/`登录` → 提示用户登录

---

### 步骤 C：发送消息

```python
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_web_bridge import ask_gemini_web

async def main():
    result = await ask_gemini_web("用户消息", image_path="图片路径(可选)")
    print("REPLY:", result)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
```

---

### 步骤 D：执行回复

严格按 Gemini 回复执行文件/目录操作，Markdown 代码块写入文件。

---

### 图片上传流程

1. `ShowWindow(SW_RESTORE)` + `SetForegroundWindow` 激活 Edge
2. `Clipboard.Clear()` + `SetImage()` 复制图片 + `ContainsImage()` 验证
3. pyautogui `hotkey('ctrl','v')` 粘贴
4. 等 3s → 注入文字 → 轮询 `button[aria-label="Send message"]` 等 enabled
5. 点击发送

---

### 回复检测参数（冻结）

阈值 `>0` | 去重 `__KNOWN_TEXTS` Set | 5s预热+10次稳定 | 90s超时 | 不依赖count

---

### 原则

- Gemini 是脑，Reasonix 是手
- 自动 fallback：MCP 不可用 → Python 直调
- Edge 150+ 必须 `--disable-background-mode`
