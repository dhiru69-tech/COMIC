#!/usr/bin/env python3
"""
COMIC — Local Intelligence Server
Logs device info to terminal on every visit.
Run:  python server.py
"""

import http.server
import socketserver
import os
import json
import datetime
import webbrowser
import urllib.request
import urllib.error
import base64
from threading import Timer
from collections import defaultdict

PORT      = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
LOG_FILE  = os.path.join(DIRECTORY, "visits.log")

# Set this in your environment, never hardcode it here:
#   export OPENAI_API_KEY="sk-...."         (Mac/Linux)
#   setx OPENAI_API_KEY "sk-...."           (Windows, restart terminal after)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL   = "gpt-4o-mini"

R="\033[0m"; B="\033[1m"; DIM="\033[2m"
CY="\033[96m"; GR="\033[92m"; YL="\033[93m"
RD="\033[91m"; MG="\033[95m"; WH="\033[97m"; BL="\033[94m"

session_count = 0
ip_visit_map  = defaultdict(list)

def div(c="─",w=64,col=DIM): print(f"{col}{c*w}{R}")
def sec(label,col=YL): print(f"\n{col}{B}  {label}{R}"); div()
def row(k,v,kc=WH,vc=GR): print(f"  {kc}{k:<30}{R} {vc}{v}{R}")

def write_log(entry):
    with open(LOG_FILE,"a",encoding="utf-8") as f:
        f.write(json.dumps(entry)+"\n")


# ----------------------------------------------------------------
# OPENAI VISION — real face / skin analysis
# ----------------------------------------------------------------

ANALYSIS_PROMPT = """You are a professional facial-aesthetics and skin analyst.
Look at the attached face photo and respond with ONLY a JSON object (no markdown,
no commentary, no code fences) with exactly these keys:

{
  "face_shape": "Oval | Round | Square | Heart | Diamond | Oblong",
  "symmetry_score": <integer 0-100>,
  "proportions_score": <integer 0-100>,
  "skin_score": <integer 0-100>,
  "skin_notes": "<short factual note on visible skin texture, tone evenness, visible concerns like dryness/oiliness/blemishes — be kind and constructive, not harsh>",
  "jawline_score": <integer 0-100>,
  "eye_area_score": <integer 0-100>,
  "overall_score": <integer 0-100>,
  "standout_features": ["<feature>", "<feature>", "<feature>"],
  "summary": "<2-3 sentence friendly, constructive overall assessment>"
}

Be realistic and varied in scoring based on what you actually observe — do not
default to a fixed number. If no face is visible, set all numeric scores to 0
and explain in "summary"."""


def call_openai_vision(image_data_url, api_key=None):
    """Send a base64 data URL image to OpenAI's vision model and return parsed JSON."""
    key = api_key or OPENAI_API_KEY
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Run: export OPENAI_API_KEY=\"sk-...\" then restart server.py"
        )

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ANALYSIS_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ],
        "max_tokens": 600,
        "temperature": 0.4,
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenAI API error {e.code}: {err_body[:300]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach OpenAI API: {e.reason}")

    text = body["choices"][0]["message"]["content"].strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def print_face_analysis(result, ip):
    now = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    print(); div("═",64,MG)
    print(f"{MG}{B}   COMIC  ·  AI FACE ANALYSIS  ·  {now}{R}")
    div("═",64,MG)
    row("Client IP",          ip, vc=RD)
    row("Model",              OPENAI_MODEL)
    sec("RESULT", GR)
    row("Face Shape",         result.get("face_shape","—"))
    row("Overall Score",      str(result.get("overall_score","—")))
    row("Symmetry",           str(result.get("symmetry_score","—")))
    row("Proportions",        str(result.get("proportions_score","—")))
    row("Skin Score",         str(result.get("skin_score","—")))
    row("Skin Notes",         result.get("skin_notes","—"))
    row("Jawline",            str(result.get("jawline_score","—")))
    row("Eye Area",           str(result.get("eye_area_score","—")))
    row("Standout Features",  ", ".join(result.get("standout_features") or []))
    sec("SUMMARY", YL)
    print(f"  {result.get('summary','—')}")
    div("═",64,MG); print()

    write_log({
        "type": "face_analysis",
        "timestamp": now,
        "ip": ip,
        "result": result,
    })


def print_report(data, ip, ua):
    global session_count
    session_count += 1
    now = datetime.datetime.now()
    ts  = now.strftime("%Y-%m-%d  %H:%M:%S")

    ip_visit_map[ip].append(ts)
    visits     = ip_visit_map[ip]
    visit_no   = len(visits)
    first_seen = visits[0]
    last_seen  = visits[-2] if len(visits)>1 else "First visit"

    print(); div("═",64,CY)
    print(f"{CY}{B}   COMIC  ·  SESSION #{session_count}  ·  {ts}{R}")
    div("═",64,CY)

    sec("CONNECTION",CY)
    row("Client IP",        ip,                          vc=RD)
    row("Visit Count",      str(visit_no),               vc=YL)
    row("First Seen",       first_seen,                  vc=DIM+WH)
    row("Last Visit",       last_seen,                   vc=DIM+WH)
    row("Referrer",         data.get("referrer","Direct"))
    row("Page URL",         data.get("pageUrl","—"))

    sec("PERFORMANCE",GR)
    perf = data.get("performance") or {}
    row("DNS Lookup",       perf.get("dns","—")+"ms")
    row("TCP Connect",      perf.get("tcp","—")+"ms")
    row("Time to First Byte",perf.get("ttfb","—")+"ms")
    row("DOM Load",         perf.get("domLoad","—")+"ms")
    row("Full Page Load",   perf.get("pageLoad","—")+"ms")
    row("DOM Elements",     str(data.get("domElements","—")))
    row("Time on Page",     data.get("timeOnPage","—"))

    sec("BROWSER",BL)
    row("User Agent",       (ua[:58]+"…") if len(ua)>58 else ua)
    row("Browser",          data.get("browser","—"))
    row("Version",          data.get("browserVersion","—"))
    row("Engine",           data.get("engine","—")+" "+data.get("engineVersion",""))
    row("Language",         data.get("language","—"))
    row("All Languages",    data.get("languages","—"))
    row("Cookies Enabled",  str(data.get("cookiesEnabled","—")))
    row("Do Not Track",     data.get("doNotTrack","unset"))
    row("Online",           str(data.get("online","—")))

    sec("DEVICE / OS",MG)
    row("Platform",         data.get("platform","—"))
    row("OS",               data.get("os","—")+" "+data.get("osVersion",""))
    row("Device Type",      data.get("deviceType","—"))
    row("Vendor / Model",   data.get("deviceVendor","—")+" "+data.get("deviceModel",""))
    row("CPU Cores",        str(data.get("cpuCores","—")))
    row("Architecture",     data.get("architecture","—"))
    row("Touch Points",     str(data.get("maxTouchPoints","—")))
    row("Pointer Type",     data.get("pointerType","—"))

    sec("HARDWARE",YL)
    row("RAM (reported)",   data.get("ram","—"))
    bat = data.get("battery") or {}
    if bat:
        row("Battery Level",    bat.get("level","—"))
        row("Charging",         bat.get("charging","—"))
        row("Discharge Time",   bat.get("dischargingTime","—"))
    else:
        row("Battery",          "API unavailable")

    sec("DISPLAY",GR)
    row("Screen Resolution",data.get("screenResolution","—"))
    row("Available Screen", data.get("availableScreen","—"))
    row("Viewport",         data.get("viewportSize","—"))
    row("Color Depth",      str(data.get("colorDepth","—"))+" bit")
    row("Pixel Ratio",      str(data.get("pixelRatio","—"))+"x")
    row("Orientation",      data.get("orientation","—"))
    row("HDR",              str(data.get("hdr","—")))
    row("Dark Mode Pref",   str(data.get("darkMode","—")))

    sec("NETWORK",BL)
    net = data.get("network") or {}
    if net:
        row("Type",             net.get("type","—"))
        row("Effective Type",   net.get("effectiveType","—"))
        row("Downlink",         str(net.get("downlink","—"))+" Mbps")
        row("RTT",              str(net.get("rtt","—"))+" ms")
        row("Save Data",        str(net.get("saveData","—")))
    else:
        row("Network API",      "Not available")

    sec("MEDIA DEVICES",MG)
    row("Cameras",          str(data.get("cameras","—")))
    row("Microphones",      str(data.get("microphones","—")))
    row("Speakers",         str(data.get("speakers","—")))
    row("Permissions",      data.get("mediaPermissions","—"))

    sec("CAPABILITIES",CY)
    row("WebGL",            str(data.get("webgl","—")))
    row("WebGL Renderer",   str(data.get("webglRenderer","—"))[:55])
    row("WebAssembly",      str(data.get("wasm","—")))
    row("Service Worker",   str(data.get("serviceWorker","—")))
    row("WebRTC",           str(data.get("webrtc","—")))
    row("Notifications",    str(data.get("notifications","—")))
    row("Geolocation",      str(data.get("geolocation","—")))
    row("Storage Estimate", data.get("storageEstimate","—"))
    row("IndexedDB",        str(data.get("indexedDB","—")))
    row("LocalStorage",     str(data.get("localStorage","—")))

    sec("LOCALE / TIME",YL)
    row("Timezone",         data.get("timezone","—"))
    row("Offset",           data.get("timezoneOffset","—"))
    row("Locale",           data.get("locale","—"))
    row("Client Time",      data.get("clientTime","—"))

    div("═",64,CY)
    print(f"{DIM}  Saved → visits.log  |  Session #{session_count}{R}")
    div("═",64,CY); print()

    write_log({
        "session":    session_count,
        "timestamp":  ts,
        "ip":         ip,
        "visits":     visit_no,
        "browser":    data.get("browser","—")+" "+data.get("browserVersion",""),
        "os":         data.get("os","—")+" "+data.get("osVersion",""),
        "device":     data.get("deviceType","—"),
        "referrer":   data.get("referrer","direct"),
        "resolution": data.get("screenResolution","—"),
        "ram":        data.get("ram","—"),
        "timezone":   data.get("timezone","—"),
        "pageLoad":   (data.get("performance") or {}).get("pageLoad","—"),
    })


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=DIRECTORY,**kw)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_POST(self):
        if self.path=="/beacon":
            body = self.rfile.read(int(self.headers.get("Content-Length",0)))
            try:   data = json.loads(body.decode("utf-8"))
            except: data = {}
            print_report(data, self.client_address[0], self.headers.get("User-Agent","—"))
            self.send_response(204); self.end_headers()

        elif self.path=="/api/analyze-face":
            length = int(self.headers.get("Content-Length",0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8"))
                image_data_url = data.get("image","")
                test_only      = data.get("testOnly", False)

                # API key: prefer the one sent from frontend (localStorage key),
                # fallback to environment variable set at server start.
                req_key = data.get("apiKey","").strip()
                key_to_use = req_key or OPENAI_API_KEY

                if not key_to_use:
                    raise RuntimeError(
                        "No OpenAI API key — set one in the app Settings modal or via: export OPENAI_API_KEY=\"sk-...\""
                    )

                # Minimal key format check — catch Google/other keys early
                if not key_to_use.startswith("sk-"):
                    resp = json.dumps({"ok": False, "keyValid": False,
                        "error": "Invalid key format — OpenAI keys start with sk-. "
                                 "You may have entered a Google or other API key."
                    }).encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type","application/json")
                    self.send_header("Content-Length",str(len(resp)))
                    self._cors()
                    self.end_headers(); self.wfile.write(resp); return

                if test_only or not image_data_url.startswith("data:image"):
                    # Just validate the key format and connectivity
                    resp = json.dumps({"ok": True, "keyValid": True}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type","application/json")
                    self.send_header("Content-Length",str(len(resp)))
                    self._cors()
                    self.end_headers(); self.wfile.write(resp); return

                result = call_openai_vision(image_data_url, key_to_use)
                print_face_analysis(result, self.client_address[0])

                resp = json.dumps({"ok": True, "result": result}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",str(len(resp)))
                self._cors()
                self.end_headers(); self.wfile.write(resp)

            except Exception as e:
                print(f"{RD}{B}  AI ANALYSIS ERROR:{R} {RD}{e}{R}")
                resp = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",str(len(resp)))
                self._cors()
                self.end_headers(); self.wfile.write(resp)

        else:
            self.send_response(404); self.end_headers()

    def log_message(self,*a): pass

    def do_GET(self):
        if self.path in ("/","/index.html"):
            try:
                with open(os.path.join(DIRECTORY,"index.html"),"r",encoding="utf-8") as f:
                    html = f.read()
                html = html.replace("</body>",'<script src="/beacon.js"></script>\n</body>')
                enc  = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","text/html; charset=utf-8")
                self.send_header("Content-Length",str(len(enc)))
                self.end_headers(); self.wfile.write(enc); return
            except Exception as e: print(f"  ERR: {e}")

        if self.path=="/beacon.js":
            js = BEACON_JS.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type","application/javascript")
            self.send_header("Content-Length",str(len(js)))
            self.end_headers(); self.wfile.write(js); return

        super().do_GET()


BEACON_JS = r"""
(async function(){
  function waitForLoad(){
    return new Promise(res => {
      if (document.readyState === 'complete') return res();
      window.addEventListener('load', () => setTimeout(res, 50));
    });
  }
  await waitForLoad();

  function perf(){
    try{
      const n=performance.getEntriesByType('navigation')[0]||{};
      const t=performance.timing||{};
      const safe = (a,b) => {
        const v = Math.round((a||0) > 0 ? a : (b||0));
        return v > 0 && v < 600000 ? String(v) : '—';
      };
      return {
        dns:     safe(n.domainLookupEnd-n.domainLookupStart, 0),
        tcp:     safe(n.connectEnd-n.connectStart, 0),
        ttfb:    safe(n.responseStart-n.requestStart, 0),
        domLoad: safe(n.domContentLoadedEventEnd, t.domContentLoadedEventEnd-t.navigationStart),
        pageLoad:safe(n.loadEventEnd, t.loadEventEnd-t.navigationStart),
      };
    }catch{return {};}
  }

  function browser(){
    const ua=navigator.userAgent;
    let b='Unknown',v='—',e='—',ev='—';
    if(/Edg\//.test(ua))        {b='Edge';    v=ua.match(/Edg\/([\d.]+)/)?.[1]||'—';     e='Blink';}
    else if(/OPR\//.test(ua))   {b='Opera';   v=ua.match(/OPR\/([\d.]+)/)?.[1]||'—';     e='Blink';}
    else if(/Chrome\//.test(ua)){b='Chrome';  v=ua.match(/Chrome\/([\d.]+)/)?.[1]||'—';   e='Blink'; ev=ua.match(/AppleWebKit\/([\d.]+)/)?.[1]||'—';}
    else if(/Firefox\//.test(ua)){b='Firefox';v=ua.match(/Firefox\/([\d.]+)/)?.[1]||'—'; e='Gecko'; ev=ua.match(/rv:([\d.]+)/)?.[1]||'—';}
    else if(/Safari\//.test(ua)){b='Safari';  v=ua.match(/Version\/([\d.]+)/)?.[1]||'—';  e='WebKit';ev=ua.match(/AppleWebKit\/([\d.]+)/)?.[1]||'—';}
    return {browser:b,browserVersion:v,engine:e,engineVersion:ev};
  }

  function os(){
    const ua=navigator.userAgent;
    let o='Unknown',ov='—',dt='Desktop',dv='—',dm='—';
    if(/iPhone/.test(ua))       {o='iOS';     ov=ua.match(/OS ([\d_]+)/)?.[1]?.replace(/_/g,'.')||'—';dt='Mobile';dv='Apple';dm='iPhone';}
    else if(/iPad/.test(ua))    {o='iPadOS';  ov=ua.match(/OS ([\d_]+)/)?.[1]?.replace(/_/g,'.')||'—';dt='Tablet';dv='Apple';dm='iPad';}
    else if(/Android/.test(ua)) {o='Android'; ov=ua.match(/Android ([\d.]+)/)?.[1]||'—';dt=/Mobile/.test(ua)?'Mobile':'Tablet';}
    else if(/Win/.test(ua))     {o='Windows'; ov=ua.match(/Windows NT ([\d.]+)/)?.[1]||'—';}
    else if(/Mac/.test(ua))     {o='macOS';   ov=ua.match(/Mac OS X ([\d_]+)/)?.[1]?.replace(/_/g,'.')||'—';dv='Apple';}
    else if(/Linux/.test(ua))   {o='Linux';}
    else if(/CrOS/.test(ua))    {o='ChromeOS';}
    return {os:o,osVersion:ov,deviceType:dt,deviceVendor:dv,deviceModel:dm};
  }

  function webgl(){
    try{
      const c=document.createElement('canvas');
      const gl=c.getContext('webgl')||c.getContext('experimental-webgl');
      if(!gl)return{webgl:false,webglRenderer:'—',webglVendor:'—'};
      const ext=gl.getExtension('WEBGL_debug_renderer_info');
      return{webgl:true,
        webglRenderer:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),
        webglVendor:ext?gl.getParameter(ext.UNMASKED_VENDOR_WEBGL):gl.getParameter(gl.VENDOR)};
    }catch{return{webgl:false,webglRenderer:'—',webglVendor:'—'};}
  }

  async function storage(){
    try{const e=await navigator.storage.estimate();
      return `${(e.usage/1e6).toFixed(1)}MB / ${(e.quota/1e9).toFixed(2)}GB`;}
    catch{return '—';}
  }

  async function battery(){
    try{const b=await navigator.getBattery();
      const f=v=>v===Infinity?'N/A':Math.round(v)+'s';
      return{level:Math.round(b.level*100)+'%',charging:b.charging?'Yes':'No',
        chargingTime:f(b.chargingTime),dischargingTime:f(b.dischargingTime)};}
    catch{return null;}
  }

  async function media(){
    try{
      const d=await navigator.mediaDevices.enumerateDevices();
      const cp=await navigator.permissions.query({name:'camera'}).catch(()=>({state:'unknown'}));
      const mp=await navigator.permissions.query({name:'microphone'}).catch(()=>({state:'unknown'}));
      return{cameras:d.filter(x=>x.kind==='videoinput').length,
        microphones:d.filter(x=>x.kind==='audioinput').length,
        speakers:d.filter(x=>x.kind==='audiooutput').length,
        mediaPermissions:`cam:${cp.state} mic:${mp.state}`};}
    catch{return{cameras:'—',microphones:'—',speakers:'—',mediaPermissions:'—'};}
  }

  function arch(){
    const ua=navigator.userAgent;
    if(/arm64|aarch64/i.test(ua))return'ARM64';
    if(/arm/i.test(ua))return'ARM32';
    if(/x86_64|x64|WOW64/i.test(ua))return'x86_64';
    return'Unknown';
  }

  function net(){
    const c=navigator.connection||navigator.mozConnection||navigator.webkitConnection;
    if(!c)return null;
    return{type:c.type||'—',effectiveType:c.effectiveType||'—',
      downlink:c.downlink??'—',rtt:c.rtt??'—',saveData:c.saveData??'—'};
  }

  const _t0=Date.now();

  const [bat,stor,med]=await Promise.all([battery(),storage(),media()]);
  const {browser:br,browserVersion:bv,engine:en,engineVersion:ev}=browser();
  const {os:o,osVersion:ov,deviceType:dt,deviceVendor:dv,deviceModel:dm}=os();
  const {webgl:wg,webglRenderer:wr,webglVendor:wv}=webgl();
  const loc=Intl.DateTimeFormat().resolvedOptions();

  const payload={
    referrer:      document.referrer||'Direct',
    pageUrl:       location.href,
    domElements:   document.querySelectorAll('*').length,
    timeOnPage:    Math.round((Date.now()-_t0)/1000)+'s',
    performance:   perf(),

    browser:br,browserVersion:bv,engine:en,engineVersion:ev,
    language:      navigator.language||'—',
    languages:     (navigator.languages||[]).join(', ')||'—',
    cookiesEnabled:navigator.cookieEnabled,
    doNotTrack:    navigator.doNotTrack||'unset',
    online:        navigator.onLine,

    platform:      navigator.platform||'—',
    os:o,osVersion:ov,deviceType:dt,deviceVendor:dv,deviceModel:dm,
    cpuCores:      navigator.hardwareConcurrency||'—',
    architecture:  arch(),
    maxTouchPoints:navigator.maxTouchPoints||0,
    touchDevice:   navigator.maxTouchPoints>0,
    pointerType:   window.matchMedia('(pointer:fine)').matches?'Mouse':'Touch',

    ram:           navigator.deviceMemory?navigator.deviceMemory+' GB':'—',
    battery:       bat,

    screenResolution:`${screen.width} × ${screen.height}`,
    availableScreen:`${screen.availWidth} × ${screen.availHeight}`,
    viewportSize:  `${window.innerWidth} × ${window.innerHeight}`,
    colorDepth:    screen.colorDepth,
    pixelRatio:    window.devicePixelRatio||1,
    orientation:   (screen.orientation||{}).type||(window.innerWidth>window.innerHeight?'landscape':'portrait'),
    hdr:           window.matchMedia('(dynamic-range: high)').matches,
    darkMode:      window.matchMedia('(prefers-color-scheme: dark)').matches,

    network:       net(),
    ...med,

    webgl:wg,webglRenderer:wr,webglVendor:wv,
    wasm:          typeof WebAssembly==='object',
    serviceWorker: 'serviceWorker' in navigator,
    notifications: 'Notification' in window,
    geolocation:   'geolocation' in navigator,
    webrtc:        !!(window.RTCPeerConnection),
    storageEstimate:stor,
    indexedDB:     'indexedDB' in window,
    localStorage:  (()=>{try{localStorage.setItem('_t','1');localStorage.removeItem('_t');return true;}catch{return false;}})(),

    timezone:      loc.timeZone||'—',
    timezoneOffset:new Date().getTimezoneOffset()+' min',
    locale:        loc.locale||'—',
    clientTime:    new Date().toLocaleString(),
  };

  try{
    await fetch('/beacon',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  }catch(e){console.warn('Beacon:',e);}
})();
"""

def startup():
    print(); div("═",64,CY)
    print(f"{CY}{B}   COMIC — Local Intelligence Server{R}")
    div("═",64,CY)
    print(f"  {WH}URL       {GR}http://localhost:{PORT}{R}")
    print(f"  {WH}Log file  {DIM}{LOG_FILE}{R}")
    key_status = f"{GR}set ({OPENAI_API_KEY[:7]}...){R}" if OPENAI_API_KEY else f"{RD}NOT SET — face AI analysis will fail{R}"
    print(f"  {WH}OpenAI Key{R} {key_status}")
    print(f"  {WH}Stop      {DIM}Ctrl + C{R}")
    div("═",64,CY); print()

startup()
Timer(1.2,lambda:webbrowser.open(f"http://localhost:{PORT}")).start()

with socketserver.TCPServer(("",PORT),Handler) as httpd:
    try:    httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{DIM}  Server stopped. Logs saved → visits.log{R}\n")
