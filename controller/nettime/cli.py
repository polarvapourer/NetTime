"""Command line: setup, doctor, serve, new-key."""
import argparse
import getpass
import os
import secrets
import signal
import subprocess
import sys
import threading

from . import VERSION
from .adapters import from_config
from .engine import POLL_SECONDS, Engine
from .host import ControllerLock, local_macs
from .service import manage
from .policy import init_tz, london
from .router import (HttpsTransport, Router, RouterError, basic_auth_header, check_pasted_header,
                     fetch_cert_fingerprint, pretty_fp, validate_router_host)
from .server import make_server, token_hash
from .store import DEFAULT_DIR, Store, private_ok, read_json


def _router(cfg):
    return from_config(cfg)


def _new_key(store, cfg):
    tok = secrets.token_urlsafe(32)
    cfg["tokenHash"] = token_hash(tok)
    store.save_config(cfg)
    print("\nYour NetTime access key (shown once - keep it private, like a password):\n\n  %s\n" % tok)
    print("Or open this link locally, or after starting an SSH tunnel (the key stays in your browser only):")
    print("  http://127.0.0.1:8787/#key=%s\n" % tok)


def cmd_setup(a, store):
    init_tz()
    store.init()
    previous = store.load_state()
    if previous["enforcement"] or previous["ownedBlock"] or previous["pending"]:
        raise ValueError("Turn blocking off and resolve any router block before changing setup")
    if a.adapter == 'command':
        return _setup_driver(a, store)
    host = validate_router_host(a.router)
    print("NetTime setup (read-only). Blocking stays OFF until you switch it on in the page.\n")
    fp = fetch_cert_fingerprint(host)
    print("Router %s certificate fingerprint (SHA-256):\n  %s" % (host, pretty_fp(fp)))
    if input("Pin this certificate for %s? Type yes: " % host).strip().lower() != "yes":
        print("Stopped. Nothing saved.")
        return 1
    if a.paste_header:
        auth = check_pasted_header(getpass.getpass("Paste X-JNAP-Authorization value (hidden): ").strip())
    else:
        auth = basic_auth_header(getpass.getpass("Router admin password (hidden): "))
    try:
        f = Router(HttpsTransport(host, fp, auth)).get_filter()
    except RouterError as e:
        print("Router test failed: %s. Nothing saved." % e)
        return 1
    print("Read test OK: MAC filter mode %s, %d entr%s in the list." % (f["mode"], len(f["macs"]), "y" if len(f["macs"]) == 1 else "ies"))
    old = store.load_config() or {}
    cfg = {"adapter": "linksys-jnap", "host": host, "pin": fp, "auth": auth, "tokenHash": old.get("tokenHash")}
    store.save_config(cfg)
    if not st_exists(store):
        store.save_state(store.load_state())
    if not cfg["tokenHash"] or a.new_key:
        _new_key(store, cfg)
    else:
        print("Kept your existing access key (use 'python3 -m nettime new-key' if lost).")
    print("Next: python -m nettime serve (or python -m nettime service install).")
    print("Use the same Python command you used for setup: py -3 on Windows, python3 on macOS/Linux.")
    return 0


def _setup_driver(a, store):
    if not a.driver or not a.driver_config:
        raise ValueError('Command adapter requires --driver and --driver-config. Read docs/ROUTERS.md.')
    driver = os.path.abspath(os.path.expanduser(a.driver))
    config_path = os.path.abspath(os.path.expanduser(a.driver_config))
    if not private_ok(config_path, 0o600):
        raise ValueError('Driver configuration must be private to your account; see ROUTERS.md')
    config = read_json(config_path)
    if not isinstance(config, dict):
        raise ValueError('Driver config must be a JSON object')
    print('This runs your trusted local router driver. Setup performs reads only.')
    cfg = {'adapter': 'command', 'driver': driver, 'driverConfig': config,
           'tokenHash': (store.load_config() or {}).get('tokenHash')}
    router = _router(cfg)
    f = router.get_filter()
    if f['mode'] != 'Deny':
        raise ValueError('Driver/router must expose a supported Deny policy; nothing saved')
    router.get_devices()
    router.get_local_device_id()
    store.save_config(cfg)
    if not st_exists(store):
        store.save_state(store.load_state())
    if not cfg['tokenHash'] or a.new_key:
        _new_key(store, cfg)
    print('Read tests passed. This does not prove traffic enforcement. Test block AND restore before relying on it.')
    print('Next: serve, then optionally service install, using this Python command.')
    return 0


def st_exists(store):
    return os.path.exists(store.state_path)


def cmd_new_key(a, store):
    cfg = store.load_config()
    if not cfg:
        print("Run setup first.")
        return 1
    _new_key(store, cfg)
    print("Restart the controller to use it: python -m nettime service restart, or restart foreground serve.")
    return 0


def cmd_doctor(a, store):
    ok = True
    v = sys.version_info
    print("NetTime %s, Python %d.%d.%d" % (VERSION, v[0], v[1], v[2]))
    if v < (3, 7):
        print("  FAIL Python 3.7 or newer is required"); ok = False
    elif v < (3, 10):
        print("  NOTE Legacy Python compatibility; use a currently supported Python and OS for a new installation.")
    print("  INFO Data directory: %s" % store.dir)
    macs = local_macs()
    print("  %s Host interface identity%s" % ("OK  " if macs else "WARN", " detected" if macs else " unavailable; router identity is required before enabling"))
    try:
        init_tz()
        print("  OK   London time now: %s" % london(__import__("time").time()))
    except RuntimeError as e:
        print("  FAIL %s" % e); ok = False
    cfg = store.load_config()
    if not cfg:
        print("  --   Not set up yet (run: python3 -m nettime setup)")
        return 0 if ok else 1
    paths = [(store.dir, 0o700), (store.config_path, 0o600)]
    if os.path.exists(store.state_path):
        paths.append((store.state_path, 0o600))
    for p, want in paths:
        good = private_ok(p, want)
        ok = ok and good
        print("  %s permissions %s" % ("OK  " if good else "FAIL", p))
    try:
        st = store.load_state()
        print("  OK   Saved state readable; blocking switch is %s" % ("ON" if st["enforcement"] else "OFF"))
    except Exception as e:
        print("  FAIL state: %s" % e); ok = False
    r = _router(cfg)
    try:
        f = r.get_filter()
        print("  OK   Router login and read work (mode %s, %d entries)" % (f["mode"], len(f["macs"])))
        try:
            devs = r.get_devices()
            print("  OK   Device list readable (%d devices)" % len(devs))
        except RouterError as e:
            print("  WARN Device list: %s" % e)
    except RouterError as e:
        print("  FAIL Router: %s" % e); ok = False
    return 0 if ok else 1


def cmd_serve(a, store):
    store.init()
    with ControllerLock(store.dir):
        return _serve(a, store)


def _serve(a, store):
    init_tz()
    cfg = store.load_config()
    if not cfg or not cfg.get("tokenHash"):
        print("Run setup first.")
        return 1
    eng = Engine(store, _router(cfg))
    srv = make_server(eng, cfg["tokenHash"], a.port)
    stop = threading.Event()

    def loop():
        delay = POLL_SECONDS
        while not stop.is_set():
            try:
                good = eng.tick()
            except Exception as e:  # keep running; never print request data
                print("tick error: %s" % type(e).__name__, flush=True)
                good = False
            delay = POLL_SECONDS if good else min(max(delay * 2, POLL_SECONDS), 120)
            stop.wait(delay)

    worker = threading.Thread(target=loop, daemon=True)
    worker.start()

    def on_term(*_):
        stop.set()
        threading.Thread(target=srv.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, on_term)
    print("NetTime serving on http://127.0.0.1:%d (loopback only)" % a.port, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        srv.server_close()
        worker.join()
    return 0


def cmd_service(a, store):
    if a.action in ("stop", "remove"):
        print("Turn blocking OFF and confirm access has returned first. Stopping does not remove router rules.")
    return manage(a.action, store)


def main(argv=None):
    p = argparse.ArgumentParser(prog="nettime")
    p.add_argument("--data-dir", default=os.environ.get("NETTIME_DATA", DEFAULT_DIR))
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("setup", help="pin router certificate, check login (read-only), create access key")
    s.add_argument("--router", default="192.168.1.1")
    s.add_argument('--adapter', choices=('linksys-jnap', 'command'), default='linksys-jnap')
    s.add_argument('--driver', help='absolute path to a trusted local driver (.py or executable)')
    s.add_argument('--driver-config', help='path to a private JSON object for that driver')
    s.add_argument("--paste-header", action="store_true", help="enter a copied login header (hidden) instead of the password")
    s.add_argument("--new-key", action="store_true")
    sub.add_parser("doctor", help="read-only checks")
    sv = sub.add_parser("serve", help="run scheduler and local page")
    sv.add_argument("--port", type=int, default=8787)
    sub.add_parser("new-key", help="replace the access key")
    service = sub.add_parser("service", help="manage native background startup")
    service.add_argument("action", choices=("install", "start", "stop", "restart", "status", "remove"))
    a = p.parse_args(argv)
    store = Store(os.path.abspath(os.path.expanduser(a.data_dir)))
    fn = {"setup": cmd_setup, "doctor": cmd_doctor, "serve": cmd_serve, "new-key": cmd_new_key, "service": cmd_service}.get(a.cmd)
    if not fn:
        p.print_help()
        return 2
    try:
        return fn(a, store)
    except RouterError as e:
        print("Router: %s" % e)
        return 1
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        print("Error: %s" % e)
        return 1
