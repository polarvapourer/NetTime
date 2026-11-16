"""Recurring school and away periods, expressed in London wall-clock time."""

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri")
DAYS = WEEKDAYS + ("sat", "sun")


def school_defaults():
    return {"enabled": False, "start": "09:00", "end": "15:00"}


def validate_schedules(raw, parse_time, validate_window):
    """Old settings omit these optional fields; normalize without enabling them."""
    errors = []
    school = raw.get("schoolHours", school_defaults())
    if not isinstance(school, dict) or set(school) != {"enabled", "start", "end"}:
        errors.append("schoolHours: must have exactly enabled, start, end")
    else:
        a, b = parse_time(school["start"]), parse_time(school["end"])
        if not isinstance(school["enabled"], bool):
            errors.append("schoolHours.enabled: must be true or false")
        if a is None or b is None or a >= b:
            errors.append("schoolHours: use HH:MM with end after start on the same day")
    away = raw.get("awayWindows", [])
    if not isinstance(away, list) or len(away) > 10:
        errors.append("awayWindows: list of at most 10")
    else:
        ids = set()
        for i, window in enumerate(away):
            if not isinstance(window, dict) or set(window) != {"id", "label", "days", "start", "end", "enabled"}:
                errors.append("awayWindows.%d: must have exactly id, label, days, start, end, enabled" % i)
                continue
            if not isinstance(window["enabled"], bool):
                errors.append("awayWindows.%d.enabled: must be true or false" % i)
            # The common window validator disallows midnight crossings; away periods allow them.
            basic = {k: window[k] for k in ("id", "label", "days", "start", "end")}
            a, b = parse_time(window["start"]), parse_time(window["end"])
            if a is not None and b is not None and a > b:
                basic["start"], basic["end"] = window["end"], window["start"]
            error = validate_window(basic)
            if error:
                errors.append("awayWindows.%d: %s" % (i, error))
            if isinstance(window["id"], str):
                if window["id"] in ids:
                    errors.append("awayWindows: ids must be unique")
                ids.add(window["id"])
    if errors:
        return None, None, errors
    return dict(school), [dict(w, days=list(w["days"])) for w in away], []


def school_window(settings, lt, parse_time):
    school = settings.get("schoolHours", school_defaults())
    if (school["enabled"] and lt["day"] in WEEKDAYS
            and parse_time(school["start"]) <= lt["minute"] < parse_time(school["end"])):
        return dict(school, id="school-hours", label="School hours", days=list(WEEKDAYS))
    return None


def away_window(settings, lt, parse_time):
    previous_day = DAYS[(DAYS.index(lt["day"]) - 1) % 7]
    for window in settings.get("awayWindows", []):
        if not window["enabled"]:
            continue
        a, b = parse_time(window["start"]), parse_time(window["end"])
        if a < b:
            match = lt["day"] in window["days"] and a <= lt["minute"] < b
        else:
            match = ((lt["day"] in window["days"] and lt["minute"] >= a)
                     or (previous_day in window["days"] and lt["minute"] < b))
        if match:
            return window
    return None
