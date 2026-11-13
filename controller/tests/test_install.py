"""Runs the documented `sh ./install-service.sh` from a python-zipfile-extracted package,
with sudo/systemctl/id replaced by test doubles. Nothing is really installed."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "build_pi_zip.py")


@unittest.skipUnless(os.name != "nt" and os.path.exists(SCRIPT) and shutil.which("sh"), "needs full project and sh")
class Install(unittest.TestCase):
    def test_documented_invocation(self):
        d = tempfile.mkdtemp()
        try:
            z = os.path.join(d, "nettime-pi.zip")
            subprocess.check_call([sys.executable, SCRIPT, z], stdout=subprocess.DEVNULL)
            home, pkg, fake = os.path.join(d, "home"), os.path.join(d, "home", "nettime"), os.path.join(d, "bin")
            os.makedirs(os.path.join(home, ".local", "share", "nettime")); os.makedirs(fake)
            with open(os.path.join(home, ".local", "share", "nettime", "config.json"), "w") as f:
                f.write("{}")
            subprocess.check_call([sys.executable, "-m", "zipfile", "-e", z, pkg])
            self.assertFalse(os.access(os.path.join(pkg, "install-service.sh"), os.X_OK))  # why `sh ./` is documented
            log = os.path.join(d, "calls.log")
            doubles = {"sudo": '"$@"', "systemctl": 'echo "systemctl $*" >> "%s"' % log,
                       "id": 'case "$1" in -u) echo 1000;; -un) echo pi;; esac', "sleep": "true"}
            for name, body in doubles.items():
                p = os.path.join(fake, name)
                with open(p, "w") as f:
                    f.write("#!/bin/sh\n%s\n" % body)
                os.chmod(p, 0o755)
            unit = os.path.join(d, "nettime.service")
            env = dict(os.environ, HOME=home, PATH=fake + os.pathsep + os.environ["PATH"], NETTIME_UNIT_PATH=unit)
            env.pop("NETTIME_DATA", None)
            out = subprocess.run(["sh", "./install-service.sh"], cwd=pkg, env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            self.assertEqual(out.returncode, 0, out.stdout)
            with open(unit) as f:
                text = f.read()
            self.assertIn("User=pi", text)
            self.assertIn("-m nettime serve", text)
            self.assertIn("WorkingDirectory=" + '"%s"' % pkg, text)
            with open(log) as f:
                calls = f.read()
            self.assertIn("enable nettime", calls)
            self.assertIn("observation only", out.stdout)
            with open(unit, "w") as f:
                f.write("[Unit]\nDescription=something else\n")
            out = subprocess.run(["sh", "./install-service.sh"], cwd=pkg, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, universal_newlines=True)
            self.assertNotEqual(out.returncode, 0)  # never overwrites a foreign service
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
