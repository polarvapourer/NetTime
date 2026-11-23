"""Private durable storage: POSIX modes or Windows DACLs, with atomic replace."""
import json
import os
import stat
import sys
import tempfile

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
    check_storage_path(path, directory=True)
    restrict(path, directory=True)


def check_storage_path(path, directory=False):
    info = os.lstat(path)
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if (not expected(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            or (not directory and info.st_nlink != 1)):
        raise ValueError("Expected an ordinary private %s at %s" % ("directory" if directory else "file", path))
    if os.name != "nt" and info.st_uid != os.geteuid():
        raise ValueError("NetTime account must own %s" % path)
    return info


def atomic_write_json(path, obj):
    parent = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            restrict(tmp)
            json.dump(obj, f, indent=1, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    try:
        dfd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError:
        pass


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def private_ok(path, want):
    try:
        info = check_storage_path(path, directory=want == 0o700)
        if os.name == "nt":
            from .windows_acl import private_ok as acl_ok
            return acl_ok(path)
        return stat.S_IMODE(info.st_mode) == want
    except (ValueError, OSError):
        return False


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

    def _load(self, path, default):
        try:
            check_storage_path(self.dir, directory=True)
            check_storage_path(path)
        except FileNotFoundError:
            return default
        if not private_ok(self.dir, 0o700) or not private_ok(path, 0o600):
            raise ValueError("NetTime data must be private to the controller account: %s" % path)
        return read_json(path)

    def load_config(self):
        cfg = self._load(self.config_path, {})
        if not isinstance(cfg, dict):
            raise ValueError("config.json must be an object")
        return cfg or None

    def save_config(self, cfg):
        self.init()
        atomic_write_json(self.config_path, cfg)

    def load_state(self):
        st = self._load(self.state_path, default_state())
        if not isinstance(st, dict):
            raise ValueError("state.json must be an object")
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
