"""Checks the ZIP build (only runs inside the full project, where scripts/ exists)."""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "build_pi_zip.py")


@unittest.skipUnless(os.path.exists(SCRIPT), "build script not present (installed copy)")
class Archive(unittest.TestCase):
    def build(self, d, name):
        out = os.path.join(d, name)
        subprocess.check_call([sys.executable, SCRIPT, out], stdout=subprocess.DEVNULL)
        return out

    def test_reproducible_and_clean(self):
        d = tempfile.mkdtemp()
        data_dir = os.path.join(os.path.dirname(SCRIPT), "..", "controller", "data")
        a = self.build(d, "a.zip")
        b = self.build(d, "b.zip")
        def h(p):
            with open(p, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(h(a), h(b))
        with zipfile.ZipFile(a) as z:
            names = z.namelist()
        self.assertFalse(any(n.endswith((".json", ".pyc")) or "__pycache__" in n for n in names))
        self.assertFalse(os.path.exists(data_dir))

    def test_versioned_download_matches_stable(self):
        root = os.path.join(os.path.dirname(SCRIPT), "..")
        with open(os.path.join(root, "controller", "nettime", "__init__.py")) as f:
            v = [l.split('"')[1] for l in f if l.startswith("VERSION")][0]
        dl = os.path.join(root, "public", "downloads")
        with open(os.path.join(dl, "nettime-controller.zip"), "rb") as a, open(os.path.join(dl, "nettime-controller-%s.zip" % v), "rb") as b:
            self.assertEqual(a.read(), b.read())
        with open(os.path.join(dl, "SHA256SUMS.txt")) as f:
            digest, filename = f.read().split()
        self.assertEqual(filename, "nettime-controller-%s.zip" % v)
        with open(os.path.join(dl, filename), "rb") as f:
            self.assertEqual(digest, hashlib.sha256(f.read()).hexdigest())


if __name__ == "__main__":
    unittest.main()
