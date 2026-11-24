from datetime import datetime, timedelta, timezone

from flask import current_app, request

from .db import fmt, parse


def form_int(name, default=0, lo=None, hi=None, src=None):
    src = src if src is not None else request.form
    try:
        v = int((src.get(name) or "").strip())
    except ValueError:
        v = default
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def form_flag(name):
    return 1 if request.form.get(name) in ("1", "on", "true") else 0


def local_to_utc(s):
    """datetime-local string (site timezone) -> UTC 'YYYY-MM-DD HH:MM:SS' or None."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        dt = datetime.strptime(s.replace("T", " ")[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return fmt(dt - timedelta(hours=current_app.config["TZ_OFFSET_HOURS"]))


def utc_to_local_input(ts):
    if not ts:
        return ""
    dt = parse(ts) + timedelta(hours=current_app.config["TZ_OFFSET_HOURS"])
    return dt.strftime("%Y-%m-%dT%H:%M")


def local_dt(ts):
    if not ts:
        return ""
    dt = parse(ts) + timedelta(hours=current_app.config["TZ_OFFSET_HOURS"])
    return dt.strftime("%d.%m.%Y %H:%M")


def page_arg():
    try:
        return max(1, int(request.args.get("page", "1")))
    except ValueError:
        return 1


def dur(seconds):
    seconds = int(seconds or 0)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")
