"""Linksys JNAP client for the owner's router, with certificate pinning.

Request/body formats come from the router's own web app (see README). Only a fixed
allowlist of actions is ever sent; nothing echoes router error text, which can contain
the supplied credentials.
"""
import base64
import hashlib
import hmac
import http.client
import ipaddress
import json
import re
import socket
import ssl

from .macs import canonical_mac, is_unicast

JNAP = "http://linksys.com/jnap/"
ACTIONS = {
    "GetMACFilterSettings": JNAP + "macfilter/GetMACFilterSettings",
    "SetMACFilterSettings": JNAP + "macfilter/SetMACFilterSettings",
    "GetDevices3": JNAP + "devicelist/GetDevices3",
    "GetDevices": JNAP + "devicelist/GetDevices",
    "GetLocalDevice": JNAP + "devicelist/GetLocalDevice",
}
AUTH_RESULTS = {"_ErrorUnauthorized"}
# Assumed names for "this action does not exist" (not observed live).
UNKNOWN_ACTION_RESULTS = {"_ErrorUnknownAction", "_ErrorInvalidAction", "_ErrorUnsupportedAction"}
MAX_RESPONSE = 4 * 1024 * 1024
_RESULT = re.compile(r"^_?[A-Za-z]{1,64}$")


class RouterError(Exception):
    """code: network | timeout | tls-pin | auth | http | unknown-action | router-result | schema | refused"""

    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code = code


class PinMismatch(RouterError):
    def __init__(self):
        RouterError.__init__(self, "tls-pin", "Router certificate changed. Communication stopped; run 'setup' again to re-enrol.")


def validate_router_host(host):
    ip = ipaddress.ip_address(host)
    if ip.version != 4 or not ip.is_private or ip.is_loopback or ip.is_link_local:
        raise ValueError("Router address must be a private IPv4 address such as 192.168.1.1")
    return str(ip)


def basic_auth_header(password):
    """Same construction as the router's web app: 'Basic ' + base64('admin:' + password)."""
    return "Basic " + base64.b64encode(("admin:" + password).encode("utf-8")).decode("ascii")


def check_pasted_header(value):
    if not value.startswith("Basic "):
        raise ValueError("Expected a value starting with 'Basic '")
    try:
        raw = base64.b64decode(value[6:].strip(), validate=True).decode("utf-8")
    except Exception:
        raise ValueError("Header is not valid base64")
    if not raw.startswith("admin:"):
        raise ValueError("Header does not look like this router's login")
    return "Basic " + value[6:].strip()


def _context():
    # Trust is established by the pinned SHA-256 fingerprint, checked before any credential is sent.
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fingerprint(der):
    return hashlib.sha256(der or b"").hexdigest()


def pretty_fp(fp):
    return ":".join(fp[i:i + 2] for i in range(0, len(fp), 2)).upper()


def fetch_cert_fingerprint(host, timeout=8):
    """Connect without sending any request or credential and return the certificate's SHA-256."""
    conn = http.client.HTTPSConnection(validate_router_host(host), 443, timeout=timeout, context=_context())
    try:
        conn.connect()
        return fingerprint(conn.sock.getpeercert(binary_form=True))
    finally:
        conn.close()


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, pin, timeout):
        http.client.HTTPSConnection.__init__(self, host, 443, timeout=timeout, context=_context())
        self._pin = pin

    def connect(self):
        http.client.HTTPSConnection.connect(self)
        got = fingerprint(self.sock.getpeercert(binary_form=True))
        if not hmac.compare_digest(got, self._pin):
            try:
                self.sock.close()
            finally:
                self.sock = None
            raise PinMismatch()


class HttpsTransport(object):
    """POST https://<router>/JNAP/ on the same TLS socket whose pin was verified. No proxies, no redirects."""

    def __init__(self, host, pin, auth_header, timeout=8):
        self.host = validate_router_host(host)
        self.pin = pin
        self._auth = auth_header
        self.timeout = timeout

    def post(self, action, body):
        url = ACTIONS[action]
        conn = PinnedHTTPSConnection(self.host, self.pin, self.timeout)
        try:
            conn.connect()  # pin checked here, before the request (and its auth header) exists
            conn.request("POST", "/JNAP/", body=json.dumps(body).encode("utf-8"), headers={
                "Content-Type": "application/json; charset=UTF-8",
                "X-JNAP-Action": url, "X-JNAP-Authorization": self._auth})
            resp = conn.getresponse()
            status = resp.status
            data = resp.read(MAX_RESPONSE + 1)
        except PinMismatch:
            raise
        except socket.timeout:
            raise RouterError("timeout", "Router did not answer in time")
        except (OSError, http.client.HTTPException):
            raise RouterError("network", "Could not reach the router")
        finally:
            conn.close()
        if status in (401, 403):
            raise RouterError("auth", "Router rejected the login")
        if status != 200:
            raise RouterError("http", "Router answered HTTP %d" % status)
        if len(data) > MAX_RESPONSE:
            raise RouterError("schema", "Router response too large")
        try:
            parsed = json.loads(data.decode("utf-8"))
        except ValueError:
            raise RouterError("schema", "Router response was not JSON")
        if not isinstance(parsed, dict):
            raise RouterError("schema", "Unexpected router response")
        return parsed


def _name(d):
    props = d.get("properties", [])
    if isinstance(props, list):
        for p in props:
            if isinstance(p, dict) and p.get("name") == "userDeviceName" and isinstance(p.get("value"), str) and p["value"].strip():
                return p["value"].strip()[:60]
    fn = d.get("friendlyName")
    return fn.strip()[:60] if isinstance(fn, str) and fn.strip() else "Unnamed device"


def parse_devices(output):
    """Parse GetDevices(3) output using the schema seen in the router's web app. Malformed -> RouterError."""
    devs = output.get("devices") if isinstance(output, dict) else None
    if not isinstance(devs, list):
        raise RouterError("schema", "Device list had an unexpected format")
    out = []
    for d in devs:
        if not isinstance(d, dict) or not isinstance(d.get("deviceID"), str):
            raise RouterError("schema", "Device entry had an unexpected format")
        conns = d.get("connections")  # required: a missing list means unknown, never "offline"
        ifaces = d.get("knownInterfaces", [])
        if not isinstance(conns, list) or not isinstance(ifaces, list):
            raise RouterError("schema", "Device entry had an unexpected format")
        conn_macs, iface_list = [], []
        for c in conns:
            mac = canonical_mac(c.get("macAddress")) if isinstance(c, dict) else None
            if mac is None:
                raise RouterError("schema", "Device connection had an unexpected format")
            conn_macs.append(mac)
        for k in ifaces:
            mac = canonical_mac(k.get("macAddress")) if isinstance(k, dict) else None
            if mac is None:
                raise RouterError("schema", "Device interface had an unexpected format")
            iface_list.append({"mac": mac, "type": str(k.get("interfaceType", ""))[:20], "band": str(k.get("band", ""))[:20]})
        out.append({"id": d["deviceID"][:80], "name": _name(d),
                    "macs": sorted(set(conn_macs) | set(i["mac"] for i in iface_list)),
                    "connectedMacs": sorted(set(conn_macs)), "online": len(conns) != 0,
                    "isAuthority": d.get("isAuthority") is True,
                    "nodeType": d.get("nodeType") if isinstance(d.get("nodeType"), str) else None,
                    "interfaces": iface_list})
    return out


class Router(object):
    def __init__(self, transport):
        self.t = transport

    def call(self, action, body=None):
        r = self.t.post(action, body or {})
        result = r.get("result")
        if result == "OK":
            out = r.get("output", {})
            return out if isinstance(out, dict) else {}
        code = result if isinstance(result, str) and _RESULT.match(result) else "unknown"
        if code in AUTH_RESULTS:
            raise RouterError("auth", "Router rejected the login")
        if code in UNKNOWN_ACTION_RESULTS:
            raise RouterError("unknown-action", "Router does not support this request")
        raise RouterError("router-result", "Router returned %s" % code)

    def get_filter(self):
        o = self.call("GetMACFilterSettings")
        mode, raw, cap = o.get("macFilterMode"), o.get("macAddresses"), o.get("maxMACAddresses")
        if not isinstance(mode, str) or not isinstance(raw, list) or not isinstance(cap, int) or isinstance(cap, bool) or cap < 0:
            raise RouterError("schema", "MAC filter settings had an unexpected format")
        macs = [canonical_mac(m) for m in raw]
        if any(m is None for m in macs):
            raise RouterError("schema", "MAC filter list contains an entry NetTime cannot read; not touching it")
        return {"mode": mode, "raw": list(raw), "macs": macs, "max": cap}

    def set_filter(self, mac_list):
        # Verified body from the router's web app; macFilterMode is always the existing Deny mode.
        self.call("SetMACFilterSettings", {"macFilterMode": "Deny", "macAddresses": mac_list})

    def get_devices(self):
        try:
            return parse_devices(self.call("GetDevices3"))
        except RouterError as e:
            if e.code != "unknown-action":
                raise
        return parse_devices(self.call("GetDevices"))

    def get_local_device_id(self):
        o = self.call("GetLocalDevice")
        return o.get("deviceID") if isinstance(o.get("deviceID"), str) else None


def apply_target(router, target, want_blocked):
    """Add/remove ONLY `target` in the Deny list, preserving every other entry, then read back.

    Returns dict(status=unchanged|confirmed|refused|write-failed|unconfirmed|readback-mismatch, message).
    """
    if not is_unicast(canonical_mac(target)):
        return {"status": "refused", "message": "Target is not a valid unicast MAC address"}
    f = router.get_filter()  # always a fresh read before any mutation
    if f["mode"] != "Deny":
        return {"status": "refused", "message": "Router MAC filter mode is %s, not Deny; NetTime will not change it" % f["mode"][:20]}
    present = target in f["macs"]
    if present == want_blocked:
        return {"status": "unchanged", "message": "Router already in the wanted state"}
    if want_blocked:
        if len(f["raw"]) >= f["max"]:
            return {"status": "refused", "message": "Router deny list is full"}
        new = f["raw"] + [target]
    else:
        new = [r for r, c in zip(f["raw"], f["macs"]) if c != target]
    others = sorted(c for c in f["macs"] if c != target)
    ambiguous = False
    try:
        router.set_filter(new)
    except PinMismatch:
        raise
    except RouterError as e:
        if e.code not in ("timeout", "network"):
            return {"status": "write-failed", "message": str(e)}
        ambiguous = True  # the write may or may not have happened: re-read, never repeat blindly
    try:
        g = router.get_filter()
    except RouterError as e:
        return {"status": "unconfirmed", "message": "Could not read back the router rule (%s)" % e.code}
    ok = (g["mode"] == "Deny" and (target in g["macs"]) == want_blocked
          and sorted(c for c in g["macs"] if c != target) == others)
    if ok:
        return {"status": "confirmed", "message": "Router rule confirmed" + (" after an unclear write" if ambiguous else "")}
    if ambiguous:
        return {"status": "unconfirmed", "message": "Write result unclear and readback does not show the change"}
    return {"status": "readback-mismatch", "message": "Router accepted the change but readback did not match"}
