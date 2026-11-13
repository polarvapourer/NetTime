"""Owner-only durable storage (directory 0700, files 0600, atomic replace)."""
import json
import os
import stat

from .policy import default_settings, validate_settings
from .macs import canonical_mac

DEFAULT_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "nettime")


def ensure_private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)


def atomic_write_json(path, obj):
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
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
