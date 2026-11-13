import http.client
import unittest

from nettime import router as R
from nettime.router import RouterError, apply_target, basic_auth_header, parse_devices
from fakes import IPAD, OTHER, make_router


class Adapter(unittest.TestCase):
    def test_block_preserves_others_and_reads_back(self):
        r, t = make_router(macs=["02-00-00-00-00-99", "AA:BB:CC:DD:EE:FF"])
        res = apply_target(r, IPAD, True)
        self.assertEqual(res["status"], "confirmed")
        self.assertEqual(t.writes()[0][1], {"macFilterMode": "Deny", "macAddresses": ["02-00-00-00-00-99", "AA:BB:CC:DD:EE:FF", IPAD]})
        self.assertEqual(t.posts[-1][0], "GetMACFilterSettings")  # readback after write
        res = apply_target(r, IPAD, False)
        self.assertEqual(t.macs, ["02-00-00-00-00-99", "AA:BB:CC:DD:EE:FF"])

    def test_unchanged_skips_write(self):
        r, t = make_router(macs=[OTHER])
        self.assertEqual(apply_target(r, IPAD, False)["status"], "unchanged")
        self.assertEqual(t.writes(), [])

    def test_wrong_mode_refused(self):
        for mode in ("Allow", "Disabled", "Weird"):
            r, t = make_router(mode=mode)
            self.assertEqual(apply_target(r, IPAD, True)["status"], "refused")
            self.assertEqual(t.writes(), [])

    def test_capacity_and_invalid(self):
        r, t = make_router(macs=[OTHER], cap=1)
        self.assertEqual(apply_target(r, IPAD, True)["status"], "refused")
        for bad in ("01:00:5E:00:00:01", "00:00:00:00:00:00", "nope"):
            self.assertEqual(apply_target(r, bad, True)["status"], "refused")
        self.assertEqual(t.writes(), [])

    def test_unreadable_entry_fails_closed(self):
        r, t = make_router(macs=["garbage"])
        with self.assertRaises(RouterError):
            apply_target(r, IPAD, True)
        self.assertEqual(t.writes(), [])

    def test_readback_mismatch(self):
        r, t = make_router()
        t.set_applies = False
        self.assertEqual(apply_target(r, IPAD, True)["status"], "readback-mismatch")

    def test_ambiguous_write_rereads_once_no_retry(self):
        r, t = make_router()
        t.set_timeout = True
        self.assertEqual(apply_target(r, IPAD, True)["status"], "confirmed")
        t2r, t2 = make_router()
        t2.set_timeout, t2.set_applies = True, False
        self.assertEqual(apply_target(t2r, IPAD, True)["status"], "unconfirmed")
        self.assertEqual(len(t2.writes()), 1)

    def test_auth_error_never_echoes(self):
        r, t = make_router()
        secret = basic_auth_header("hunter2")
        t.result["GetMACFilterSettings"] = {"result": "_ErrorUnauthorized", "error": "Invalid authorization credentials '%s'" % secret}
        with self.assertRaises(RouterError) as c:
            r.get_filter()
        self.assertEqual(c.exception.code, "auth")
        self.assertNotIn(secret[6:], str(c.exception))
        self.assertNotIn("hunter2", repr(c.exception.args))

    def test_basic_auth_format(self):
        self.assertEqual(basic_auth_header("pw"), "Basic YWRtaW46cHc=")


class Devices(unittest.TestCase):
    def test_parse_and_fallback(self):
        r, t = make_router()
        devs = r.get_devices()
        ipad = [d for d in devs if d["id"] == "ipad"][0]
        self.assertEqual(ipad["name"], "Demo tablet")
        self.assertTrue(ipad["online"])
        t.result["GetDevices3"] = {"result": "_ErrorUnknownAction"}
        t.result["GetDevices"] = {"result": "OK", "output": {"devices": []}}
        self.assertEqual(r.get_devices(), [])

    def test_no_fallback_on_auth(self):
        r, t = make_router()
        t.result["GetDevices3"] = {"result": "_ErrorUnauthorized"}
        with self.assertRaises(RouterError):
            r.get_devices()
        self.assertNotIn("GetDevices", [p[0] for p in t.posts])

    def test_malformed_rejected(self):
        for out in ({}, {"devices": [{"deviceID": "x", "connections": "no"}]},
                    {"devices": [{"deviceID": "x", "knownInterfaces": []}]},  # missing connections != offline
                    {"devices": [{"deviceID": "x", "connections": [{"macAddress": "zz"}]}]}):
            with self.assertRaises(RouterError):
                parse_devices(out)


class FakeSock(object):
    def __init__(self):
        self.sent = []

    def getpeercert(self, binary_form=False):
        return b"different-cert"

    def sendall(self, d):
        self.sent.append(d)

    def close(self):
        pass


class Pin(unittest.TestCase):
    def test_mismatch_fails_before_any_auth_is_sent(self):
        sock = FakeSock()
        orig = http.client.HTTPSConnection.connect

        def fake_connect(self):
            self.sock = sock
        http.client.HTTPSConnection.connect = fake_connect
        try:
            t = R.HttpsTransport("192.168.1.1", "0" * 64, basic_auth_header("secret"))
            with self.assertRaises(R.PinMismatch):
                t.post("GetMACFilterSettings", {})
        finally:
            http.client.HTTPSConnection.connect = orig
        self.assertEqual(sock.sent, [])

    def test_only_private_router_and_allowlisted_actions(self):
        for bad in ("8.8.8.8", "127.0.0.1", "example.com"):
            with self.assertRaises(ValueError):
                R.validate_router_host(bad)
        t = R.HttpsTransport("192.168.1.1", "0" * 64, "Basic x")
        with self.assertRaises(KeyError):
            t.post("http://evil/", {})


if __name__ == "__main__":
    unittest.main()
