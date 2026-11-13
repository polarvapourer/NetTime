"""Scheduler, metering and enforcement. Runs without any browser open."""
import os
import threading
import time

from .macs import canonical_mac, is_unicast
from .policy import active_exception, decide, london, setup_complete, split_charge, validate_settings
from .router import PinMismatch, RouterError, apply_target

POLL_SECONDS = 10
MAX_GAP = 30.0        # longer gaps between samples are never charged (no backfill)
JUMP_TOLERANCE = 5.0  # wall vs monotonic disagreement => clock jump, interval not charged
KEEP_DAYS = 14
FAILED = ("refused", "write-failed", "unconfirmed", "readback-mismatch")


class UserError(Exception):
    pass


def local_macs():
    """This Pi's own interface MACs and the gateway's MAC (never valid targets)."""
    out = set()
    try:
        for n in os.listdir("/sys/class/net"):
            try:
                with open("/sys/class/net/%s/address" % n) as f:
                    m = canonical_mac(f.read().strip())
                if m and m != "00:00:00:00:00:00":
                    out.add(m)
            except OSError:
                pass
        with open("/proc/net/arp") as f:
            for line in f.read().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == "192.168.1.1":
                    m = canonical_mac(parts[3])
                    if m:
                        out.add(m)
    except OSError:
        pass
    return out


class Engine(object):
    def __init__(self, store, router, clock=time.time, mono=time.monotonic, self_macs=None):
        self.store, self.router, self.clock, self.mono = store, router, clock, mono
        self.lock = threading.RLock()
        self.st = store.load_state()
        for k, v in (("pending", None), ("ownedBlock", False)):
            self.st.setdefault(k, v)
        self.self_macs = set(self_macs) if self_macs is not None else local_macs()
        self.last_sample = None
        self.devices = None        # fresh device list from this process only (never trusted across restarts)
        self.local_device_id = None
        # A saved "on" switch resumes only after a fresh check of router, target and expected membership.
        self.needs_revalidation = bool(self.st["enforcement"])
        self.status = {"router": "not-configured" if router is None else "unknown", "lastSuccess": None,
                       "lastError": None, "mode": None, "targetInList": None, "connection": "unknown",
                       "connectionStale": None, "metering": "off", "exceptionLabel": None,
                       "rule": None, "ruleMessage": None, "entries": None}

    # ---------- helpers
    def _save(self):
        keep = sorted(self.st["usage"])[-KEEP_DAYS:]
        self.st["usage"] = {k: self.st["usage"][k] for k in keep}
        self.store.save_state(self.st)

    def _err(self, e):
        self.status["router"] = "tls-pin" if isinstance(e, PinMismatch) else "error"
        self.status["lastError"] = {"code": e.code, "message": str(e), "at": self.clock()}

    def _ok(self):
        self.status["router"] = "ok"
        self.status["lastSuccess"] = self.clock()

    def _pause(self, message, pending=None):
        self.st["paused"] = message[:200]
        if pending is not None:
            self.st["pending"] = pending
        self.last_sample = None

    def _bonus_minutes(self, date):
        b = self.st["bonus"]
        return b["minutes"] if b and b.get("date") == date else 0

    def _drop_stale_bonus(self, date):
        if self.st["bonus"] and self.st["bonus"].get("date") != date:
            self.st["bonus"] = None

    def _forbidden_reason(self, mac):
        if canonical_mac(mac) != mac or not is_unicast(mac):
            return "Not a valid device address"
        if mac in self.self_macs:
            return "This is the controller or router itself"
        for d in self.devices or []:
            if mac in d["macs"]:
                if d["isAuthority"] or (d["nodeType"] or "") in ("Master", "Slave"):
                    return "This is a router/Wi-Fi node"
                if self.local_device_id and d["id"] == self.local_device_id:
                    return "This is the controller itself"
        return None

    def _connection(self, devs):
        """Only the selected MAC counts: other interfaces of the same device are ignored."""
        if devs is None:
            return "unknown"
        target = self.st["target"]
        if any(target in d["connectedMacs"] for d in devs):
            return "connected"
        if any(target in d["macs"] for d in devs):
            return "not-connected"
        return "not-listed"

    def _fresh_identity(self):
        """Fresh device list + controller identity, used before switching on or resuming."""
        self.devices = self.router.get_devices()
        self.local_device_id = self.router.get_local_device_id()

    def active(self):
        return bool(self.st["enforcement"]) and not self.st["paused"]

    # ---------- main loop step
    def tick(self):
        with self.lock:
            if self.router is None:
                return False
            now, mono = self.clock(), self.mono()
            target = self.st["target"]
            try:
                f = self.router.get_filter()
                devs = self.router.get_devices() if target else None
                if self.needs_revalidation and self.active():
                    self.local_device_id = self.router.get_local_device_id()
            except RouterError as e:
                self._err(e)
                self.last_sample = None  # unknown gap: nothing is charged across it
                if self.status["connection"] != "unknown":
                    self.status["connectionStale"] = self.status["connection"]
                self.status["connection"] = "unknown"
                self.status["metering"] = "unknown" if self.active() else "off"
                return False
            self._ok()
            if devs is not None:
                self.devices = devs
            lt = london(now)
            self._drop_stale_bonus(lt["date"])
            observed = (target in f["macs"]) if target else None
            self.status.update(mode=f["mode"], targetInList=observed, entries=len(f["macs"]), connectionStale=None,
                               connection=self._connection(devs) if target else "unknown")

            if not self.st["enforcement"] and self.st["ownedBlock"] and observed is False:
                self.st["ownedBlock"] = False  # NetTime's leftover block is gone (no write needed)
                self.st["pending"] = None

            if self.active() and self.needs_revalidation:
                problems = self.activation_problems(f, resuming=True)
                if self.st["expectedBlocked"] is None or observed != self.st["expectedBlocked"]:
                    problems.append("the iPad's router entry differs from what NetTime last confirmed")
                if problems:
                    self._pause("Paused after restart: " + "; ".join(problems))
                self.needs_revalidation = False

            # external change detection: pause automation, do not undo the change
            if self.active():
                if f["mode"] != "Deny":
                    self._pause("Router filter mode changed to %s outside NetTime" % f["mode"][:20])
                elif observed != self.st["expectedBlocked"]:
                    self._pause("The iPad was %s in the router outside NetTime"
                                % ("unblocked" if self.st["expectedBlocked"] else "blocked"))
                    if not observed:
                        self.st["ownedBlock"] = False

            # metering: selected MAC router-reported connected AND rule allowed at both samples
            allowed_now = self.status["connection"] == "connected" and observed is False
            win = active_exception(self.st["settings"], lt)
            self.status["exceptionLabel"] = win["label"] if win else None
            if self.active():
                prev = self.last_sample
                if prev and prev[2] and allowed_now:
                    dt, dm = now - prev[0], mono - prev[1]
                    if 0 < dt <= MAX_GAP and abs(dt - dm) <= JUMP_TOLERANCE:
                        start = max(prev[0], float(self.st["chargedUntil"] or 0))
                        if now > start:
                            for date, sec in split_charge(self.st["settings"], start, now).items():
                                self.st["usage"][date] = self.st["usage"].get(date, 0.0) + sec
                            self.st["chargedUntil"] = now
                self.status["metering"] = ("exception" if allowed_now and win else "counting" if allowed_now else
                                           "blocked" if observed else "not-connected")
                self.last_sample = (now, mono, allowed_now)
            else:
                self.status["metering"] = "off"
                self.last_sample = None

            d = decide(self.st["settings"], lt, self.st["usage"].get(lt["date"], 0.0), self._bonus_minutes(lt["date"]))
            if self.active() and d["block"] is not None and d["block"] != observed:
                try:
                    res = apply_target(self.router, target, d["block"])
                except RouterError as e:
                    self._err(e)
                    res = {"status": "unconfirmed", "message": "Router error (%s)" % e.code}
                self.status["rule"], self.status["ruleMessage"] = res["status"], res["message"]
                if res["status"] in ("confirmed", "unchanged"):
                    self.st["expectedBlocked"] = d["block"]
                    self.st["ownedBlock"] = d["block"]
                    self.st["pending"] = None
                else:
                    uncertain = res["status"] in ("unconfirmed", "readback-mismatch")
                    self._pause(("Rule uncertain - check router. " if uncertain else "Router change refused. ")
                                + res["message"],
                                pending={"want": d["block"], "status": res["status"], "at": now})
                    self._save()
                    return False
            self._save()
            return True

    # ---------- owner actions
    def activation_problems(self, f=None, resuming=False):
        p = []
        if self.router is None:
            p.append("Router login not set up")
        if not setup_complete(self.st["settings"]):
            p.append("Choose an allowance for every day")
        t = self.st["target"]
        if not t:
            p.append("Select the iPad from the device list")
        else:
            if self.devices is None or not any(t in d["macs"] for d in self.devices):
                p.append("Selected iPad address not in the router's current device list (find devices again)")
            r = self._forbidden_reason(t)
            if r:
                p.append(r)
        if f is None:
            if self.status["router"] != "ok":
                p.append("Router login/read not verified yet")
        else:
            if f["mode"] != "Deny":
                p.append("Router MAC filter mode must be Deny")
            if not resuming and t and t in f["macs"] and not self.st["ownedBlock"]:
                p.append("The iPad is already in the router's deny list (added manually). Remove it in the router first.")
        return p

    def set_enforcement(self, enabled):
        with self.lock:
            if enabled:
                if self.router is None:
                    raise UserError("Router login not set up")
                if self.st["pending"]:
                    raise UserError("A previous router change is unresolved. Use 'Check router and resume' or 'Check uncertain block' first.")
                f = self.router.get_filter()
                self._fresh_identity()
                self._ok()
                probs = self.activation_problems(f)
                if probs:
                    raise UserError("; ".join(probs))
                observed = self.st["target"] in f["macs"]
                self.st.update(enforcement=True, paused=None, expectedBlocked=observed)
                self.needs_revalidation = False
                self.last_sample = None
                self._save()
                return "Blocking switched on"
            # Stop is durable first, even if the router can't be reached.
            self.st.update(enforcement=False, paused=None, expectedBlocked=None)
            self.needs_revalidation = False
            self.last_sample = None
            self._save()
            if not self.st["ownedBlock"]:
                pend = self.st["pending"] or {}
                if pend.get("want") is True:
                    # A block write may have applied but was never confirmed: keep the marker.
                    return ("Automation stopped. Router block may remain: NetTime's last block attempt was never "
                            "confirmed. Use 'Check uncertain block' to read the router.")
                self.st["pending"] = None
                self._save()
                return "Blocking switched off"
            return "Automation stopped. " + self._release()

    def _release(self):
        """Remove only a block NetTime added. Keeps ownership until the removal is verified."""
        try:
            res = apply_target(self.router, self.st["target"], False)
        except RouterError as e:
            self._err(e)
            res = {"status": "unconfirmed", "message": "Router error (%s)" % e.code}
        if res["status"] in ("confirmed", "unchanged"):
            self.st["ownedBlock"] = False
            self.st["pending"] = None
            self._save()
            return "NetTime's block removed and confirmed."
        self.st["pending"] = {"want": False, "status": res["status"], "at": self.clock()}
        self._save()
        return "Router block may remain (%s). Use 'Retry removing block' or remove it in the router." % res["message"]

    def retry_release(self, confirm_uncertain=False):
        """Owner action. Confirmed ownership: remove. Uncertain NetTime write: fresh read, then only
        remove after an explicit owner confirmation. Never touches a block NetTime has no record of."""
        with self.lock:
            if self.st["enforcement"]:
                raise UserError("Switch blocking off first")
            if self.st["ownedBlock"]:
                return self._release()
            pend = self.st["pending"] or {}
            if pend.get("want") is not True:
                return "No NetTime block to remove"
            f = self.router.get_filter()
            self._ok()
            if self.st["target"] not in f["macs"]:
                self.st["pending"] = None
                self._save()
                return "Router checked: the iPad is not in the deny list. Uncertain marker cleared."
            if not confirm_uncertain or pend.get("status") != "present-unverified":
                self.st["pending"] = dict(pend, status="present-unverified", at=self.clock())
                self._save()
                return ("The iPad is in the deny list. NetTime tried to add it but never confirmed, so it may be "
                        "NetTime's block or a manual one. Use 'Remove uncertain block' to remove it, or leave it.")
            self.st["ownedBlock"] = True  # owner confirmed this entry is NetTime's
            self._save()
            return self._release()

    def resume(self):
        """Owner reconciliation after any pause: fresh read, accept the router's current state."""
        with self.lock:
            if not self.st["paused"]:
                return "Not paused"
            f = self.router.get_filter()
            self._fresh_identity()
            self._ok()
            probs = self.activation_problems(f, resuming=True)
            if probs:
                raise UserError("; ".join(probs))
            observed = self.st["target"] in f["macs"]
            pend = self.st["pending"] or {}
            owned = observed and (self.st["ownedBlock"] or pend.get("want") is True)
            if observed and not owned:
                raise UserError("The iPad is in the deny list but NetTime did not add it. Remove it in the router or switch blocking off.")
            self.st.update(paused=None, pending=None, expectedBlocked=observed, ownedBlock=owned)
            self.needs_revalidation = False
            self.last_sample = None
            self._save()
            return "Router checked; automation resumed"

    def discover(self):
        with self.lock:
            devs = self.router.get_devices()
            try:
                self.local_device_id = self.router.get_local_device_id()
            except RouterError:
                self.local_device_id = None
            self._ok()
            self.devices = devs
            out = []
            for d in devs:
                rows = [{"mac": m, "connected": m in d["connectedMacs"], "reason": self._forbidden_reason(m)} for m in d["macs"]]
                out.append(dict(d, addresses=rows))
            return out

    def select_target(self, mac, name=None):
        with self.lock:
            self._require_target_change_safe("changing")
            m = canonical_mac(mac)
            if not is_unicast(m):
                raise UserError("Not a valid device address")
            if not self.devices or not any(m in d["macs"] for d in self.devices):
                raise UserError("Find devices first, then choose one from the list")
            r = self._forbidden_reason(m)
            if r:
                raise UserError(r)
            changed = m != self.st["target"]
            self.st["target"] = m
            self.st["targetName"] = (name or "")[:60] or None
            self._save()
            if changed:
                self._reset_target_status()

    def _require_target_change_safe(self, verb):
        if self.st["enforcement"]:
            raise UserError("Switch blocking off before %s the device" % verb)
        if self.st["ownedBlock"] or self.st["pending"]:
            raise UserError("A router change for this device is still unresolved. Switch blocking off, then use "
                            "'Retry removing block' / 'Check uncertain block' before %s the device" % verb)

    def _reset_target_status(self):
        """Forget live status that belonged to the previous device so it is never shown for another one."""
        self.last_sample = None
        self.status.update(targetInList=None, connection="unknown", connectionStale=None, metering="off",
                           exceptionLabel=None, rule=None, ruleMessage=None)

    def clear_target(self):
        """Unselect the device. Local only: no router contact, no router writes. Idempotent when safe."""
        with self.lock:
            self._require_target_change_safe("unselecting")
            if self.st["target"] is not None or self.st["targetName"] is not None:
                self.st["target"] = None
                self.st["targetName"] = None
                self.st["expectedBlocked"] = None
                self._save()
            self._reset_target_status()

    def save_settings(self, raw):
        s, errs = validate_settings(raw)
        if errs:
            raise UserError("; ".join(errs[:8]))
        with self.lock:
            if self.st["enforcement"] and not setup_complete(s):
                raise UserError("Every day needs an allowance while blocking is on")
            self.st["settings"] = s  # never changes the enforcement switch
            self._save()

    def add_bonus(self, minutes):
        if not isinstance(minutes, int) or isinstance(minutes, bool) or not 1 <= minutes <= 1440:
            raise UserError("Minutes must be 1-1440")
        with self.lock:
            date = london(self.clock())["date"]
            self.st["bonus"] = {"date": date, "minutes": min(1440, self._bonus_minutes(date) + minutes)}
            self._save()

    def clear_bonus(self):
        with self.lock:
            self.st["bonus"] = None
            self._save()

    def snapshot(self):
        with self.lock:
            now = self.clock()
            lt = london(now)
            self._drop_stale_bonus(lt["date"])
            used = self.st["usage"].get(lt["date"], 0.0)
            d = decide(self.st["settings"], lt, used, self._bonus_minutes(lt["date"]))
            return {"status": dict(self.status), "settings": self.st["settings"], "target": self.st["target"],
                    "targetName": self.st["targetName"], "enforcement": self.st["enforcement"],
                    "paused": self.st["paused"], "pending": self.st["pending"], "ownedBlock": self.st["ownedBlock"],
                    "releaseAttention": (not self.st["enforcement"]) and bool(
                        self.st["ownedBlock"] or (self.st["pending"] or {}).get("want") is True),
                    "observationOnly": not self.active(),
                    "today": {"date": lt["date"], "day": lt["day"], "minute": lt["minute"], "usedSeconds": used,
                              "bonusMinutes": self._bonus_minutes(lt["date"]), "decision": d},
                    "activationProblems": self.activation_problems() if not self.st["enforcement"] else []}
