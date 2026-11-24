import json
import os
import secrets
import time

from flask import Flask, g, jsonify, redirect, render_template, request, session
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from . import audit, db as dbm, i18n, security
from .config import BASE_DIR, load_config
from .helpers import dur, local_dt


def bootstrap_admin():
    """Create the first administrator from environment variables (never hard-coded)."""
    u, p = os.environ.get("ADMIN_USERNAME"), os.environ.get("ADMIN_PASSWORD")
    if not u or not p:
        return
    db = dbm.open_db()
    try:
        if db.val("SELECT 1 FROM users WHERE username_lower = ?", (u.lower(),)):
            return
        if security.validate_password(p) or not security.USERNAME_RE.match(u):
            print("ADMIN bootstrap skipped: invalid ADMIN_USERNAME / weak ADMIN_PASSWORD")
            return
        phone = security.normalize_phone(os.environ.get("ADMIN_PHONE", "")) or "+0%09d" % secrets.randbelow(10 ** 9)
        now = dbm.utcnow()
        db.insert(
            "INSERT INTO users(username,username_lower,first_name,last_name,phone,password_hash,role,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (u, u.lower(), os.environ.get("ADMIN_FIRST_NAME", "Site"), os.environ.get("ADMIN_LAST_NAME", "Admin"),
             phone, security.hash_password(p), "admin", now, now))
        db.commit()
    finally:
        db.close()


def _log(msg):
    print(f"[boot] {msg}", flush=True)


def _boot(app):
    """Prepare the database. Retries (Railway's private network can be a few seconds late) and logs every step."""
    from urllib.parse import urlparse
    url = app.config["DATABASE_URL"]
    if url.startswith("postgres"):
        u = urlparse(url)
        _log(f"database: PostgreSQL host={u.hostname} port={u.port} db={u.path.lstrip('/')}")
    else:
        _log("database: SQLite (development file)")
    _log("env: SECRET_KEY set=%s, ADMIN_USERNAME set=%s, PORT=%s, APP_ENV=%s" % (
        bool(os.environ.get("SECRET_KEY")), bool(os.environ.get("ADMIN_USERNAME")), os.environ.get("PORT"), app.config["APP_ENV"]))
    last = None
    for attempt in range(1, 7):
        try:
            with app.app_context():
                _log("running migrations...")
                dbm.migrate()
                _log("seeding defaults...")
                dbm.seed_defaults()
                bootstrap_admin()
            _log("database ready")
            return
        except Exception as e:
            last = e
            _log(f"attempt {attempt}/6 failed: {type(e).__name__}: {e}")
            time.sleep(min(2 * attempt, 8))
    raise last


def create_app(overrides=None):
    app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"),
                template_folder=os.path.join(BASE_DIR, "templates"))
    app.config.update(load_config())
    if overrides:
        app.config.update(overrides)
    if app.config["APP_ENV"] == "production":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    dbm.init_app(app)
    _boot(app)

    from .routes import admin, api, auth, main, teacher
    for m in (auth, main, api, teacher, admin):
        app.register_blueprint(m.bp)

    @app.before_request
    def _before():
        security.load_user()
        security.check_csrf()

    app.after_request(security.add_security_headers)

    def current_lang():
        c = request.cookies.get("lang")
        if c in ("uz", "en"):
            return c
        try:
            v = dbm.get_setting("language")
        except Exception:
            v = "uz"
        return v if v in ("uz", "en") else "uz"

    @app.after_request
    def _translate(resp):
        if request.endpoint in (None, "static") or resp.direct_passthrough or resp.status_code == 304:
            return resp
        if current_lang() != "uz":
            return resp
        if resp.mimetype == "text/html":
            resp.set_data(i18n.translate_html(resp.get_data(as_text=True)))
        elif resp.mimetype == "application/json":
            try:
                data = json.loads(resp.get_data(as_text=True))
            except ValueError:
                return resp
            resp.set_data(json.dumps(i18n.translate_json_error(data), ensure_ascii=False))
        return resp

    @app.get("/lang/<code>")
    def set_lang(code):
        if code not in ("uz", "en"):
            return jsonify(error="Unknown language."), 404
        r = redirect(security.safe_next(request.args.get("next")) or "/")
        r.set_cookie("lang", code, max_age=60 * 60 * 24 * 365, samesite="Lax", httponly=True,
                     secure=app.config["SESSION_COOKIE_SECURE"])
        return r

    @app.context_processor
    def _ctx():
        unread = audit.unread_count(g.user["id"]) if g.get("user") else 0
        notes = []
        if g.get("user"):
            notes = dbm.get_db().all(
                "SELECT n.id, n.title, n.body, n.level, n.created_at, "
                "(SELECT COUNT(*) FROM notification_reads r WHERE r.notification_id = n.id AND r.user_id = ?) AS is_read "
                "FROM notifications n WHERE n.user_id = ? OR n.user_id IS NULL ORDER BY n.id DESC LIMIT 6",
                (g.user["id"], g.user["id"]))
        lang = current_lang()
        return {"current_user": g.get("user"), "csrf_token": security.csrf_token, "unread_count": unread,
                "site_name": dbm.get_setting("site_name"), "has_perm": security.has_perm, "bell_notes": notes,
                "lang": lang, "i18n_dict": i18n.js_dict(lang)}

    app.jinja_env.filters["dt"] = local_dt
    app.jinja_env.filters["dur"] = dur
    app.jinja_env.filters["pct"] = lambda v: f"{float(v or 0):.0f}%"
    app.jinja_env.filters["fromjson"] = lambda s: json.loads(s or "[]")

    def _err(code, title):
        def h(e):
            msg = e.description if isinstance(e, HTTPException) else ""
            if request.path.startswith("/api/") or "/api/" in request.path or request.is_json:
                return jsonify(error=msg or title), code
            return render_template("error.html", code=code, title=title, message=msg), code
        return h

    for code, title in ((400, "Bad request"), (403, "Access denied"), (404, "Page not found"),
                        (413, "File too large"), (429, "Too many requests")):
        app.register_error_handler(code, _err(code, title))

    @app.errorhandler(500)
    def _500(e):
        app.logger.exception("Unhandled server error")
        if request.path.startswith("/api/") or "/api/" in request.path:
            return jsonify(error="Internal server error."), 500
        return render_template("error.html", code=500, title="Server error",
                               message="Something went wrong. Please try again."), 500

    @app.get("/healthz")
    def healthz():
        try:
            dbm.get_db().val("SELECT 1")
            return jsonify(status="ok")
        except Exception:
            return jsonify(status="db_error"), 503

    if app.config["RUN_SCHEDULER"] and not app.config["TESTING"]:
        from .backup import start_scheduler
        start_scheduler(app)
    _log("application ready")
    return app
