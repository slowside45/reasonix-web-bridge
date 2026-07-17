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
                return await send_cdp(cid, "Runtime.evaluate", {"expression": js})

            # ── 多模态：通过隐藏 input 注入文件 ──
            if image_path and os.path.isfile(image_path):
                log("Uploading:", image_path)
                abs_path = os.path.abspath(image_path)

                # 用 JS 创建一个隐藏的 file input（如果不存在），插入到 body
                create_res = await send_cdp(201, "Runtime.evaluate", {
                    "expression": (
                        "(function(){"
                        " var inp=document.getElementById('__gemini_file_upload');"
                        " if(!inp){"
                        "   inp=document.createElement('input');"
                        "   inp.id='__gemini_file_upload';"
                        "   inp.type='file';"
                        "   inp.style.display='none';"
                        "   document.body.appendChild(inp);"
                        " }"
                        " return inp.id;"
                        "})()"
                    ),
                    "returnByValue": False
                })
                obj_id = create_res.get("result", {}).get("result", {}).get("objectId")
                if obj_id:
                    await send_cdp(202, "DOM.setFileInputFiles", {
                        "objectId": obj_id,
                        "files": [abs_path]
                    })
                    log("File injected")
                    # 触发 change 事件
                    await exec_js(203, (
                        "(function(){"
                        " var inp=document.getElementById('__gemini_file_upload');"
                        " if(inp) inp.dispatchEvent(new Event('change',{bubbles:true}));"
                        " return inp ? 'ok' : 'no-inp';"
                        "})();"
                    ))
                else:
                    log("Could not create hidden input")
                await asyncio.sleep(2.0)

            # ── 发送文本（无论是否传图，都聚焦输入框并填入文本）──
            # 注意：文本注入必须在图片操作之后进行，且必须重新查找输入框
            log("Now injecting text...")

            # ── 基准气泡数 ──
            js_count = "(function(){var s=['message-content','.message-content','gmat-rich-text','.model-response','[data-message-author-role=\"model\"]'];for(var i=0;i<s.length;i++){var e=document.querySelectorAll(s[i]);if(e.length>0)return e.length;}return 0;})();"
            old_res = await exec_js(101, js_count)
            old_count = old_res.get("result",{}).get("result",{}).get("value",0) or 0
            log("Base bubbles:", old_count)
            escaped = prompt_text.replace("\\","\\\\").replace("`","\\`").replace("\n","\\n").replace("\r","\\r")
            js_input = ("(function(){var b=document.querySelector('div[role=\"textbox\"],textarea,.rich-textarea,[contenteditable=\"true\"]');if(!b)return false;b.focus();"
                        f"if(b.tagName==='TEXTAREA'||b.tagName==='INPUT'){{b.value=`{escaped}`;}}"
                        f"else{{b.innerText=`{escaped}`;}}"
                        "b.dispatchEvent(new Event('input',{bubbles:true,composed:true}));return true;})();")
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
