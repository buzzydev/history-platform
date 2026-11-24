import hmac
import re
import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import abort, current_app, flash, g, redirect, request, session, url_for, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

from .db import fmt, future, get_db, parse, past, utcnow

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")


def hash_password(p):
    return generate_password_hash(p, method="scrypt")


def verify_password(h, p):
    return check_password_hash(h, p)


def validate_password(p):
    errs = []
    if len(p or "") < 8:
        errs.append("Password must be at least 8 characters.")
    if len(p or "") > 128:
        errs.append("Password is too long (max 128).")
    if not re.search(r"[A-Za-z\u0400-\u04FF]", p or "") or not re.search(r"\d", p or ""):
        errs.append("Password must contain letters and digits.")
    return errs


def normalize_phone(raw):
    s = re.sub(r"[\s\-()]", "", raw or "")
    if re.fullmatch(r"\d{9}", s):
        s = "+998" + s
    elif re.fullmatch(r"998\d{9}", s):
        s = "+" + s
    return s if re.fullmatch(r"\+\d{9,15}", s) else None


def client_ip():
    return request.remote_addr or ""


def user_agent():
    return (request.headers.get("User-Agent") or "")[:300]


# ---------- CSRF ----------
def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        tok = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token") or ""
        if not tok or not hmac.compare_digest(tok, session.get("csrf", "")):
            abort(400, "Invalid or missing CSRF token.")


# ---------- Rate limiting (DB backed, shared across workers) ----------
def rl_count(key, window_seconds):
    return get_db().val("SELECT COUNT(*) FROM rate_limits WHERE k = ? AND created_at > ?",
                        (key, past(seconds=window_seconds)), 0)


def rl_hit(key):
    db = get_db()
    db.execute("INSERT INTO rate_limits(k, created_at) VALUES (?, ?)", (key, utcnow()))
    if secrets.randbelow(50) == 0:
        db.execute("DELETE FROM rate_limits WHERE created_at < ?", (past(days=1),))


def rl_blocked(key, limit, window_seconds):
    return rl_count(key, window_seconds) >= limit


# ---------- Sessions ----------
def create_session(user_id, remember):
    sid = secrets.token_urlsafe(32)
    now = utcnow()
    exp = future(days=30) if remember else future(days=1)
    get_db().execute(
        "INSERT INTO user_sessions(id,user_id,ip,user_agent,created_at,last_seen_at,expires_at,revoked) VALUES (?,?,?,?,?,?,?,0)",
        (sid, user_id, client_ip(), user_agent(), now, now, exp))
    session.clear()
    session["sid"] = sid
    session["csrf"] = secrets.token_urlsafe(32)
    session.permanent = bool(remember)
    return sid


def revoke_sessions(user_id, except_sid=None):
    db = get_db()
    if except_sid:
        db.execute("UPDATE user_sessions SET revoked = 1 WHERE user_id = ? AND id <> ?", (user_id, except_sid))
    else:
        db.execute("UPDATE user_sessions SET revoked = 1 WHERE user_id = ?", (user_id,))


def load_user():
    g.user = None
    sid = session.get("sid")
    if not sid:
        return
    db = get_db()
    row = db.one(
        "SELECT u.*, s.expires_at AS s_exp, s.revoked AS s_rev, s.last_seen_at AS s_seen "
        "FROM user_sessions s JOIN users u ON u.id = s.user_id WHERE s.id = ?", (sid,))
    if not row or row["s_rev"] or row["is_blocked"] or row["s_exp"] <= utcnow():
        session.pop("sid", None)
        return
    if row["s_seen"] < past(minutes=5):
        db.execute("UPDATE user_sessions SET last_seen_at = ? WHERE id = ?", (utcnow(), sid))
    g.user = row
    g.sid = sid


def teacher_perms(user):
    import json
    try:
        return json.loads(user.get("teacher_perms") or "{}")
    except ValueError:
        return {}


def has_perm(perm):
    u = g.user
    if not u:
        return False
    if u["role"] == "admin":
        return True
    return u["role"] == "teacher" and bool(teacher_perms(u).get(perm))


def _wants_json():
    return request.path.startswith("/api/") or "/api/" in request.path or request.is_json


def deny(status):
    if _wants_json():
        return jsonify(error="Authentication required." if status == 401 else "Forbidden."), status
    if status == 401:
        flash("Please log in to continue.", "info")
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
    abort(403)


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not g.user:
            return deny(401)
        return f(*a, **k)
    return w


def role_required(*roles):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if not g.user:
                return deny(401)
            if g.user["role"] not in roles:
                return deny(403)
            return f(*a, **k)
        return w
    return deco


def perm_required(perm):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if not g.user:
                return deny(401)
            if not has_perm(perm):
                return deny(403)
            return f(*a, **k)
        return w
    return deco


def safe_next(url):
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return None


def add_security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    if current_app.config["APP_ENV"] == "production":
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.endpoint and request.endpoint != "static":
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp
