"""Owner-only local web UI/API. Binds 127.0.0.1 only; reach it through an SSH tunnel."""
import hashlib
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .engine import UserError
from .router import RouterError

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/app.css": ("app.css", "text/css; charset=utf-8")}
MAX_BODY = 64 * 1024
MAX_TOKEN = 200
SECURITY_HEADERS = {
    "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
}


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Handler(BaseHTTPRequestHandler):
    server_version = "NetTime"
    sys_version = ""

    def log_message(self, fmt, *args):  # never log requests (headers/paths could carry secrets)
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _host_ok(self):
        return self.headers.get("Host", "") in self.server.allowed_hosts

    def _authed(self):
        h = self.headers.get("Authorization", "")
        if not h.startswith("Bearer ") or len(h) > MAX_TOKEN + 7:
            return False
        return hmac.compare_digest(token_hash(h[7:]), self.server.token_hash)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "Forbidden host"})
        path = self.path.split("?", 1)[0]
        if path in STATIC:
            name, ctype = STATIC[path]
            with open(os.path.join(STATIC_DIR, name), "rb") as f:
                return self._send(200, f.read(), ctype)
        if not path.startswith("/api/"):
            return self._send(404, {"error": "Not found"})
        if not self._authed():
            return self._send(401, {"error": "Access key required"})
        eng = self.server.engine
        if path == "/api/status":
            return self._send(200, eng.snapshot())
        if path == "/api/export":
            return self._send(200, eng.snapshot()["settings"])  # weekly rules only: no bonus, token or login
        return self._send(404, {"error": "Not found"})

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"error": "Forbidden host"})
        origin = self.headers.get("Origin")
        if origin is not None and origin not in self.server.allowed_origins:
            return self._send(403, {"error": "Cross-origin request refused"})
        if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
            return self._send(403, {"error": "Cross-origin request refused"})
        if not self._authed():
            return self._send(401, {"error": "Access key required"})
        if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
            return self._send(415, {"error": "JSON required"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = -1
        if n < 0 or n > MAX_BODY:
            return self._send(413, {"error": "Body too large"})
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except ValueError:
            return self._send(400, {"error": "Invalid JSON"})
        if not isinstance(body, dict):
            return self._send(400, {"error": "Invalid JSON"})
        eng = self.server.engine
        path = self.path.split("?", 1)[0]
        try:
            if path in ("/api/settings", "/api/import"):
                eng.save_settings(body.get("settings"))
                return self._send(200, {"message": "Saved. Blocking switch unchanged."})
            if path == "/api/discover":
                return self._send(200, {"devices": eng.discover()})
            if path == "/api/target":
                eng.select_target(body.get("mac"), body.get("name") if isinstance(body.get("name"), str) else None)
                return self._send(200, {"message": "Device selected"})
            if path == "/api/target/clear":
                eng.clear_target()
                return self._send(200, {"message": "Device unselected. Blocking stays off."})
            if path == "/api/bonus":
                eng.add_bonus(body.get("minutes"))
                return self._send(200, {"message": "Extra time added for today"})
            if path == "/api/bonus/clear":
                eng.clear_bonus()
                return self._send(200, {"message": "Extra time cleared"})
            if path == "/api/enforcement":
                if not isinstance(body.get("enabled"), bool):
                    raise UserError("enabled must be true or false")
                return self._send(200, {"message": eng.set_enforcement(body["enabled"])})
            if path == "/api/release":
                return self._send(200, {"message": eng.retry_release(body.get("confirmUncertain") is True)})
            if path == "/api/resume":
                return self._send(200, {"message": eng.resume()})
        except UserError as e:
            return self._send(400, {"error": str(e)})
        except RouterError as e:
            return self._send(502, {"error": str(e), "code": e.code})
        return self._send(404, {"error": "Not found"})

    def _no(self):
        if not self._host_ok():
            return self._send(403, {"error": "Forbidden host"})
        self._send(405, {"error": "Method not allowed"})

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _no


def make_server(engine, tok_hash, port=8787):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)  # loopback only
    srv.daemon_threads = True
    real = srv.server_address[1]
    srv.engine, srv.token_hash = engine, tok_hash
    srv.allowed_hosts = {"127.0.0.1:%d" % real, "localhost:%d" % real}
    srv.allowed_origins = {"http://127.0.0.1:%d" % real, "http://localhost:%d" % real}
    return srv


