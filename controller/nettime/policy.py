"""Pure schedule policy in Europe/London wall-clock time (same rules as the NetTime dashboard)."""
import math
import calendar
from datetime import datetime, timedelta, timezone
import re

TIMEZONE = "Europe/London"
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MAX_DAY_MINUTES = 1440
_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
TOP_KEYS = {"schemaVersion", "timezone", "deviceLabel", "weekly", "exceptions", "leisurePaused"}
EXC_KEYS = {"id", "label", "days", "start", "end"}


def init_tz():
    """Compatibility entry point. Conversion no longer changes the process timezone."""
    return TIMEZONE


def london(ts):
    """UK scheduling rules since 1996, independent of host TZ and tzset availability.

    BST starts/ends at 01:00 UTC on the last Sunday of March/October.
    This is a current-schedule converter, not a historical timezone database.
    """
    t = datetime.fromtimestamp(ts, timezone.utc)
    if t.year < 1996:
        raise ValueError("NetTime scheduling supports dates from 1996 onwards")
    def boundary(month):
        last = calendar.monthrange(t.year, month)[1]
        d = datetime(t.year, month, last, 1, tzinfo=timezone.utc)
        return d - timedelta(days=(d.weekday() + 1) % 7)
    if boundary(3) <= t < boundary(10):
        t += timedelta(hours=1)
    return {"date": t.strftime("%Y-%m-%d"), "day": DAYS[t.weekday()],
            "minute": t.hour * 60 + t.minute}


def parse_hhmm(v):
    m = _HHMM.match(v) if isinstance(v, str) else None
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def default_settings():
    return {"schemaVersion": 1, "timezone": TIMEZONE, "deviceLabel": "iPad",
            "weekly": {d: None for d in DAYS},
            "exceptions": [{"id": "study", "label": "Study time", "days": ["sat", "sun"],
                            "start": "11:00", "end": "12:00"}],
            "leisurePaused": False}


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate_settings(raw):
    """Return (settings, errors). Mirrors the dashboard's schemaVersion 1 format (strict keys)."""
    errs = []
    if not isinstance(raw, dict):
        return None, ["file: must be a JSON object"]
    extra = set(raw) - TOP_KEYS
    missing = TOP_KEYS - set(raw)
    if extra:
        errs.append("file: unknown keys " + ", ".join(sorted(extra)))
    if missing:
        errs.append("file: missing keys " + ", ".join(sorted(missing)))
    if errs:
        return None, errs
    if raw["schemaVersion"] != 1 or isinstance(raw["schemaVersion"], bool):
        errs.append("schemaVersion: Unsupported schemaVersion (expected 1)")
    if raw["timezone"] != TIMEZONE:
        errs.append('timezone: must be "%s"' % TIMEZONE)
    label = raw["deviceLabel"]
    if not isinstance(label, str) or not (1 <= len(label.strip()) <= 40):
        errs.append("deviceLabel: 1-40 characters")
    weekly = raw["weekly"]
    if not isinstance(weekly, dict) or set(weekly) != set(DAYS):
        errs.append("weekly: must contain exactly mon..sun")
    else:
        for d in DAYS:
            v = weekly[d]
            if v is not None and not (_is_int(v) and 0 <= v <= MAX_DAY_MINUTES):
                errs.append("weekly.%s: whole minutes 0-1440 or null" % d)
    exc = raw["exceptions"]
    if not isinstance(exc, list) or len(exc) > 10:
        errs.append("exceptions: list of at most 10")
    else:
        for i, e in enumerate(exc):
            err = validate_exception(e)
            if err:
                errs.append("exceptions.%d: %s" % (i, err))
    if not isinstance(raw["leisurePaused"], bool):
        errs.append("leisurePaused: must be true or false")
    if errs:
        return None, errs
    s = {"schemaVersion": 1, "timezone": TIMEZONE, "deviceLabel": label.strip(),
         "weekly": {d: weekly[d] for d in DAYS},
         "exceptions": [{k: (list(e[k]) if k == "days" else e[k]) for k in ("id", "label", "days", "start", "end")} for e in exc],
         "leisurePaused": raw["leisurePaused"]}
    return s, []


def validate_exception(e):
    if not isinstance(e, dict) or set(e) != EXC_KEYS:
        return "must have exactly id, label, days, start, end"
    if not isinstance(e["id"], str) or not e["id"] or len(e["id"]) > 64:
        return "id required"
    if not isinstance(e["label"], str) or not (1 <= len(e["label"]) <= 40):
        return "label 1-40 characters"
    if not isinstance(e["days"], list) or not e["days"]:
        return "Choose at least one day."
    if any(d not in DAYS for d in e["days"]):
        return "unknown day"
    a, b = parse_hhmm(e["start"]), parse_hhmm(e["end"])
    if a is None or b is None:
        return "Times must be HH:MM (24-hour)."
    if a == b:
        return "Start and end cannot be the same."
    if a > b:
        return "End must be after start (windows crossing midnight are not supported)."
    return None


def setup_complete(s):
    return all(_is_int(s["weekly"][d]) for d in DAYS)


def active_exception(s, lt):
    for e in s["exceptions"]:
        a, b = parse_hhmm(e["start"]), parse_hhmm(e["end"])
        if a is not None and b is not None and lt["day"] in e["days"] and a <= lt["minute"] < b:
            return e
    return None


def decide(s, lt, used_seconds, bonus_minutes=0):
    """block: True/False, or None when setup is incomplete (never block silently)."""
    if not setup_complete(s):
        return {"kind": "setup-incomplete", "label": "Setup incomplete", "block": None}
    win = active_exception(s, lt)
    if win:
        return {"kind": "allow-exception", "label": "Allow - %s exception" % win["label"].lower(), "block": False}
    if s["leisurePaused"]:
        return {"kind": "block-paused", "label": "Block - leisure paused", "block": True}
    total = (s["weekly"][lt["day"]] + max(0, bonus_minutes)) * 60.0
    remaining = total - max(0.0, used_seconds)
    if remaining > 0:
        return {"kind": "allow-remaining", "label": "Allow - allowance remaining", "block": False,
                "remainingSeconds": remaining, "totalSeconds": total}
    return {"kind": "block-exhausted", "label": "Block - allowance exhausted", "block": True, "totalSeconds": total}


def split_charge(s, start, end):
    """Seconds per London date for [start, end), excluding exception windows.

    London's UTC offset is a whole number of hours, so UTC minute boundaries are
    London minute boundaries; splitting per minute handles midnight, window edges and GMT/BST.
    """
    out = {}
    t = float(start)
    while t < end:
        nxt = min(float(end), (math.floor(t / 60.0) + 1) * 60.0)
        lt = london(t)
        if active_exception(s, lt) is None:
            out[lt["date"]] = out.get(lt["date"], 0.0) + (nxt - t)
        t = nxt
    return out
