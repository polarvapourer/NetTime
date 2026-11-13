#!/usr/bin/env python3
"""Compatibility alias. Prefer build_controller_zip.py for new instructions."""
from build_controller_zip import build, build_release
import sys

if __name__ == "__main__":
    names = build(sys.argv[1]) if len(sys.argv) > 1 else build_release()
    print("%d files" % len(names))
