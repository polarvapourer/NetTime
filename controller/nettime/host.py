"""Host identity and a process lock, without third-party dependencies."""
import os
import re
import subprocess
import sys

from .macs import canonical_mac, is_unicast
from .store import check_storage_path


def parse_macs(text):
    return {canonical_mac(m.group()) for m in re.finditer(
        r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])", text)
        if is_unicast(canonical_mac(m.group()))}


def local_macs():
    out = set()
    if sys.platform.startswith("linux"):
        try:
            for name in os.listdir("/sys/class/net"):
                try:
                    with open("/sys/class/net/%s/address" % name) as f:
                        out.update(parse_macs(f.read()))
                except OSError:
                    pass
        except OSError:
            pass
        return out
    command = ([os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "getmac.exe"), "/FO", "CSV", "/NH"]
               if os.name == "nt" else ["/sbin/ifconfig", "-a"])
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
        if result.returncode == 0:
            out.update(parse_macs(result.stdout.decode("utf-8", "replace")))
    except (OSError, subprocess.TimeoutExpired):
        pass
    return out


class ControllerLock(object):
    def __init__(self, directory):
        self.path = os.path.join(directory, "controller.lock")
        self.file = None

    def __enter__(self):
        try:
            check_storage_path(self.path)
        except FileNotFoundError:
            pass
        self.file = open(self.path, "a+b")
        try:
            self.file.seek(0, 2)
            if self.file.tell() == 0:
                self.file.write(b"0"); self.file.flush()
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close(); self.file = None
            raise ValueError("Another controller is already using this data directory")
        return self

    def __exit__(self, *_):
        if self.file:
            self.file.close()
            self.file = None
