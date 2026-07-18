#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
❖ Gemini Web Bridge — 一键安装脚本 (v2.2)
-------------------------------------------
用法：
    python install.py

自动完成：
  1. 安装依赖 (websockets)
  2. 若 gemini_web_bridge.py 缺失则创建
  3. 生成/更新 .mcp.json
  4. 安装/更新 gemini-mode Skill

支持：Windows / macOS / Linux
"""

import json, os, platform, subprocess, sys

COLOR_GREEN  = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED    = "\033[91m"
COLOR_RESET  = "\033[0m"

if platform.system() == "Windows":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        COLOR_GREEN = COLOR_YELLOW = COLOR_RED = COLOR_RESET = ""

def green(s):  return f"{COLOR_GREEN}{s}{COLOR_RESET}"
def yellow(s): return f"{COLOR_YELLOW}{s}{COLOR_RESET}"
def red(s):    return f"{COLOR_RED}{s}{COLOR_RESET}"

# ═══════════════════════════════ 配置
PYTHON_EXE = sys.executable
TARGET_DIR = os.getcwd()
MCP_JSON_PATH = os.path.join(TARGET_DIR, ".mcp.json")
SKILLS_DIR = os.path.join(TARGET_DIR, ".reasonix", "skills", "gemini-mode")
BRIDGE_SCRIPT_NAME = "gemini_web_bridge.py"
BRIDGE_SCRIPT_PATH = os.path.join(TARGET_DIR, BRIDGE_SCRIPT_NAME)

# ═══════════════════════════════ Skill 内容 (v2.2 — 自举版)
SKILL_CONTENT = r"""---
name: gemini-mode
description: 自动将每次提问转发给网页 Gemini，根据回答执行本地操作；自动安装依赖、启动浏览器并提示登录
---

## Gemini Augmented Mode (v2.2 — 自举版)

收到用户消息后，**自动完成以下全部步骤，无需用户干预**：

---

### 步骤 A：环境自检 & 自动修复

**每次执行前检查**：

```
1. websockets 是否已安装？→ 没有就 pip install websockets
2. gemini_web_bridge.py 是否存在？→ 没有就 python install.py（仅首次）
3. .mcp.json 是否配置了 gemini-web-bridge？→ 没有就 python install.py（仅首次）
```

> 环境就绪后直接进入步骤 B，不再重复检查依赖。

---

### 步骤 B：确保浏览器就绪

**优先级：MCP 工具 > Python 直调**

**B1. 检查状态：**
- 优先调用 MCP `check_gemini_status`
- MCP 不可用时，用 Python 检查 CDP：
  ```python
  import urllib.request, json
  tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=3).read())
  # 检查是否有 gemini.google.com 标签页
  ```

**B2. 启动浏览器（如未运行）：**
- 优先调用 MCP `setup_gemini_browser`
- MCP 不可用时，用 bash 启动（关键：`--disable-background-mode`）：
  ```powershell
  $edgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
  $userDir = "$env:USERPROFILE\.gemini-mcp-browser-profile"
  & $edgePath --remote-debugging-port=9222 --user-data-dir="$userDir" --no-first-run --no-default-browser-check --disable-background-mode https://gemini.google.com
  ```
  等待 5-8 秒后验证 CDP 就绪。

**B3. 登录检查：**
- Gemini 标签页标题含 "Sign in" / "登录" / "Google 账号" → 提示用户手动登录
- 已登录 → 继续

---

### 步骤 C：发送消息到 Gemini

**优先级：MCP `ask_gemini_web` > Python 直调**

MCP 不可用时，写临时 Python 脚本直调：
```python
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_web_bridge import ask_gemini_web
async def main():
    result = await ask_gemini_web("用户消息原文")
    print("REPLY:", result)
asyncio.run(main())
```

---

### 步骤 D：执行 Gemini 的回复

- 文件/目录操作严格按 Gemini 规划执行
- 纯提问直接用 Gemini 回答
- Markdown 代码块写入对应文件
- 异常时根据错误排查，必要时重新启动浏览器

---

### 原则
- 不要提示"先问问 Gemini"，静默执行全部步骤
- Gemini 是脑（规划），Reasonix 是手（执行）
- 保留 emoji 和特殊字符
- 任何步骤失败自动 fallback 到 Python 直调路径
- Edge 150+ 必须 `--disable-background-mode`，否则进程秒退
"""

# ═══════════════════════════════ 安装步骤
def run(cmd, desc=""):
    print(f"  {desc}...")
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print()
    print(green("╔══════════════════════════════════════╗"))
    print(green("║  Gemini Web Bridge - 一键安装向导   ║"))
    print(green("╚══════════════════════════════════════╝"))
    print()
    print(f"  Platform:   {platform.system()}")
    print(f"  Python:     {sys.version.split()[0]}")
    print(f"  Target dir: {TARGET_DIR}")
    print()

    # ── 1. 安装依赖 ──
    print(yellow("[1/4] Installing websockets..."))
    ok = run([PYTHON_EXE, "-m", "pip", "install", "websockets", "-q"], "pip install websockets")
    if ok:
        print(green("       websockets installed"))
    else:
        print(yellow("       Retrying with --user..."))
        run([PYTHON_EXE, "-m", "pip", "install", "websockets", "--user", "-q"], "pip install --user")
    print()

    # ── 2. MCP 服务器脚本（仅当缺失时创建）──
    print(yellow(f"[2/4] Checking {BRIDGE_SCRIPT_NAME}..."))
    if os.path.exists(BRIDGE_SCRIPT_PATH):
        print(green(f"       {BRIDGE_SCRIPT_NAME} already exists, skipping"))
    else:
        # 紧急 fallback：从当前仓库复制，或报错
        print(red(f"       {BRIDGE_SCRIPT_NAME} NOT FOUND!"))
        print(red(f"       Please clone the full repository, or re-download {BRIDGE_SCRIPT_NAME}"))
        print()
        return 1
    print()

    # ── 3. 配置 MCP JSON ──
    print(yellow("[3/4] Configuring .mcp.json..."))
    mcp_config = {
        "mcpServers": {
            "gemini-web-bridge": {
                "command": "python",
                "args": [BRIDGE_SCRIPT_PATH],
                "alwaysAllow": True,
                "env": {
                    "PYTHONIOENCODING": "utf-8",
                    "GEMINI_CDP_PORT": "9222"
                }
            }
        }
    }

    # 合并已有配置
    if os.path.exists(MCP_JSON_PATH):
        with open(MCP_JSON_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing_servers = existing.get("mcpServers", {})
        existing_servers["gemini-web-bridge"] = mcp_config["mcpServers"]["gemini-web-bridge"]
        existing["mcpServers"] = existing_servers
        mcp_config = existing

    with open(MCP_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(mcp_config, f, indent=2, ensure_ascii=False)
    print(green("       .mcp.json configured"))
    print()

    # ── 4. 安装/更新 Skill ──
    print(yellow("[4/4] Installing gemini-mode skill..."))
    os.makedirs(SKILLS_DIR, exist_ok=True)
    with open(os.path.join(SKILLS_DIR, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(SKILL_CONTENT)
    print(green(f"       Skill installed at {SKILLS_DIR}"))
    print()

    # ── 验证 ──
    print(green("═══════════════════════════════════════"))
    print(green("  安装完成！"))
    print(green("═══════════════════════════════════════"))
    print()
    print("  ✅ websockets 依赖")
    print(f"  ✅ MCP Server:  {BRIDGE_SCRIPT_NAME}")
    print(f"  ✅ MCP Config:  .mcp.json")
    print(f"  ✅ Skill:       .reasonix/skills/gemini-mode/")
    print()
    print(yellow("  Next: 输入 /gemini-mode 即可使用！"))
    print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
