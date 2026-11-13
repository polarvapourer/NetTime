#!/usr/bin/env python3
"""Reproducible build of public/downloads/nettime-controller.zip from controller/ (no data, no credentials).

Usage: python3 scripts/build_controller_zip.py [output.zip]
Without an argument writes public/downloads/nettime-controller.zip AND nettime-controller-<VERSION>.zip (identical bytes).
"""
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "controller")
OUT = os.path.join(ROOT, "public", "downloads", "nettime-controller.zip")
ALLOWED_EXT = {".py", ".html", ".js", ".css", ".md", ".sh", ".ps1"}
FORBIDDEN_NAMES = re.compile(r"(config|state)\.json$|\.tmp$|\.env|\.git|__pycache__|\.pyc$|token|\.pem$|\.key$", re.I)
SECRET_CONTENT = re.compile(r"Basic [A-Za-z0-9+/]{12,}={0,2}|X-JNAP-Authorization\s*[:=]\s*['\"]Basic [A-Za-z0-9+/]")
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def version():
    with open(os.path.join(SRC, "nettime", "__init__.py")) as f:
        m = re.search(r'^VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"$', f.read(), re.M)
    assert m, "VERSION not found"
    return m.group(1)


def versioned_path(v=None):
    return os.path.join(os.path.dirname(OUT), "nettime-controller-%s.zip" % (v or version()))


def collect():
    out = []
    for base, dirs, files in os.walk(SRC):
        dirs[:] = sorted(d for d in dirs if d not in ("__pycache__", "data") and not d.startswith("."))
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(base, f), SRC).replace(os.sep, "/")
            if os.path.splitext(f)[1] in ALLOWED_EXT and not FORBIDDEN_NAMES.search(rel):
                out.append(rel)
    return sorted(out)


def verify(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for n in names:
            assert not FORBIDDEN_NAMES.search(n), "forbidden entry " + n
            assert not n.startswith("/") and ".." not in n.split("/"), "unsafe path " + n
            data = z.read(n).decode("utf-8")
            assert not SECRET_CONTENT.search(data), "credential-like content in " + n
        for need in ("nettime/__main__.py", "nettime/static/index.html", "install-service.sh", "install-service.ps1", "nettime/service.py", "README.md", "ROUTERS.md", "examples/router_driver.py", "tests/test_engine.py"):
            assert need in names, "missing " + need
    return names


def build(out=OUT):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".part"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in collect():
            info = zipfile.ZipInfo(rel, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((0o755 if rel.endswith(".sh") else 0o644) | 0o100000) << 16
            with open(os.path.join(SRC, rel), "rb") as f:
                z.writestr(info, f.read())
    os.replace(tmp, out)
    return verify(out)


def build_release():
    names = build(OUT)
    vp = versioned_path()
    with open(OUT, "rb") as f:
        data = f.read()
    with open(vp + ".part", "wb") as f:
        f.write(data)
    os.replace(vp + ".part", vp)
    verify(vp)
    # Preserve the old stable download URL for existing bookmarks.
    with open(os.path.join(os.path.dirname(OUT), "nettime-pi.zip"), "wb") as f:
        f.write(data)
    return names


if __name__ == "__main__":
    names = build(sys.argv[1]) if len(sys.argv) > 1 else build_release()
    print("%d files" % len(names))
    for n in names:
        print("  " + n)
