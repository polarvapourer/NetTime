"""Local page/API tests against a MOCK router (test-only, no real network)."""
import http.client
import json
import os
import shutil
import stat
import tempfile
import threading
import unittest

from nettime.engine import Engine
from nettime.policy import init_tz
from nettime.server import make_server, token_hash
from nettime.store import Store, private_ok
from fakes import IPAD, PI, Clock, make_router, utc

init_tz()
TOKEN = "test-token-only"


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.store = Store(cls.dir)
        r, cls.t = make_router()
        c = Clock(utc(2026, 11, 16, 15))
        cls.eng = Engine(cls.store, r, clock=c.wall, mono=c.mono, self_macs={PI})
        cls.srv = make_server(cls.eng, token_hash(TOKEN), 0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); shutil.rmtree(cls.dir)

    def req(self, method, path, body=None, headers=None, token=TOKEN, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": host or "127.0.0.1:%d" % self.port}
        if token:
            h["Authorization"] = "Bearer " + token
        if body is not None:
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        data = r.read()
        c.close()
        return r, data

    def test_bound_to_loopback(self):
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")

    def test_static_public_without_secrets(self):
        r, d = self.req("GET", "/", token=None)
        self.assertEqual(r.status, 200)
        self.assertIn(b"NetTime", d)
        self.assertIsNone(r.getheader("Access-Control-Allow-Origin"))
        for p in ("/app.js", "/app.css"):
            self.assertEqual(self.req("GET", p, token=None)[0].status, 200)
        for p in ("/config.json", "/../config.json", "/state.json", "/static/app.js", "/%2e%2e/etc/passwd"):
            self.assertEqual(self.req("GET", p, token=None)[0].status, 404)

    def test_api_requires_token(self):
        self.assertEqual(self.req("GET", "/api/status", token=None)[0].status, 401)
        self.assertEqual(self.req("GET", "/api/status", token="wrong")[0].status, 401)
        self.assertEqual(self.req("POST", "/api/enforcement", {"enabled": True}, token=None)[0].status, 401)
        self.assertEqual(self.req("GET", "/api/status?key=" + TOKEN, token=None)[0].status, 401)
        r, d = self.req("GET", "/api/status")
        self.assertEqual(r.status, 200)
        s = json.loads(d)
        self.assertTrue(s["observationOnly"])
        self.assertNotIn(b"auth", d.lower().replace(b"authority", b""))

    def test_host_and_origin(self):
        self.assertEqual(self.req("GET", "/api/status", host="evil.example:8787")[0].status, 403)
        self.assertEqual(self.req("GET", "/", host="192.0.2.10:%d" % self.port)[0].status, 403)
        r, _ = self.req("POST", "/api/bonus", {"minutes": 5}, headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status, 403)
        r, _ = self.req("POST", "/api/bonus/clear", {}, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(r.status, 403)
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request("POST", "/api/bonus", body="minutes=5", headers={"Host": "127.0.0.1:%d" % self.port, "Authorization": "Bearer " + TOKEN, "Content-Type": "text/plain"})
        self.assertEqual(c.getresponse().status, 415)
        self.assertEqual(self.req("OPTIONS", "/api/status")[0].status, 405)

    def test_import_export_and_no_auto_enable(self):
        settings = json.loads(self.req("GET", "/api/export")[1])
        settings["weekly"] = {d: 30 for d in settings["weekly"]}
        r, _ = self.req("POST", "/api/import", {"settings": settings}, headers={"Origin": "http://127.0.0.1:%d" % self.port})
        self.assertEqual(r.status, 200)
        self.req("POST", "/api/bonus", {"minutes": 10})
        exp = json.loads(self.req("GET", "/api/export")[1])
        self.assertEqual(set(exp), {"schemaVersion", "timezone", "deviceLabel", "weekly", "exceptions", "leisurePaused"})
        self.assertFalse(json.loads(self.req("GET", "/api/status")[1])["enforcement"])
        bad = dict(settings, weekly=dict(settings["weekly"], mon=5000))
        self.assertEqual(self.req("POST", "/api/import", {"settings": bad})[0].status, 400)
        self.assertEqual(self.t.writes(), [])

    def test_body_limit(self):
        self.assertEqual(self.req("POST", "/api/import", {"settings": "x" * 70000})[0].status, 413)

    def test_files_private(self):
        self.req("POST", "/api/bonus", {"minutes": 1})
        self.assertTrue(private_ok(self.dir, 0o700))
        self.assertTrue(private_ok(self.store.state_path, 0o600))


class UnselectApi(Server):
    def test_api_clear(self):
        self.eng.discover(); self.eng.select_target(IPAD, "iPad")
        self.assertEqual(self.req("POST", "/api/target/clear", {}, token=None)[0].status, 401)
        self.assertEqual(self.req("POST", "/api/target/clear", {}, host="evil:1")[0].status, 403)
        self.assertEqual(self.req("POST", "/api/target/clear", {}, headers={"Origin": "http://evil"})[0].status, 403)
        self.assertEqual(self.eng.st["target"], IPAD)
        r, _ = self.req("POST", "/api/target/clear", {"mac": "junk", "x": [1]})  # extra/invalid payload ignored
        self.assertEqual(r.status, 200)
        self.assertIsNone(self.eng.st["target"])
        self.assertEqual(self.req("POST", "/api/target/clear", {})[0].status, 200)  # idempotent
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request("POST", "/api/target/clear", body="[1]", headers={"Host": "127.0.0.1:%d" % self.port,
                  "Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
        self.assertEqual(c.getresponse().status, 400); c.close()
        self.assertEqual(self.req("GET", "/api/target/clear")[0].status, 404)
        self.eng.st["pending"] = {"want": True, "status": "present-unverified", "at": 1}
        self.eng.st["target"] = IPAD
        r, d = self.req("POST", "/api/target/clear", {})
        self.assertEqual(r.status, 400); self.assertIn(b"unresolved", d)
        self.assertEqual(self.eng.st["target"], IPAD)
        self.eng.st["pending"] = None



if __name__ == "__main__":
    unittest.main()
