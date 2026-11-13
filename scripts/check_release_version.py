#!/usr/bin/env python3
"""Verify NetTime's public version convention and source-version consistency."""
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent


def check():
    package = json.loads((ROOT / 'package.json').read_text())
    lock = json.loads((ROOT / 'package-lock.json').read_text())
    match = re.search(r'^VERSION = "([^"]+)"$', (ROOT / 'controller/nettime/__init__.py').read_text(), re.M)
    version = package['version']
    if not re.fullmatch(r'1\.(0|[1-9][0-9]*)\.0', version):
        raise ValueError('Public releases must use 1.x.0, for example 1.2.0')
    if not match or any(v != version for v in [match.group(1), lock['version'], lock['packages']['']['version']]):
        raise ValueError('Package, lockfile and controller versions disagree')
    if os.environ.get('GITHUB_REF_TYPE') == 'tag' and os.environ.get('GITHUB_REF_NAME') != 'v' + version:
        raise ValueError('Release tag does not match the program version')
    print('Release version consistent: v' + version)
    return version


if __name__ == '__main__':
    check()
