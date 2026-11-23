"""Python 3.7 compatibility guard (grammar + APIs newer than 3.7)."""
import ast
import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BANNED = [r"\bzoneinfo\b", r"\.removeprefix\(", r"\.removesuffix\(", r"functools\.cache\b", r"cached_property",
          r"math\.isqrt", r"\bimport tomllib", r"\bgraphlib\b", r"list\[", r"dict\[", r"tuple\[", r"\bmatch \w+:", r":=",
          r"from typing import .*(Literal|Protocol|TypedDict|Final)", r"\bimportlib\.metadata\b", r"shlex\.join"]


def sources():
    for base, _, files in os.walk(ROOT):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(base, f)


class Compat(unittest.TestCase):
    def test_grammar_37(self):
        for p in sources():
            with open(p) as f:
                ast.parse(f.read(), p, feature_version=(3, 7))

    def test_no_newer_apis_or_third_party(self):
        allowed_local = {"nettime", "fakes", "test_policy"}
        for p in sources():
            if p.endswith("test_compat.py"):
                continue
            with open(p) as fh:
                src = fh.read()
            for pat in BANNED:
                self.assertIsNone(re.search(pat, src), "%s uses %s" % (p, pat))
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module.split(".")[0]]
                else:
                    continue
                for n in names:
                    self.assertTrue(n in allowed_local or n in STDLIB, "%s imports %s" % (p, n))


STDLIB = {"argparse", "ast", "base64", "calendar", "copy", "getpass", "hashlib", "hmac", "http", "ipaddress", "json",
          "math", "os", "re", "secrets", "shutil", "signal", "socket", "ssl", "stat", "sys", "tempfile", "threading",
          "time", "unittest", "warnings", "zipfile", "subprocess", "io", "datetime", "ctypes", "plistlib", "fcntl", "msvcrt"}

if __name__ == "__main__":
    unittest.main()
