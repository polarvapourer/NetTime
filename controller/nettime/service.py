"""Native background startup. Windows/macOS jobs run while the owner is logged in."""
import os
import plistlib
import subprocess
import sys

LABEL = "io.nettime.controller"


def launch_agent(package_dir, data_dir, python):
    return {"Label": LABEL, "ProgramArguments": [python, "-m", "nettime", "--data-dir", data_dir, "serve"],
            "WorkingDirectory": package_dir, "RunAtLoad": True, "KeepAlive": True,
            "ThrottleInterval": 10, "Umask": 0o077,
            "StandardOutPath": os.path.join(data_dir, "service.log"),
            "StandardErrorPath": os.path.join(data_dir, "service-error.log")}


def _run(args, env=None, check=True):
    return subprocess.run(args, env=env, check=check).returncode


def manage(action, store):
    package = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if action == "install" and not store.load_config():
        raise ValueError("Run setup first, then install the background job")
    data = os.path.abspath(store.dir)
    if os.name == "nt":
        powershell = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
        return _run([powershell, "-NoProfile", "-NonInteractive", "-File", os.path.join(package, "install-service.ps1"),
                     "-Action", action, "-PythonExe", sys.executable, "-DataDir", data])
    if sys.platform == "darwin":
        agent_dir = os.path.expanduser("~/Library/LaunchAgents")
        path = os.path.join(agent_dir, LABEL + ".plist")
        domain = "gui/%s" % os.getuid()
        target = domain + "/" + LABEL
        if action == "install":
            store.init()
            os.makedirs(agent_dir, exist_ok=True)
            if os.path.exists(path):
                with open(path, "rb") as f:
                    existing = plistlib.load(f)
                if existing.get("Label") != LABEL or "nettime" not in existing.get("ProgramArguments", []):
                    raise ValueError("LaunchAgent exists and is not NetTime's; refusing to replace it")
            with open(path, "wb") as f:
                plistlib.dump(launch_agent(package, data, sys.executable), f)
            os.chmod(path, 0o600)
            _run(["launchctl", "bootout", target], check=False)
            return _run(["launchctl", "bootstrap", domain, path])
        if action == "remove":
            if not os.path.isfile(path):
                raise ValueError("NetTime LaunchAgent is not installed")
            with open(path, "rb") as f:
                existing = plistlib.load(f)
            if existing.get("Label") != LABEL or "nettime" not in existing.get("ProgramArguments", []):
                raise ValueError("Refusing to remove an unrelated LaunchAgent")
            _run(["launchctl", "bootout", target], check=False)
            os.remove(path)
            return 0
        if action == "stop":
            return _run(["launchctl", "bootout", target])
        if action == "start":
            return _run(["launchctl", "bootstrap", domain, path])
        if action == "restart":
            return _run(["launchctl", "kickstart", "-k", target])
        return _run(["launchctl", "print", target])
    if sys.platform.startswith("linux"):
        if action == "install":
            env = dict(os.environ, NETTIME_DATA=data, NETTIME_PYTHON=sys.executable)
            return _run(["sh", os.path.join(package, "install-service.sh")], env=env)
        if action == "remove":
            # Leave the small unit file in place; do not unlink a potentially replaced system file.
            return _run(["sudo", "systemctl", "disable", "--now", "nettime"])
        if action == "status":
            return _run(["systemctl", "--no-pager", "status", "nettime"], check=False)
        return _run(["sudo", "systemctl", action, "nettime"])
    raise ValueError("No native background installer for this OS; use 'serve' with your own supervisor")
