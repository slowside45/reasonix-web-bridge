---
name: gemini-mode
description: 自动将每次提问转发给网页 Gemini，根据回答执行本地操作；自动安装依赖、启动浏览器并提示登录
---

## Gemini Augmented Mode (v3.1 — 冻结版)

收到用户消息后，**自动完成以下全部步骤，无需用户干预**。

---

### 步骤 A：环境自检 & 自动修复

| 检查项 | 缺失时处理 |
|--------|-----------|
| `websockets` | `pip install websockets` |
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

MCP 不可用时，Python 直调：

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

### ⚠️ 回复检测核心逻辑（冻结，禁止修改）

```
1. MutationObserver 注入 document.body（childList+subtree+characterData）
   - 每次 DOM 变化扫描全部 message-content，取最后一条 innerText
   - 缓存到 window.__GEMINI_LAST_RESP
   - 阈值 >0 （不过滤任何长度）

2. 发送前：
   - 清空 __GEMINI_LAST_RESP = ''
   - 快照 __KNOWN_TEXTS = Set(所有现有 message-content 前80字符)

3. js_get 轮询：
   - 优先读 __GEMINI_LAST_RESP → 不在 __KNOWN_TEXTS 中则返回
   - 兜底扫描 message-content → 跳过 __KNOWN_TEXTS 中的文本
   - 阈值 >0
   - 90s 超时
   - 不依赖 count（paste 后 DOM 重建导致计数不可靠）

4. 图片上传：
   - Runtime.evaluate(returnByValue=false) 创建 input → 获取 objectId
   - DOM.setFileInputFiles(objectId=...) 注入文件
   - DataTransfer + ClipboardEvent('paste') 触发上传
```

---

### 原则

- Gemini 是脑，Reasonix 是手
- 自动 fallback：MCP 不可用 → Python 直调
- Edge 150+ 必须 `--disable-background-mode`
- **回复检测参数已冻结：阈值 0，不依赖 count，known_texts 去重**
