"""TEST-ONLY mock router and clock. Nothing here talks to a real network."""
import calendar
import copy

from nettime.router import RouterError, Router

IPAD = "AA:11:22:33:44:55"
OTHER = "02:00:00:00:00:99"
PI = "B8:27:EB:00:00:01"
NODE = "C0:00:00:00:00:01"


def utc(y, mo, d, h, mi=0, s=0):
    return float(calendar.timegm((y, mo, d, h, mi, s)))


class FakeTransport(object):
    def __init__(self, mode="Deny", macs=None, cap=100, ipad_online=True):
        self.mode, self.macs, self.cap = mode, list(macs or []), cap
        self.posts = []
        self.ipad_online = ipad_online
        self.fail = {}        # action -> RouterError to raise once/always
        self.result = {}      # action -> raw response override
        self.set_applies = True
        self.set_timeout = False
        self.fail_get_after_set = False

    def writes(self):
        return [p for p in self.posts if p[0] == "SetMACFilterSettings"]

    def post(self, action, body):
        self.posts.append((action, copy.deepcopy(body)))
        if action in self.fail:
            raise self.fail[action]
        if action in self.result:
            return copy.deepcopy(self.result[action])
        if action == "GetMACFilterSettings":
            if self.fail_get_after_set and self.writes():
                self.fail_get_after_set = False
                raise RouterError("timeout", "Router did not answer in time")
            return {"result": "OK", "output": {"macFilterMode": self.mode, "macAddresses": list(self.macs), "maxMACAddresses": self.cap}}
        if action == "SetMACFilterSettings":
            if self.set_applies:
                self.macs = list(body["macAddresses"])
            if self.set_timeout:
                raise RouterError("timeout", "Router did not answer in time")
            return {"result": "OK"}
        if action == "GetDevices3":
            return {"result": "OK", "output": {"devices": [
                {"deviceID": "ipad", "friendlyName": "iPad", "properties": [{"name": "userDeviceName", "value": "Demo tablet"}],
                 "connections": [{"macAddress": IPAD.lower(), "ipAddress": "192.168.1.50", "isGuest": False}] if self.ipad_online else [],
                 "knownInterfaces": [{"macAddress": IPAD, "interfaceType": "Wireless", "band": "5GHz"}]},
                {"deviceID": "pi", "friendlyName": "raspberrypi", "connections": [{"macAddress": PI}],
                 "knownInterfaces": [{"macAddress": PI, "interfaceType": "Wired"}]},
                {"deviceID": "node", "friendlyName": "Router", "isAuthority": True, "nodeType": "Master",
                 "connections": [], "knownInterfaces": [{"macAddress": NODE}]},
            ]}}
        if action == "GetLocalDevice":
            return {"result": "OK", "output": {"deviceID": "pi"}}
        return {"result": "_ErrorUnknownAction"}


class Clock(object):
    def __init__(self, t):
        self.t = t
        self.m = 1000.0

    def wall(self):
        return self.t

    def mono(self):
        return self.m

    def advance(self, s, wall_only=False):
        self.t += s
        if not wall_only:
            self.m += s


def make_router(**kw):
    t = FakeTransport(**kw)
    return Router(t), t
