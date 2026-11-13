"""Private durable storage: POSIX modes or Windows DACLs, with atomic replace."""
import json
import os
import stat
import sys

from .policy import default_settings, validate_settings
from .macs import canonical_mac

def default_dir():
    home = os.path.expanduser("~")
    legacy = os.path.join(home, ".local", "share", "nettime")
    # Never silently abandon a previous installation's credentials or block ownership.
    if os.path.isfile(os.path.join(legacy, "config.json")):
        return legacy
    if os.name == "nt":
        return os.path.join(os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local")), "NetTime")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", "NetTime")
    return legacy


DEFAULT_DIR = default_dir()


def restrict(path, directory=False):
    if os.name == "nt":
        from .windows_acl import protect
        protect(path, directory)
    else:
        os.chmod(path, 0o700 if directory else 0o600)


def ensure_private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    restrict(path, directory=True)


def atomic_write_json(path, obj):
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    restrict(tmp)
    os.replace(tmp, path)
    try:
        dfd = os.open(os.path.dirname(path) or ".", os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError:
        pass


def read_json(path):
    with open(path) as f:
        return json.load(f)


def private_ok(path, want):
    if os.name == "nt":
        from .windows_acl import private_ok as acl_ok
        return acl_ok(path)
    return stat.S_IMODE(os.stat(path).st_mode) == want


def default_state():
    return {"version": 1, "settings": default_settings(), "target": None, "targetName": None,
            "enforcement": False, "paused": None, "ownedBlock": False, "expectedBlocked": None,
            "bonus": None, "usage": {}, "chargedUntil": 0.0, "pending": None}


class Store(object):
    def __init__(self, data_dir):
        self.dir = data_dir
        self.config_path = os.path.join(data_dir, "config.json")
        self.state_path = os.path.join(data_dir, "state.json")

    def init(self):
        ensure_private_dir(self.dir)

    def load_config(self):
        return read_json(self.config_path) if os.path.exists(self.config_path) else None

    def save_config(self, cfg):
        self.init()
        atomic_write_json(self.config_path, cfg)

    def load_state(self):
        if not os.path.exists(self.state_path):
            return default_state()
        st = read_json(self.state_path)  # corrupt file -> error (fail closed, usage is never silently reset)
        s, errs = validate_settings(st.get("settings"))
        if errs or not isinstance(st.get("usage"), dict):
            raise ValueError("state.json is invalid: " + "; ".join(errs))
        base = default_state()
        base.update(st)
        base["settings"] = s
        if base["target"] is not None and canonical_mac(base["target"]) != base["target"]:
            raise ValueError("state.json target is invalid")
        return base

    def save_state(self, st):
        self.init()
        atomic_write_json(self.state_path, st)
