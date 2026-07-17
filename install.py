#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
❖ Gemini Web Bridge — 一键安装脚本
-----------------------------------
用法：
    python install.py

自动完成：
  1. 安装依赖 (websockets)
  2. 生成 MCP 服务器脚本 (gemini_web_bridge.py)
  3. 生成/更新 .mcp.json 配置
  4. 安装 Skill (gemini-mode/)
  5. 验证环境

支持：Windows / macOS / Linux
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request

# ═══════════════════════════════
COLOR_GREEN  = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED    = "\033[91m"
COLOR_RESET  = "\033[0m"

if platform.system() == "Windows":
    # Windows CMD/PowerShell 不一定支持 ANSI
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        COLOR_GREEN = COLOR_YELLOW = COLOR_RED = COLOR_RESET = ""

def green(s):  return f"{COLOR_GREEN}{s}{COLOR_RESET}"
def yellow(s): return f"{COLOR_YELLOW}{s}{COLOR_RESET}"
def red(s):    return f"{COLOR_RED}{s}{COLOR_RESET}"

# ═══════════════════════════════
#  配置
# ═══════════════════════════════
PYTHON_EXE = sys.executable
TARGET_DIR = os.getcwd()
MCP_JSON_PATH = os.path.join(TARGET_DIR, ".mcp.json")
SKILLS_DIR = os.path.join(TARGET_DIR, ".reasonix", "skills", "gemini-mode")
BRIDGE_SCRIPT_NAME = "gemini_web_bridge.py"
BRIDGE_SCRIPT_PATH = os.path.join(TARGET_DIR, BRIDGE_SCRIPT_NAME)

# MCP 服务器脚本内容（内嵌，不需要网络下载）
MCP_SERVER_CODE = r'''##!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gemini Web Bridge - Cross-Platform MCP stdio Server
https://github.com/yourname/mcp-server-gemini-web
"""
import asyncio, json, os, platform, shutil, subprocess, sys, threading, urllib.request

def log(*args): print(*args, file=sys.stderr, flush=True)

PLATFORM = platform.system()

BROWSER_CANDIDATES = {
    "chrome": [
        ("C:/Program Files/Google/Chrome/Application/chrome.exe", "Google Chrome (64-bit)"),
        ("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe", "Google Chrome (32-bit)"),
        ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "Google Chrome"),
        ("google-chrome", "Google Chrome (system)"),
    ],
    "edge": [
        ("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "Microsoft Edge (x86)"),
        ("C:/Program Files/Microsoft/Edge/Application/msedge.exe", "Microsoft Edge (64-bit)"),
        ("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge", "Microsoft Edge"),
        ("microsoft-edge", "Microsoft Edge (system)"),
    ],
    "chromium": [
        (os.path.expandvars("%LOCALAPPDATA%/Chromium/Application/chrome.exe"), "Chromium"),
        ("/Applications/Chromium.app/Contents/MacOS/Chromium", "Chromium"),
        ("chromium-browser", "Chromium (system)"),
        ("chromium", "Chromium (system)"),
    ],
    "brave": [
        ("C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe", "Brave"),
        ("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser", "Brave"),
    ],
}

def find_browser():
    for brow_name, candidates in BROWSER_CANDIDATES.items():
        for path_tmpl, display in candidates:
            path = path_tmpl
            if PLATFORM == "Windows" and "%" in path:
                try: path = os.path.expandvars(path)
                except: continue
            if "/" not in path and "\\" not in path:
                found = shutil.which(path)
                if found: return {"name": brow_name, "path": found, "display": display}
                continue
            if os.path.isfile(path): return {"name": brow_name, "path": path, "display": display}
    return None

BROWSER = find_browser()
CDP_PORT = int(os.environ.get("GEMINI_CDP_PORT", "9222"))
USER_DATA_DIR = os.environ.get("GEMINI_USER_DATA_DIR", "")
if not USER_DATA_DIR:
    USER_DATA_DIR = (os.path.expandvars(r"%USERPROFILE%\.gemini-mcp-browser-profile")
                     if PLATFORM == "Windows"
                     else os.path.expanduser("~/.gemini-mcp-browser-profile"))

def get_cdp_json():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=2) as resp:
            return json.loads(resp.read().decode())
    except: return None

def get_gemini_ws():
    tabs = get_cdp_json()
    if not tabs: return None
    for tab in tabs:
        if "gemini.google.com" in tab.get("url",""): return tab.get("webSocketDebuggerUrl")
    return None

def check_gemini_ready():
    tabs = get_cdp_json()
    if not tabs: return False, f"No browser on port {CDP_PORT}"
    for tab in tabs:
        if "gemini.google.com" in tab.get("url",""):
            title = tab.get("title","")
            if any(kw in title for kw in ["Sign in","登录","Google 账号"]):
                return False, "Gemini open but NOT LOGGED IN"
            return True, "Gemini ready"
    return False, "No Gemini tab"

async def ask_gemini_web(prompt_text, image_path=None):
    ws_url = get_gemini_ws()
    if not ws_url:
        hint = BROWSER["display"] if BROWSER else "Chrome/Edge"
        return f"ERROR: No browser. Start {hint} with --remote-debugging-port={CDP_PORT}"
    import websockets
    try:
        async with websockets.connect(ws_url, ping_interval=None) as ws:
            # 通用 CDP 命令发送
            async def send_cdp(cid, method, params=None):
                cmd = {"id": cid, "method": method}
                if params: cmd["params"] = params
                await ws.send(json.dumps(cmd))
                return json.loads(await ws.recv())

            async def exec_js(cid, js):
                return await send_cdp(cid, "Runtime.evaluate", {"expression": js})

            # ── 多模态：上传图片 ──
            if image_path and os.path.isfile(image_path):
                log("Uploading image:", image_path)
                abs_path = os.path.abspath(image_path)
                # 1. 启用 DOM
                await send_cdp(201, "DOM.enable")
                # 2. 获取 document
                doc = await send_cdp(202, "DOM.getDocument", {"depth": -1})
                root_id = doc.get("result", {}).get("root", {}).get("nodeId", 0)
                # 3. 查找第一个 input[type="file"]
                qr = await send_cdp(203, "DOM.querySelector", {
                    "nodeId": root_id,
                    "selector": "input[type='file']"
                })
                file_node_id = qr.get("result", {}).get("nodeId", 0)
                if file_node_id:
                    # 4. 注入文件
                    await send_cdp(204, "DOM.setFileInputFiles", {
                        "nodeId": file_node_id,
                        "files": [abs_path]
                    })
                    # 5. 触发 change 事件让 Gemini 感知
                    await exec_js(205, (
                        "(function(){"
                        " var f=document.querySelector('input[type=\"file\"]');"
                        " if(f){ f.dispatchEvent(new Event('change',{bubbles:true}));"
                        "        f.dispatchEvent(new Event('input',{bubbles:true})); }"
                        "})();"
                    ))
                    await asyncio.sleep(2.0)  # 等 Gemini 上传处理
                    log("Image uploaded")
                else:
                    log("No file input found on page")

            # ── 基准气泡数 ──
            js_count = "(function(){var s=['message-content','.message-content','gmat-rich-text','.model-response','[data-message-author-role=\"model\"]'];for(var i=0;i<s.length;i++){var e=document.querySelectorAll(s[i]);if(e.length>0)return e.length;}return 0;})();"
            old_res = await exec_js(101, js_count)
            old_count = old_res.get("result",{}).get("result",{}).get("value",0) or 0
            log("Base bubbles:", old_count)
            escaped = prompt_text.replace("\\","\\\\").replace("`","\\`").replace("\n","\\n").replace("\r","\\r")
            js_input = ("(function(){var b=document.querySelector('div[role=\"textbox\"],textarea,.rich-textarea,[contenteditable=\"true\"]');if(!b)return false;b.focus();"
                        f"if(b.tagName==='TEXTAREA'||b.tagName==='INPUT'){{b.value=`{escaped}`;}}"
                        f"else{{b.innerText=`{escaped}`;}}"
                        "b.dispatchEvent(new Event('input',{bubbles:true}));return true;})();")
            await exec_js(102, js_input)
            await asyncio.sleep(0.2)
            js_click = "(function(){var b=document.querySelector('button[aria-label*=\"Send\"],button[aria-label*=\"发送\"],.send-button');if(b){b.click();return true;}return false;})();"
            await exec_js(103, js_click)
            log("Injected, waiting...")
            js_get = ("(function(){var s=['message-content','.message-content','gmat-rich-text','.model-response','[data-message-author-role=\"model\"]'];var base="+str(old_count)+
                      ";for(var i=0;i<s.length;i++){var e=document.querySelectorAll(s[i]);if(e.length>base){var t=e[e.length-1].innerText||e[e.length-1].textContent;if(t&&t.trim().length>0)return t.trim();}}return 'WAIT';})();")
            sl=0; st=0; ft=""; await asyncio.sleep(3.0)
            while True:
                await asyncio.sleep(0.5)
                ro = await exec_js(104, js_get)
                ft = ro.get("result",{}).get("result",{}).get("value","") or ""
                if ft=="WAIT" or not ft: continue
                if len(ft)==sl and len(ft)>0: st+=1
                else: sl=len(ft); st=0
                if st>=6: log("Captured, len:", len(ft)); break
            return ft
    except Exception as e: return "ERROR: "+str(e)

def setup_browser():
    lines=[]
    existing=get_cdp_json()
    if existing:
        lines.append("OK Browser already on port "+str(CDP_PORT))
        rd,msg=check_gemini_ready()
        lines.append(("OK " if rd else "WARN ")+msg)
        return "\n".join(lines)
    if not BROWSER: return "FAIL No browser found. Install Chrome or Edge."
    cmd=[BROWSER["path"],f"--remote-debugging-port={CDP_PORT}",f"--user-data-dir={USER_DATA_DIR}","--no-first-run","--no-default-browser-check","https://gemini.google.com"]
    try:
        if PLATFORM=="Windows": subprocess.Popen(cmd,creationflags=subprocess.DETACHED_PROCESS)
        else: subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        lines.append("OK Launched "+BROWSER["display"]+" on port "+str(CDP_PORT))
        lines.append("   Please LOG IN at gemini.google.com")
    except Exception as e: lines.append("FAIL "+str(e))
    return "\n".join(lines)

SN="gemini-web-bridge"; SV="2.0.0"
TOOLS=[{"name":"ask_gemini_web","description":"Send prompt (and optionally an image) to Gemini in Chrome/Edge. Set image_path to a local image file for vision analysis. Returns full reply.","inputSchema":{"type":"object","properties":{"prompt":{"type":"string","description":"The prompt to send"},"image_path":{"type":"string","description":"Optional: absolute path to an image file for Gemini vision analysis"}},"required":["prompt"]}},{"name":"setup_gemini_browser","description":"Auto-detect and launch Chrome/Edge with debug port.","inputSchema":{"type":"object","properties":{},"required":[]}},{"name":"check_gemini_status","description":"Check browser+Gemini status.","inputSchema":{"type":"object","properties":{},"required":[]}}]
def mr(i,r): return json.dumps({"jsonrpc":"2.0","id":i,"result":r},ensure_ascii=False)
def me(i,c,m): return json.dumps({"jsonrpc":"2.0","id":i,"error":{"code":c,"message":m}},ensure_ascii=False)

async def handle(req):
    rid=req.get("id"); m=req.get("method",""); p=req.get("params",{})
    if m=="initialize": return mr(rid,{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":SN,"version":SV}})
    if m=="tools/list": return mr(rid,{"tools":TOOLS})
    if m=="tools/call":
        tn=p.get("name",""); a=p.get("arguments",{})
        if tn=="ask_gemini_web":
            pr=a.get("prompt","").strip()
            if not pr: return mr(rid,{"content":[{"type":"text","text":"ERROR: prompt required"}],"isError":True})
            img = a.get("image_path","").strip() or None
            return mr(rid,{"content":[{"type":"text","text":await ask_gemini_web(pr, img)}]})
        if tn=="setup_gemini_browser": return mr(rid,{"content":[{"type":"text","text":setup_browser()}]})
        if tn=="check_gemini_status":
            rd,msg=check_gemini_ready()
            info=[f"{'OK' if rd else 'FAIL'} {msg}","","Platform: "+PLATFORM,"CDP Port: "+str(CDP_PORT)]
            if BROWSER: info.append("Browser: "+BROWSER["display"])
            return mr(rid,{"content":[{"type":"text","text":"\n".join(info)}]})
        return me(rid,-32601,"Unknown tool: "+tn)
    return me(rid,-32601,"Unknown method: "+m)

async def main():
    log(SN+" v"+SV+" MCP stdio started")
    q=asyncio.Queue()
    def sr():
        for line in sys.stdin:
            line=line.strip()
            if line: asyncio.run_coroutine_threadsafe(q.put(line),loop)
        asyncio.run_coroutine_threadsafe(q.put(None),loop)
    loop=asyncio.get_event_loop()
    threading.Thread(target=sr,daemon=True).start()
    while True:
        line=await q.get()
        if line is None: break
        line=line.replace('\ufeff','').strip()
        try: req=json.loads(line)
        except: continue
        if req.get("method") and req.get("id") is None: continue
        resp=await handle(req)
        sys.stdout.write(resp+"\n"); sys.stdout.flush()

if __name__=="__main__":
    if sys.platform=="win32":
        sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout,"reconfigure") else None
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
'''

# Skill 内容
SKILL_CONTENT = """---
name: gemini-mode
description: 自动将每次提问转发给网页 Gemini，根据回答执行本地操作；自动启动浏览器并提示登录
---

## Gemini Augmented Mode (v2)

收到用户消息后：

### 步骤 0：确保浏览器就绪（首次）
1. 调用 `check_gemini_status` 检查
2. 若浏览器未启动，调用 `setup_gemini_browser` 并提示用户登录取
3. 用户确认后用 `check_gemini_status` 验证

### 步骤 1：转发到 Gemini
调用 `ask_gemini_web`，把用户消息原样发送。

### 步骤 2：获取回复
等待返回完整文本。

### 步骤 3：执行
- 文件/目录操作严格按 Gemini 规划执行
- 纯提问用 Gemini 回答
- Markdown 代码块写入对应文件

### 原则
- 不要提示"先问问 Gemini"，静默执行
- Gemini 是脑（规划），你是手（执行）
- 保留 emoji 和特殊字符
- 异常时根据错误排查，必要时重新启动浏览器
"""


# ═══════════════════════════════
#  安装步骤
# ═══════════════════════════════
def run(cmd, desc=""):
    print(f"  {desc}...")
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    # 防止 Windows GBK 编码错误
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
    print(yellow("[1/4] Installing dependencies (websockets)..."))
    ok = run([PYTHON_EXE, "-m", "pip", "install", "websockets", "-q"], "pip install websockets")
    if ok:
        print(green(f"       websockets installed"))
    else:
        print(red(f"       pip install failed, trying with --user..."))
        run([PYTHON_EXE, "-m", "pip", "install", "websockets", "--user", "-q"], "pip install --user")
    print()

    # ── 2. 生成 MCP 服务器脚本 ──
    print(yellow("[2/4] Creating MCP server script..."))
    with open(BRIDGE_SCRIPT_PATH, "w", encoding="utf-8") as f:
        f.write(MCP_SERVER_CODE)
    print(green(f"       {BRIDGE_SCRIPT_NAME} created"))
    print()

    # ── 3. 配置 MCP JSON ──
    print(yellow("[3/4] Configuring .mcp.json..."))
    mcp_config = {
        "mcpServers": {
            "gemini-web-bridge": {
                "command": PYTHON_EXE,
                "args": [BRIDGE_SCRIPT_PATH],
                "alwaysAllow": True,
                "env": {
                    "PYTHONIOENCODING": "utf-8",
                    "GEMINI_CDP_PORT": "9222"
                }
            }
        }
    }

    # 如果已有 .mcp.json，合并
    if os.path.exists(MCP_JSON_PATH):
        with open(MCP_JSON_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing_servers = existing.get("mcpServers", {})
        existing_servers["gemini-web-bridge"] = mcp_config["mcpServers"]["gemini-web-bridge"]
        existing["mcpServers"] = existing_servers
        mcp_config = existing

    with open(MCP_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(mcp_config, f, indent=2, ensure_ascii=False)
    print(green(f"       .mcp.json configured"))
    print()

    # ── 4. 安装 Skill ──
    print(yellow("[4/4] Installing gemini-mode skill..."))
    os.makedirs(SKILLS_DIR, exist_ok=True)
    with open(os.path.join(SKILLS_DIR, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(SKILL_CONTENT)
    print(green(f"       Skill installed at {SKILLS_DIR}"))
    print()

    # ── 验证 ──
    print(green("═══════════════════════════════════════"))
    print(green("  安裝完成！"))
    print(green("═══════════════════════════════════════"))
    print()
    print("  ✅ websockets 依赖")
    print(f"  ✅ MCP Server:  {BRIDGE_SCRIPT_NAME}")
    print(f"  ✅ MCP Config:  .mcp.json")
    print(f"  ✅ Skill:       .reasonix/skills/gemini-mode/")
    print()
    print(yellow("  Next steps:"))
    print("    1. 重启 Reasonix 客户端")
    print("    2. 在控制台输入 /gemini-mode 激活")
    print("    3. 开始使用！")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
