"""Command line: setup, doctor, serve, new-key."""
import argparse
import getpass
import os
import secrets
import signal
import sys
import threading

from . import VERSION
from .engine import POLL_SECONDS, Engine
from .policy import init_tz, london
from .router import (HttpsTransport, Router, RouterError, basic_auth_header, check_pasted_header,
                     fetch_cert_fingerprint, pretty_fp, validate_router_host)
from .server import make_server, token_hash
from .store import DEFAULT_DIR, Store, private_ok


def _router(cfg):
    return Router(HttpsTransport(cfg["host"], cfg["pin"], cfg["auth"])) if cfg else None


def _new_key(store, cfg):
    tok = secrets.token_urlsafe(32)
    cfg["tokenHash"] = token_hash(tok)
    store.save_config(cfg)
    print("\nYour NetTime access key (shown once - keep it private, like a password):\n\n  %s\n" % tok)
    print("Or open this link after starting the SSH tunnel (the key stays in your browser only):")
    print("  http://127.0.0.1:8787/#key=%s\n" % tok)


def cmd_setup(a, store):
    init_tz()
    store.init()
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
    cfg = {"host": host, "pin": fp, "auth": auth, "tokenHash": old.get("tokenHash")}
    store.save_config(cfg)
    if not st_exists(store):
        store.save_state(store.load_state())
    if not cfg["tokenHash"] or a.new_key:
        _new_key(store, cfg)
    else:
        print("Kept your existing access key (use 'python3 -m nettime new-key' if lost).")
    print("Next: sh ./install-service.sh")
    return 0


def st_exists(store):
    return os.path.exists(store.state_path)


def cmd_new_key(a, store):
    cfg = store.load_config()
    if not cfg:
        print("Run setup first.")
        return 1
    _new_key(store, cfg)
    print("Restart the service to use it: sudo systemctl restart nettime")
    return 0


def cmd_doctor(a, store):
    ok = True
    v = sys.version_info
    print("NetTime %s, Python %d.%d.%d" % (VERSION, v[0], v[1], v[2]))
    if v < (3, 7):
        print("  FAIL Python 3.7 or newer is required"); ok = False
    elif v < (3, 9):
        print("  NOTE This Python/OS is end-of-life. Fine for testing; a supported Raspberry Pi OS Lite on a separate microSD is recommended long-term.")
    try:
        init_tz()
        print("  OK   London time now: %s" % london(__import__("time").time()))
    except RuntimeError as e:
        print("  FAIL %s" % e); ok = False
    cfg = store.load_config()
    if not cfg:
        print("  --   Not set up yet (run: python3 -m nettime setup)")
        return 0 if ok else 1
    for p, want in ((store.dir, 0o700), (store.config_path, 0o600)):
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

    threading.Thread(target=loop, daemon=True).start()

    def on_term(*_):
        stop.set()
        threading.Thread(target=srv.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, on_term)
    print("NetTime serving on http://127.0.0.1:%d (loopback only)" % a.port, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    stop.set()
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="nettime")
    p.add_argument("--data-dir", default=os.environ.get("NETTIME_DATA", DEFAULT_DIR))
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("setup", help="pin router certificate, check login (read-only), create access key")
    s.add_argument("--router", default="192.168.1.1")
    s.add_argument("--paste-header", action="store_true", help="enter a copied login header (hidden) instead of the password")
    s.add_argument("--new-key", action="store_true")
    sub.add_parser("doctor", help="read-only checks")
    sv = sub.add_parser("serve", help="run scheduler and local page")
    sv.add_argument("--port", type=int, default=8787)
    sub.add_parser("new-key", help="replace the access key")
    a = p.parse_args(argv)
    store = Store(a.data_dir)
    fn = {"setup": cmd_setup, "doctor": cmd_doctor, "serve": cmd_serve, "new-key": cmd_new_key}.get(a.cmd)
    if not fn:
        p.print_help()
        return 2
    try:
        return fn(a, store)
    except RouterError as e:
        print("Router: %s" % e)
        return 1
    except (ValueError, OSError) as e:
        print("Error: %s" % e)
        return 1
