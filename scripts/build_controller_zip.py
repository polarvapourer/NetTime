#!/usr/bin/env python3
"""Reproducible build of public/downloads/nettime-controller.zip from controller/ (no data, no credentials).

Usage: python3 scripts/build_controller_zip.py [output.zip]
Without an argument writes public/downloads/nettime-controller.zip AND nettime-controller-<VERSION>.zip (identical bytes).
"""
import hashlib
import os
import re
import stat
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "controller")
OUT = os.path.join(ROOT, "public", "downloads", "nettime-controller.zip")
FORBIDDEN_NAMES = re.compile(r"(config|state)\.json$|\.tmp$|\.env|\.git|__pycache__|\.pyc$|token|\.pem$|\.key$", re.I)
SECRET_CONTENT = re.compile(r"Basic [A-Za-z0-9+/]{12,}={0,2}|X-JNAP-Authorization\s*[:=]\s*['\"]Basic [A-Za-z0-9+/]")
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
PACKAGE_FILES = {
    "README.md", "ROUTERS.md", "install-service.sh", "install-service.ps1",
    "nettime/static/index.html", "nettime/static/app.css", "nettime/static/app.js",
    "examples/router_driver.py", "tests/fakes.py",
}
PACKAGE_PATTERNS = {"nettime": re.compile(r"nettime/[A-Za-z_][A-Za-z0-9_]*\.py"),
                    "tests": re.compile(r"tests/test_[A-Za-z0-9_]+\.py")}


def version():
    with open(os.path.join(SRC, "nettime", "__init__.py")) as f:
        m = re.search(r'^VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"$', f.read(), re.M)
    if not m:
        raise ValueError("VERSION not found")
    return m.group(1)


def versioned_path(v=None):
    return os.path.join(os.path.dirname(OUT), "nettime-controller-%s.zip" % (v or version()))


def checked_path(rel, directory=False):
    path = os.path.join(SRC, rel)
    info = os.lstat(path)
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if (not expected(info.st_mode) or (not directory and info.st_nlink != 1)
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ValueError("Package entries must be ordinary files and directories: " + rel)
    return path


def collect():
    for rel in (".", "nettime", "nettime/static", "examples", "tests"):
        checked_path(rel, directory=True)
    names = set(PACKAGE_FILES)
    for folder, pattern in PACKAGE_PATTERNS.items():
        names.update(rel for rel in (folder + "/" + name for name in os.listdir(os.path.join(SRC, folder)))
                     if pattern.fullmatch(rel) and not FORBIDDEN_NAMES.search(rel))
    for rel in names:
        checked_path(rel)
    return sorted(names)


def verify(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or set(names) != set(collect()):
            raise ValueError("Controller ZIP members differ from the package file list")
        for n in names:
            data = z.read(n).decode("utf-8")
            if SECRET_CONTENT.search(data):
                raise ValueError("Credential-like content in " + n)
        if not {"nettime/__main__.py", "nettime/service.py", "tests/test_engine.py"}.issubset(names):
            raise ValueError("Required controller source or tests are missing")
    return names


def build(out=OUT):
    parent = os.path.dirname(out) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".nettime-", suffix=".part", dir=parent)
    try:
        with os.fdopen(fd, "w+b") as packaged:
            with zipfile.ZipFile(packaged, "w", zipfile.ZIP_DEFLATED) as z:
                for rel in collect():
                    info = zipfile.ZipInfo(rel, FIXED_TIME)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.create_system = 3  # Preserve the same Unix mode metadata on every build host.
                    info.external_attr = ((0o755 if rel.endswith(".sh") else 0o644) | 0o100000) << 16
                    with open(checked_path(rel), "rb") as f:
                        z.writestr(info, f.read())
        names = verify(tmp)
        os.chmod(tmp, 0o644)
        os.replace(tmp, out)
        return names
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def publish_copy(path, data):
    fd, tmp = tempfile.mkstemp(prefix=".nettime-", suffix=".part", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def build_release():
    names = build(OUT)
    vp = versioned_path()
    with open(OUT, "rb") as f:
        data = f.read()
    publish_copy(vp, data)
    # Preserve the old stable download URL for existing bookmarks.
    publish_copy(os.path.join(os.path.dirname(OUT), "nettime-pi.zip"), data)
    digest = "%s  %s\n" % (hashlib.sha256(data).hexdigest(), os.path.basename(vp))
    publish_copy(os.path.join(os.path.dirname(OUT), "SHA256SUMS.txt"), digest.encode("ascii"))
    return names


if __name__ == "__main__":
    names = build(sys.argv[1]) if len(sys.argv) > 1 else build_release()
    print("%d files" % len(names))
    for n in names:
        print("  " + n)
