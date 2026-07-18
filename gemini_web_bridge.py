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

            # ── 注入 MutationObserver（Gemini 改进版：处理 addedNodes）──
            await exec_js(200, (
                "(function(){"
                " if(window.__GEMINI_OBSERVER) return 'already';"
                " window.__GEMINI_LAST_RESP='';"
                " var extract=function(node){"
                "  if(!node||node.nodeType!==1) return null;"
                "  var el=node.matches('message-content')?node:node.querySelector('message-content');"
                "  if(!el) return null;"
                "  var t=(el.innerText||el.textContent||'').trim();"
                "  return t.length>20?t:null;"
                " };"
                " var observer=new MutationObserver(function(mutations){"
                "  for(var mi=0;mi<mutations.length;mi++){"
                "   var m=mutations[mi];"
                "   for(var j=0;j<m.addedNodes.length;j++){"
                "    var nt=extract(m.addedNodes[j]);"
                "    if(nt) window.__GEMINI_LAST_RESP=nt;"
                "   }"
                "   if(m.target&&m.target.querySelectorAll){"
                "    var mcs=m.target.querySelectorAll('message-content');"
                "    for(var k=0;k<mcs.length;k++){"
                "     var t=(mcs[k].innerText||'').trim();"
                "     if(t.length>20) window.__GEMINI_LAST_RESP=t;"
                "    }"
                "   }"
                "  }"
                " });"
                " observer.observe(document.body,{childList:true,subtree:true,characterData:true});"
                " window.__GEMINI_OBSERVER=observer;"
                " return 'ok';"
                "})();"
            ))
            log("MutationObserver installed")

            # ── 每次发送前：清空缓存 + 记录基准 count（去重用）──
            await exec_js(201, (
                "window.__GEMINI_LAST_RESP='';"
                "window.__GEMINI_SENT_COUNT=document.querySelectorAll('message-content').length;"
                "'ok';"
            ))

            # ── 多模态：通过 DataTransfer + paste 事件模拟 Ctrl+V 粘贴 ──
            if image_path and os.path.isfile(image_path):
                log("Uploading image via paste simulation:", image_path)
                abs_path = os.path.abspath(image_path)

                # 步骤1：用 JS 创建隐藏 file input，通过 objectId 注入文件（绕过 DOM 树刷新问题）
                create_res = await exec_js(210, (
                    "(function(){"
                    " var inp=document.createElement('input');"
                    " inp.type='file';"
                    " inp.style.display='none';"
                    " document.body.appendChild(inp);"
                    " return inp;"  # returnByValue=false → 返回 objectId
                    "})();"
                ))
                # exec_js 用了 returnByValue=True，所以返回的是 "[object HTMLInputElement]" 之类的字符串
                # 需要用 send_cdp 直接调 Runtime.evaluate（returnByValue=false）来获取 objectId
                obj_res = await send_cdp(211, "Runtime.evaluate", {
                    "expression": (
                        "(function(){"
                        " var inp=document.createElement('input');"
                        " inp.type='file';"
                        " inp.style.display='none';"
                        " document.body.appendChild(inp);"
                        " return inp;"
                        "})();"
                    ),
                    "returnByValue": False
                })
                obj_id = obj_res.get("result", {}).get("result", {}).get("objectId")
                if obj_id:
                    await send_cdp(212, "DOM.setFileInputFiles", {
                        "objectId": obj_id,
                        "files": [abs_path]
                    })
                    log("File injected via objectId, dispatching paste...")
                    await exec_js(213, (
                        "(function(){"
                        " var fi=document.querySelector('input[type=\"file\"]:not([accept])');"
                        " if(!fi||!fi.files||fi.files.length===0) return 'no-files';"
                        " var dt=new DataTransfer();"
                        " for(var i=0;i<fi.files.length;i++){dt.items.add(fi.files[i]);}"
                        " var tb=document.querySelector('rich-textarea div[contenteditable=\"true\"], div[role=\"textbox\"]');"
                        " if(!tb) return 'no-textbox';"
                        " tb.focus();"
                        " tb.dispatchEvent(new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:dt}));"
                        " return 'paste-ok';"
                        "})();"
                    ))
                    log("Paste dispatched")
                    await asyncio.sleep(3.0)
                else:
                    log("Cannot get objectId for file input")

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

            # 回复检测：Observer 缓存 → 兜底扫描（跳过 sent_count 之前的旧消息）
            js_get = (
                "(function(){"
                " var c=window.__GEMINI_LAST_RESP;"
                " if(c&&c.length>10) return c;"
                " var all=document.querySelectorAll('message-content');"
                " if(all.length===0){"
                "  var busy=document.querySelector('[aria-busy=\"true\"], mat-progress-bar');"
                "  return busy?'PROCESSING':'WAIT';"
                " }"
                # 只扫描新消息（至少 +2: 跳过用户消息，等模型回复）
                " var sent=window.__GEMINI_SENT_COUNT||0;"
                " if(all.length<=sent+1) return 'WAIT';"
                " for(var i=all.length-1;i>=0;i--){"
                "  var t=(all[i].innerText||all[i].textContent||'').trim();"
                "  if(t.length>10) return t;"
                " }"
                " return 'WAIT';"
                "})();"
            )
            sl=0; st=0; ft=""; stale=0; await asyncio.sleep(3.0)
            while True:
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
                if st>=3: log("Captured, len:", len(ft)); break
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

SN="gemini-web-bridge"; SV="2.2.0"
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
