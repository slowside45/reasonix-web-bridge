---
name: gemini-mode
description: 自动将每次提问转发给网页 Gemini，根据回答执行本地操作；自动安装依赖、启动浏览器并提示登录
---

## Gemini Augmented Mode (v3.11)

收到用户消息后，**自动完成以下全部步骤，无需用户干预**。

---

### 步骤 A：环境自检 & 自动修复

| 检查项 | 缺失时处理 |
|--------|-----------|
| `websockets` | `pip install websockets` |
| `pyautogui` `pyperclip` | `pip install pyautogui pyperclip` |
| `gemini_web_bridge.py` | clone 完整仓库 |
| `.mcp.json` 含 gemini-web-bridge | `python install.py` |

---

### 步骤 B：确保浏览器就绪

1. 检查 CDP `http://127.0.0.1:9222/json`，找到 `gemini.google.com` 标签页
2. CDP 无响应 → 启动 Edge（**必须** `--disable-background-mode`）：
   ```powershell
   $edgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
   & $edgePath --remote-debugging-port=9222 --user-data-dir="$env:USERPROFILE\.gemini-mcp-browser-profile" --no-first-run --no-default-browser-check --disable-background-mode https://gemini.google.com
   ```
3. 登录检查：标题含 `Sign in` / `登录` → 提示用户

---

### 步骤 C：发送消息到 Gemini

**优先级：MCP `ask_gemini_web` > Python 直调脚本**

```python
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_web_bridge import ask_gemini_web

async def main():
    result = await ask_gemini_web("用户消息原文")  # 有图片时加 image_path=...
    print("REPLY:", result)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
```

---

### 步骤 D：执行 Gemini 的回复

- 文件/目录操作严格按回复规划执行
- 纯提问用 Gemini 回答直接展示
- Markdown 代码块写入对应文件

---

### ⚠️ 回复检测核心逻辑（冻结，禁止修改）

| 参数 | 值 | 说明 |
|------|:--:|------|
| 文本阈值 | `>0` | 不过滤任何长度 |
| 去重 | `__KNOWN_TEXTS` Set | 发送前快照所有消息前80字符 |
| Observer | MutationObserver 简化版 | childList+subtree+characterData |
| 稳定性 | 5s预热 + 连续10次不变 | 防止流式截断 |
| 超时 | 90s | |
| count依赖 | 无 | paste 后 DOM 重建不可靠 |

---

### 🖼 图片上传方案

1. `SetForegroundWindow` 激活 Edge 窗口（支持最小化恢复）
2. `Clipboard.Clear()` + `SetImage()` 复制图片数据 + `ContainsImage()` 验证
3. pyautogui `hotkey('ctrl','v')` 物理粘贴
4. 光标移到末尾 → `Input.insertText` 追加文字（不清除预览）
5. 轮询 `button[aria-label="Send message"]` 等 disabled=false
6. 点击发送 → 回复检测

---

### 原则

- Gemini 是脑，Reasonix 是手
- 自动 fallback：MCP 不可用 → Python 直调
- Edge 150+ 必须 `--disable-background-mode`
- **回复检测参数已冻结**
