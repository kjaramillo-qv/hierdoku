import base64, getpass, json, os, sys, time, urllib.request
import websocket

PORT = 9222
BASE = f"http://127.0.0.1:{PORT}"

def targets():
    return json.load(urllib.request.urlopen(BASE + "/json/list"))

def connect():
    pages = [t for t in targets() if t.get("type") == "page"]
    ws = websocket.create_connection(pages[0]["webSocketDebuggerUrl"], timeout=20, suppress_origin=True)
    return ws

ws = connect(); seq = 0

def cmd(method, params=None, timeout=30):
    global seq
    seq += 1; i = seq
    ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
    end = time.time() + timeout
    while time.time() < end:
        msg = json.loads(ws.recv())
        if msg.get("id") == i:
            if "error" in msg: raise RuntimeError(msg["error"])
            return msg.get("result", {})
    raise TimeoutError(method)

def ev(expr):
    r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    return r.get("result", {}).get("value")

def nav(url):
    cmd("Page.navigate", {"url": url}); time.sleep(5)

def real_click(text):
    rect = ev("(() => {const e=[...document.querySelectorAll('button,a,[role=button]')].find(x=>x.getClientRects().length&&(x.innerText||x.getAttribute('aria-label')||'').trim()===" + json.dumps(text) + "); if(!e)return null; e.scrollIntoView({block:'center'}); const r=e.getBoundingClientRect(); return {x:r.left+r.width/2,y:r.top+r.height/2,html:e.outerHTML.slice(0,500)}})()")
    if not rect: return "not found"
    cmd("Input.dispatchMouseEvent", {"type":"mouseMoved","x":rect["x"],"y":rect["y"]})
    cmd("Input.dispatchMouseEvent", {"type":"mousePressed","x":rect["x"],"y":rect["y"],"button":"left","clickCount":1})
    cmd("Input.dispatchMouseEvent", {"type":"mouseReleased","x":rect["x"],"y":rect["y"],"button":"left","clickCount":1})
    return rect

def shot(path):
    r = cmd("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    with open(path, "wb") as f: f.write(base64.b64decode(r["data"]))

cmd("Page.enable"); cmd("Runtime.enable")
cmd("Emulation.setDeviceMetricsOverride", {"width": 1920, "height": 1080, "deviceScaleFactor": 1, "mobile": False})
mode = sys.argv[1] if len(sys.argv) > 1 else "inspect"
if mode == "login":
    user = input("Email: ")
    password = getpass.getpass("Password: ")
    nav("https://app.izytesting.com/")
    script = """(() => {
      const inputs=[...document.querySelectorAll('input')];
      const email=inputs.find(x=>/email|correo/i.test((x.placeholder||'')+' '+(x.type||'')))||inputs[0];
      const pass=inputs.find(x=>x.type==='password')||inputs[1];
      const set=(el,v)=>{const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};
      set(email,%s); set(pass,%s);
      const b=[...document.querySelectorAll('button')].find(x=>/iniciar|ingresar|login|log in/i.test(x.innerText));
      if(b){b.click(); return 'clicked '+b.innerText} return 'no button';
    })()""" % (json.dumps(user), json.dumps(password))
    print(ev(script)); time.sleep(8)
if mode == "elements":
    print(ev("JSON.stringify([...document.querySelectorAll('a,button,[role=button]')].map((e,i)=>({i,text:(e.innerText||e.getAttribute('aria-label')||e.title||'').trim(),href:e.href||'',cls:e.className||''})).filter(x=>x.text),null,2)"))
elif mode == "click-config":
    print(real_click("Configuraciones")); time.sleep(3)
elif mode == "click-mcp":
    print(real_click("MCP")); time.sleep(5)
elif mode == "click-integrations":
    print(real_click("Integraciones")); time.sleep(5)
elif mode == "open-mcp-key":
    print(real_click("Generar clave MCP")); time.sleep(4)
elif mode == "cancel":
    print(real_click("Cancelar")); time.sleep(4)
elif mode == "modals":
    print(ev("JSON.stringify([...document.querySelectorAll('.modal')].map((m,i)=>({i,id:m.id,text:m.innerText,html:m.outerHTML.slice(0,8000)})),null,2)"))
elif mode == "diag-config":
    print(ev("(() => {let e=[...document.querySelectorAll('button')].find(x=>(x.innerText||'').trim()==='Configuraciones');let a=[];while(e&&a.length<8){let r=e.getBoundingClientRect();a.push({tag:e.tagName,cls:e.className,rect:{x:r.x,y:r.y,w:r.width,h:r.height},style:getComputedStyle(e).cssText,html:e.outerHTML.slice(0,1000)});e=e.parentElement}return JSON.stringify(a,null,2)})()"))
elif mode == "show-sidebar":
    print(ev("(() => {const p=document.querySelector('.sidebar-wrapper');p.style.setProperty('transform','none','important');p.style.setProperty('left','0','important');p.style.setProperty('display','block','important');p.style.setProperty('visibility','visible','important');p.style.setProperty('z-index','99999','important');return p.getBoundingClientRect().toJSON()})()")); time.sleep(2)
elif mode == "open-config":
    print(ev("(() => {const p=document.querySelector('.sidebar-wrapper');p.style.setProperty('transform','none','important');p.style.setProperty('left','0','important');p.style.setProperty('display','block','important');p.style.setProperty('visibility','visible','important');p.style.setProperty('z-index','99999','important');return p.getBoundingClientRect().toJSON()})()")); time.sleep(1)
    rect=ev("(() => {const e=document.querySelector('.burger-btn');const r=e.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()")
    cmd("Input.dispatchMouseEvent", {"type":"mousePressed","x":rect["x"],"y":rect["y"],"button":"left","clickCount":1}); cmd("Input.dispatchMouseEvent", {"type":"mouseReleased","x":rect["x"],"y":rect["y"],"button":"left","clickCount":1}); time.sleep(2)
    print(real_click("Configuraciones")); time.sleep(4)
print("URL", ev("location.href"))
print("TITLE", ev("document.title"))
print("TEXT\n", ev("document.body.innerText"))
shot("/opt/data/izy-current.png")
print("SHOT /opt/data/izy-current.png")
ws.close()
