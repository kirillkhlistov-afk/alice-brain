import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__

PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Алиса — панель</title>
<style>
  :root { --bg:#12141a; --card:#1c1f29; --accent:#7c6cff; --text:#e8e9ee; --muted:#8b8fa3; }
  * { box-sizing:border-box; margin:0; padding:0; font-family:system-ui,-apple-system,sans-serif; }
  body { background:var(--bg); color:var(--text); min-height:100vh; display:flex; flex-direction:column; align-items:center; padding:24px 16px; }
  h1 { font-size:1.3rem; margin-bottom:4px; }
  .status { color:var(--muted); font-size:.85rem; margin-bottom:16px; }
  #chat { background:var(--card); border-radius:16px; width:100%; max-width:560px; height:55vh; overflow-y:auto; padding:16px; display:flex; flex-direction:column; gap:10px; }
  .msg { max-width:85%; padding:10px 14px; border-radius:14px; line-height:1.4; white-space:pre-wrap; }
  .user { align-self:flex-end; background:var(--accent); color:#fff; border-bottom-right-radius:4px; }
  .bot  { align-self:flex-start; background:#2a2e3c; border-bottom-left-radius:4px; }
  .row { width:100%; max-width:560px; display:flex; gap:8px; margin-top:12px; }
  input#txt { flex:1; background:var(--card); color:var(--text); border:1px solid #2e3242; border-radius:12px; padding:12px 14px; font-size:1rem; outline:none; }
  input#txt:focus { border-color:var(--accent); }
  button { background:var(--accent); color:#fff; border:none; border-radius:12px; padding:12px 20px; font-size:1rem; cursor:pointer; }
  button:active { opacity:.8; }
  .cards { width:100%; max-width:560px; display:flex; gap:10px; margin-top:14px; flex-wrap:wrap; }
  .card { background:var(--card); border-radius:14px; padding:14px 18px; flex:1; min-width:150px; text-align:center; }
  .card b { display:block; font-size:1.4rem; }
  .card span { color:var(--muted); font-size:.8rem; }
  input[type=range] { width:100%; accent-color:var(--accent); }
</style>
</head>
<body>
  <h1>@ <span id="title">Алиса</span></h1>
  <div class="status" id="status">загрузка...</div>
  <div id="chat"></div>
  <div class="row">
    <input id="txt" placeholder="Скажи что-нибудь текстом..." autocomplete="off">
    <button onclick="send()">-></button>
  </div>
  <div class="cards">
    <div class="card"><b id="timers">0</b><span>таймеров</span></div>
    <div class="card"><b id="brain">-</b><span>LLM-мозг</span></div>
  </div>
  <div class="cards">
    <div class="card" style="text-align:left">
      <span>Громкость: <b id="vol_label">-</b></span>
      <input type="range" id="vol" min="0" max="100" onchange="setVolume(this.value)">
    </div>
  </div>
<script>
const chat = document.getElementById('chat');
function add(cls, text){ const d=document.createElement('div'); d.className='msg '+cls; d.textContent=text; chat.appendChild(d); chat.scrollTop=chat.scrollHeight; }
async function refresh(){
  const s = await (await fetch('/api/status')).json();
  document.getElementById('title').textContent = s.name;
  document.getElementById('status').textContent = s.llm ? 'LLM-мозг подключён' : 'офлайн-режим (LLM-ключ не задан)';
  document.getElementById('timers').textContent = s.timers;
  document.getElementById('brain').textContent = s.llm ? 'вкл' : 'выкл';
}
async function send(){
  const input = document.getElementById('txt');
  const text = input.value.trim();
  if(!text) return;
  input.value='';
  add('user', text);
  const r = await (await fetch('/api/ask', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text})})).json();
  add('bot', r.answer || '(нет ответа)');
  refresh();
}
async function setVolume(v){
  document.getElementById('vol_label').textContent = v + '%';
  await fetch('/api/volume', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({level:+v})});
}
document.getElementById('txt').addEventListener('keydown', e => { if(e.key==='Enter') send(); });
refresh(); setInterval(refresh, 10000);
</script>
</body>
</html>
"""


class ControlServer:
    def __init__(self, assistant, host: str = "0.0.0.0", port: int = 8080):
        self.assistant = assistant
        self.host = host
        self.port = port
        self.httpd = None
        self.thread = None
        self.lock = threading.Lock()

    def start_background(self):
        self.httpd = ThreadingHTTPServer((self.host, self.port), self._handler())
        self.host, self.port = self.httpd.server_address[:2]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd = None

    def _handler(self):
        assistant = self.assistant
        lock = self.lock
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _json(self, data, code=200):
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _body(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    return json.loads(raw)
                except Exception:
                    return {}

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    body = PAGE.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == "/api/status":
                    self._json({
                        "name": assistant.config.name,
                        "city": assistant.config.city,
                        "llm": bool(assistant.config.llm.api_key),
                        "timers": assistant.timers.count(),
                        "version": __version__,
                    })
                elif self.path == "/api/timers":
                    self._json({"count": assistant.timers.count()})
                else:
                    self._json({"error": "not found"}, 404)

            def do_POST(self):
                if self.path == "/api/ask":
                    data = self._body()
                    text = str(data.get("text", "")).strip()
                    if not text:
                        self._json({"answer": ""}, 400)
                        return
                    with lock:
                        answer = assistant.handle_text(text)
                    self._json({"answer": answer})
                elif self.path == "/api/volume":
                    data = self._body()
                    ok, message = outer.set_volume(data.get("level"))
                    self._json({"ok": ok, "message": message}, 200 if ok else 400)
                else:
                    self._json({"error": "not found"}, 404)

        return Handler

    @staticmethod
    def set_volume(level) -> tuple:
        import subprocess
        try:
            value = max(0, min(100, int(level)))
            subprocess.run(
                ["amixer", "sset", "Master", f"{value}%"],
                check=True, capture_output=True, timeout=10,
            )
            return True, f"{value}%"
        except Exception as exc:
            return False, f"не удалось изменить громкость: {exc}"
