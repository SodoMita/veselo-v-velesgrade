#!/usr/bin/env python3
"""
serve.py – Mira (OpenCog chat stack) exposed as an OpenAI-compatible LLM server.

The model behind the API is the Velesgrad chat itself: AtomSpace knowledge,
PLN reasoning, speech-act recognition, Link Grammar validation. No neural
network is involved, so the "model" answers only from what the AtomSpace
holds, and every reply is grammar-checked.

Endpoints (JSON, stdlib only, no dependencies):
  GET  /                        browser chat page
  GET  /health                  liveness + whether Link Grammar is active
  GET  /v1/models               lists the single model "mira-opencog"
  POST /v1/chat/completions     OpenAI chat format (stream=true supported)
  POST /v1/completions          OpenAI text format (last line = player input)

Conversation state: the API is stateless like the OpenAI one. Each request
replays the user turns of `messages` into a fresh Mira instance, so the
same history always yields the same answers (seeded RNG).

Usage:
  VELESGRAD_DEV=1 python -m velesgrad_v2.serve --host 0.0.0.0 --port 8080
"""

import argparse
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL_ID = "mira-opencog"
MIRA_SEED = 7

# The AtomSpace is process-global (cog.atomspace._ASP), so only one Mira
# may be live at a time. Requests are serialized through this lock.
_LOCK = threading.Lock()


KNOWLEDGE = None  # None or "books"; set by --knowledge


def _mira_reply(user_turns):
    """Replay user turns into a fresh MiraChat; return the final reply."""
    from .chat import MiraChat
    mira = MiraChat(seed=MIRA_SEED, knowledge=KNOWLEDGE)
    reply = ""
    for text in user_turns:
        reply = mira.respond(text)
    return reply


def _user_turns_from_messages(messages):
    turns = []
    for m in messages or []:
        if m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, list):  # OpenAI multi-part content
                content = " ".join(p.get("text", "") for p in content
                                   if isinstance(p, dict))
            turns.append(str(content).strip())
    return [t for t in turns if t]


def _approx_tokens(text):
    return max(1, len(text.split()))


def answer(user_turns):
    if not user_turns:
        return "Ask, and I will answer what I can."
    with _LOCK:
        return _mira_reply(user_turns)


def _chat_payload(reply, prompt_text, stream):
    created = int(time.time())
    rid = "chatcmpl-" + uuid.uuid4().hex[:24]
    usage = {"prompt_tokens": _approx_tokens(prompt_text),
             "completion_tokens": _approx_tokens(reply),
             "total_tokens": _approx_tokens(prompt_text) + _approx_tokens(reply)}
    if stream:
        return rid, created, usage
    return {
        "id": rid, "object": "chat.completion", "created": created,
        "model": MODEL_ID,
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": reply},
                     "finish_reason": "stop"}],
        "usage": usage,
    }


INDEX_HTML = """<!doctype html><meta charset="utf-8">
<title>Mira – OpenCog chat server</title>
<style>
body{font-family:Georgia,serif;background:#1d1a16;color:#eadfc8;max-width:720px;margin:2rem auto;padding:0 1rem}
h1{font-size:1.3rem;color:#d8b36a}
#log{border:1px solid #4a4032;padding:1rem;min-height:320px;white-space:pre-wrap;background:#14120f}
.you{color:#9fc3d9}.mira{color:#eadfc8}
form{display:flex;gap:.5rem;margin-top:.7rem}
input{flex:1;padding:.5rem;background:#14120f;color:#eadfc8;border:1px solid #4a4032}
button{padding:.5rem 1rem;background:#d8b36a;border:0;color:#1d1a16;cursor:pointer}
small{color:#8a7d66}
</style>
<h1>Mira, keeper of the Velesgrad archive</h1>
<small>Answers come from the OpenCog AtomSpace, checked by Link Grammar. API: /v1/chat/completions</small>
<div id="log"></div>
<form id="f"><input id="q" autocomplete="off" placeholder="Say something to Mira..." autofocus><button>Send</button></form>
<script>
const msgs=[];const log=document.getElementById('log');
function add(who,t){const d=document.createElement('div');d.className=who;d.textContent=(who==='you'?'You: ':'Mira: ')+t;log.appendChild(d);log.scrollTop=log.scrollHeight;}
document.getElementById('f').onsubmit=async e=>{
  e.preventDefault();const q=document.getElementById('q');const t=q.value.trim();if(!t)return;q.value='';
  add('you',t);msgs.push({role:'user',content:t});
  const r=await fetch('v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:'mira-opencog',messages:msgs})});
  const j=await r.json();const c=j.choices[0].message.content;msgs.push({role:'assistant',content:c});add('mira',c);
};
</script>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "MiraServer/1.0"

    def log_message(self, fmt, *args):
        print("[serve]", self.address_string(), fmt % args, flush=True)

    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code, msg):
        self._send_json(code, {"error": {"message": msg, "type": "invalid_request_error"}})

    def _read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return None
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            body = INDEX_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/health":
            from .dialogue import lg_ctypes
            self._send_json(200, {"status": "ok", "model": MODEL_ID,
                                  "link_grammar": bool(lg_ctypes.is_available())})
        elif path == "/v1/models":
            self._send_json(200, {"object": "list", "data": [
                {"id": MODEL_ID, "object": "model", "created": 0,
                 "owned_by": "velesgrad"}]})
        else:
            self._error(404, f"unknown path {path}")

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            req = self._read_json() or {}
        except (ValueError, UnicodeDecodeError):
            return self._error(400, "body must be JSON")

        if path == "/v1/chat/completions":
            turns = _user_turns_from_messages(req.get("messages"))
            prompt_text = " ".join(turns)
        elif path == "/v1/completions":
            prompt = req.get("prompt", "")
            if isinstance(prompt, list):
                prompt = "\n".join(str(p) for p in prompt)
            lines = [l.strip() for l in str(prompt).strip().split("\n") if l.strip()]
            turns = lines[-1:]
            prompt_text = str(prompt)
        else:
            return self._error(404, f"unknown path {path}")

        reply = answer(turns)
        stream = bool(req.get("stream"))

        if path == "/v1/completions":
            payload = {"id": "cmpl-" + uuid.uuid4().hex[:24],
                       "object": "text_completion", "created": int(time.time()),
                       "model": MODEL_ID,
                       "choices": [{"index": 0, "text": reply,
                                    "finish_reason": "stop", "logprobs": None}],
                       "usage": {"prompt_tokens": _approx_tokens(prompt_text),
                                 "completion_tokens": _approx_tokens(reply),
                                 "total_tokens": _approx_tokens(prompt_text) + _approx_tokens(reply)}}
            return self._send_json(200, payload)

        if not stream:
            return self._send_json(200, _chat_payload(reply, prompt_text, False))

        # Streaming: one content chunk, then the [DONE] sentinel (SSE).
        rid, created, _ = _chat_payload(reply, prompt_text, True)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        chunks = [
            {"id": rid, "object": "chat.completion.chunk", "created": created,
             "model": MODEL_ID,
             "choices": [{"index": 0, "delta": {"role": "assistant", "content": reply},
                          "finish_reason": None}]},
            {"id": rid, "object": "chat.completion.chunk", "created": created,
             "model": MODEL_ID,
             "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        ]
        for c in chunks:
            self.wfile.write(b"data: " + json.dumps(c, ensure_ascii=False).encode() + b"\n\n")
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def main():
    ap = argparse.ArgumentParser(description="Mira (OpenCog) as an OpenAI-compatible server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--knowledge", choices=["none", "books"], default="none",
                    help="books: add human-life facts from Gutenberg (data/book_facts.json)")
    args = ap.parse_args()
    global KNOWLEDGE
    KNOWLEDGE = None if args.knowledge == "none" else args.knowledge
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Mira server on http://{args.host}:{args.port}  (model '{MODEL_ID}', knowledge={args.knowledge})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
