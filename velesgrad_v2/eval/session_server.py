"""One long-lived MiraChat session behind a tiny HTTP endpoint, for interactive testing.

POST /say   {"text": "..."}  -> {"reply": "..."}
POST /reset                  -> new session
Bound to 127.0.0.1 (local testing only).
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

from velesgrad_v2.chat import MiraChat

_lock = threading.Lock()
_state = {"mira": None}


def _fresh():
    _state["mira"] = MiraChat("seed", knowledge="books")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        with _lock:
            if self.path == "/reset":
                _fresh()
                return self._send({"reset": True})
            if _state["mira"] is None:
                _fresh()
            reply = _state["mira"].respond(body.get("text", ""))
        self._send({"reply": reply})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8099), H).serve_forever()
