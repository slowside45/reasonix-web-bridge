#!/usr/bin/env python
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
        async with websockets.connect(ws_url, ping_interval=None, max_size=None) as ws:
            # 通用 CDP 命令发送
            async def send_cdp(cid, method, params=None):
                cmd = {"id": cid, "method": method}
                if params: cmd["params"] = params
                # ensure_ascii=False: 中文直接以 UTF-8 传输，避免 \uXXXX 转义
                # 在 Windows 的某些 CDP/websocket 路径上导致 GBK 混淆
                await ws.send(json.dumps(cmd, ensure_ascii=False))
                return json.loads(await ws.recv())

            async def exec_js(cid, js):
                return await send_cdp(cid, "Runtime.evaluate", {"expression": js, "returnByValue": True})

            # ── RPA 图片上传（pyautogui 物理点击 + 文件对话框）──
            if image_path and os.path.isfile(image_path):
                abs_path = os.path.abspath(image_path)
                log("RPA upload:", abs_path)
                try:
                    import pyautogui, pyperclip
                    # 1. 获取按钮在视口中的坐标 + 窗口在屏幕上的偏移
                    pos_info = await exec_js(300, (
                        "(function(){"
                        " var b=document.querySelector('button[aria-label=\"Upload and tools\"]');"
                        " if(!b) return 'no-btn';"
                        " var r=b.getBoundingClientRect();"
                        " return JSON.stringify({bx:r.left+r.width/2,by:r.top+r.height/2,"
                        "  ow:window.outerWidth- window.innerWidth,oh:window.outerHeight-window.innerHeight});"
                        "})();"
                    ))
                    pos = json.loads(pos_info.get("result",{}).get("result",{}).get("value","{}"))
                    if not pos or pos.get("bx") is None: raise Exception("no upload button")
                    # 屏幕坐标 = 视口坐标 + 窗口边框偏移
                    sx = pos["bx"] + (pos.get("ow", 0) or 0)
                    sy = pos["by"] + (pos.get("oh", 0) or 40)  # 标题栏 ~40px
                    log(f"RPA click at screen ({sx:.0f},{sy:.0f})")
                    # 2. pyautogui 物理点击（真实鼠标，isTrusted=true）
                    pyautogui.moveTo(sx, sy, duration=0.2)
                    pyautogui.click()
                    await asyncio.sleep(2.0)
                    # 3. 文件对话框操作
                    pyperclip.copy(abs_path)
                    pyautogui.hotkey('ctrl','v')
                    await asyncio.sleep(0.5)
                    pyautogui.press('enter')
                    await asyncio.sleep(4.0)
                    log("RPA upload completed")
                except Exception as e:
                    log(f"RPA failed: {e}")

            # ── 注入 MutationObserver（简化版，阈值 2）──
            await exec_js(200, (
                "(function(){"
                " if(window.__GEMINI_OBSERVER) return 'already';"
                " window.__GEMINI_LAST_RESP='';"
                " var scan=function(){"
                "  var all=document.querySelectorAll('message-content');"
                "  for(var i=all.length-1;i>=0;i--){"
                "   var t=(all[i].innerText||all[i].textContent||'').trim();"
                "   if(t.length>1){window.__GEMINI_LAST_RESP=t;return;}"
                "  }"
                " };"
                " var observer=new MutationObserver(scan);"
                " observer.observe(document.body,{childList:true,subtree:true,characterData:true});"
                " window.__GEMINI_OBSERVER=observer;"
                " scan();"
                " return 'ok';"
                "})();"
            ))
            log("Observer installed")

            # ── 每次发送前：清空缓存 + 快照所有已知文本 ──
            await exec_js(201, (
                "window.__GEMINI_LAST_RESP='';"
                "window.__KNOWN_TEXTS=new Set(Array.from("
                " document.querySelectorAll('message-content')).map(function(m){"
                "  return (m.innerText||'').trim().substring(0,80);}));"
                "'ok';"
            ))

            # ── 发送文本（无论是否传图）──
            log("Now injecting text...")

            # 文本注入：使用 CDP Input.insertText（Quill 只接受真实输入事件）
            log("Injecting text via Input.insertText...")
            # 先聚焦输入框
            await exec_js(102, (
                "(function(){"
                " var b=document.querySelector('.ql-editor');"
                " if(!b) b=document.querySelector('div[role=\"textbox\"][contenteditable=\"true\"]');"
                " if(!b) return 'no-input';"
                " b.focus(); b.click();"
                " return 'focused';"
                "})();"
            ))
            await asyncio.sleep(0.1)
            # 用 Input.insertText 逐段注入（中文友好，触发 Quill 内部状态更新）
            await send_cdp(103, "Input.insertText", {"text": prompt_text})
            await asyncio.sleep(0.3)
            js_click = "(function(){var b=document.querySelector('button[aria-label*=\"Send\"],button[aria-label*=\"发送\"],.send-button');if(b){b.click();return true;}return false;})();"
            await exec_js(104, js_click)
            log("Injected, waiting for reply...")

            # 回复检测：Observer 优先 → DOM 扫描（跳过 known_texts）
            js_get = (
                "(function(){"
                " var c=window.__GEMINI_LAST_RESP;"
                " if(c&&typeof c==='string'&&c.trim().length>0){"
                "  if(!window.__KNOWN_TEXTS.has(c.trim().substring(0,80))) return c;"
                " }"
                " var all=document.querySelectorAll('message-content');"
                " if(all.length===0) return 'WAIT';"
                " for(var i=all.length-1;i>=0;i--){"
                "  var t=(all[i].innerText||all[i].textContent||'').trim();"
                "  if(t.length>0&&!window.__KNOWN_TEXTS.has(t.substring(0,80))) return t;"
                " }"
                " return 'WAIT';"
                "})();"
            )
            sl=0; st=0; ft=""; stale=0; start_ts = asyncio.get_event_loop().time(); await asyncio.sleep(5.0)
            while True:
                await asyncio.sleep(0.5)
                try:
                    ro = await exec_js(105, js_get)
                    ft = str(ro.get("result",{}).get("result",{}).get("value","") or "")
                except Exception as e:
                    log("JS eval error:", e)
                    stale += 1
                    if stale > 10: break
                    await asyncio.sleep(1.0)
                    continue
                if ft=="PROCESSING":
                    stale = 0  # 图片处理中，不计入超时
                    await asyncio.sleep(1.0)
                    continue
                if ft=="WAIT" or not ft:
                    stale += 1
                    if stale > 90:
                        log("Timeout waiting for reply")
                        return "ERROR: Gemini did not respond within 90 seconds"
                    await asyncio.sleep(1.0)
                    continue
                stale = 0
                if len(ft)==sl and len(ft)>0: st+=1
                else: sl=len(ft); st=0
                elapsed = asyncio.get_event_loop().time() - start_ts
                if elapsed > 5 and st >= 10: log("Captured, len:", len(ft)); break
            return ft
    except websockets.exceptions.ConnectionClosed as e:
        log(f"WS closed: {e.code}:{e.reason}")
        return "ERROR: WebSocket connection closed - Gemini tab may have crashed"
    except Exception as e:
        log(f"Unexpected: {type(e).__name__}: {e}")
        return "ERROR: "+str(e)

def setup_browser():
    lines=[]
    existing=get_cdp_json()
    if existing:
        lines.append("OK Browser already on port "+str(CDP_PORT))
        rd,msg=check_gemini_ready()
        lines.append(("OK " if rd else "WARN ")+msg)
        return "\n".join(lines)
    if not BROWSER: return "FAIL No browser found. Install Chrome or Edge."
    cmd=[BROWSER["path"],f"--remote-debugging-port={CDP_PORT}",f"--user-data-dir={USER_DATA_DIR}","--no-first-run","--no-default-browser-check","--disable-background-mode","https://gemini.google.com"]
    try:
        if PLATFORM=="Windows":
            subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        lines.append("OK Launched "+BROWSER["display"]+" on port "+str(CDP_PORT))
        lines.append("   Please LOG IN at gemini.google.com")
    except Exception as e: lines.append("FAIL "+str(e))
    return "\n".join(lines)

SN="gemini-web-bridge"; SV="3.1.0"  # 冻结版 — 回复检测逻辑勿改
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
