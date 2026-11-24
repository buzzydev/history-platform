"""Tiny database layer that runs on PostgreSQL (production) and SQLite (local/tests)."""
import glob
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import current_app, g

from .config import BASE_DIR


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse(ts):
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) if ts else None


def future(**kw):
    return fmt(datetime.now(timezone.utc) + timedelta(**kw))


def past(**kw):
    return fmt(datetime.now(timezone.utc) - timedelta(**kw))


class IntegrityError(Exception):
    pass


def _clean(row):
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, memoryview):
            d[k] = bytes(v)
    return d


class Db:
    def __init__(self, url):
        self.url = url
        self.pg = url.startswith("postgres")
        if self.pg:
            import psycopg
            from psycopg.rows import dict_row
            self.conn = psycopg.connect(url, row_factory=dict_row, connect_timeout=10)
            self._ie = psycopg.errors.IntegrityError
        else:
            path = url.replace("sqlite:///", "", 1)
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys=ON")
            if path != ":memory:":
                self.conn.execute("PRAGMA journal_mode=WAL")
            self._ie = sqlite3.IntegrityError

    def _sql(self, sql):
        return sql.replace("?", "%s") if self.pg else sql

    def execute(self, sql, params=()):
        try:
            cur = self.conn.cursor()
            cur.execute(self._sql(sql), tuple(params))
            return cur
        except self._ie as e:
            raise IntegrityError(str(e)) from e

    def all(self, sql, params=()):
        return [_clean(r) for r in self.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        r = self.execute(sql, params).fetchone()
        return _clean(r) if r else None

    def val(self, sql, params=(), default=None):
        r = self.execute(sql, params).fetchone()
        if r is None:
            return default
        v = list(dict(r).values())[0]
        return default if v is None else v

    def insert(self, sql, params=()):
        r = self.execute(sql + " RETURNING id", params).fetchone()
        return dict(r)["id"]

    def lock_user(self, user_id):
        """Serialise per-user critical sections (quiz start) on both engines."""
        if self.pg:
            self.execute("SELECT id FROM users WHERE id = ? FOR UPDATE", (user_id,))
        else:
            self.execute("UPDATE users SET id = id WHERE id = ?", (user_id,))

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def run_file(self, text):
        """Run a whole multi-statement file as-is (needed for trigger bodies containing ';')."""
        if self.pg:
            self.conn.cursor().execute(text)
        else:
            self.conn.executescript(text)

    def script(self, text):
        for stmt in [s.strip() for s in text.split(";") if s.strip()]:
            self.execute(stmt)


def render_ddl(text, pg):
    pk = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    blob = "BYTEA" if pg else "BLOB"
    return text.replace("{{PK}}", pk).replace("{{BLOB}}", blob)


def get_db():
    if "db" not in g:
        g.db = Db(current_app.config["DATABASE_URL"])
    return g.db


def open_db(url=None):
    return Db(url or current_app.config["DATABASE_URL"])


def init_app(app):
    @app.teardown_appcontext
    def _close(exc):
        db = g.pop("db", None)
        if db is not None:
            try:
                db.rollback() if exc else db.commit()
            finally:
                db.close()


def migrate(db=None):
    own = db is None
    db = db or open_db()
    db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    db.commit()
    done = {r["name"] for r in db.all("SELECT name FROM schema_migrations")}
    engine = "pg" if db.pg else "sqlite"
    other = "sqlite" if db.pg else "pg"
    for path in sorted(glob.glob(os.path.join(BASE_DIR, "migrations", "*.sql"))):
        name = os.path.basename(path)
        if name in done or name.endswith(f".{other}.sql"):
            continue
        with open(path, encoding="utf-8") as fh:
            text = render_ddl(fh.read(), db.pg)
        if name.endswith(f".{engine}.sql"):
            # engine-specific hardening (triggers): a failure must not stop the site from booting
            try:
                db.run_file(text)
            except Exception as e:  # pragma: no cover - only reachable on PostgreSQL
                db.rollback()
                print(f"WARNING: optional migration {name} failed and was skipped: {e}")
                continue
        else:
            db.script(text)
        db.execute("INSERT INTO schema_migrations(name, applied_at) VALUES (?, ?)", (name, utcnow()))
        db.commit()
    if own:
        db.close()


DEFAULT_SETTINGS = {
    "site_name": "History Quiz",
    "language": "uz",
    "registration_open": "1",
    "default_questions_per_attempt": "20",
    "default_time_limit_minutes": "0",
    "default_max_attempts": "0",
    "default_show_correct": "1",
    "leaderboard_min_attempts": "3",
    "leaderboard_prior_strength": "5",
    "backup_enabled": "1",
    "backup_interval_hours": "24",
    "backup_retention_count": "14",
    "backup_include_pdfs": "1",
}


def get_setting(key, db=None):
    db = db or get_db()
    v = db.val("SELECT v FROM settings WHERE k = ?", (key,))
    return v if v is not None else DEFAULT_SETTINGS.get(key, "")


def set_setting(key, value, db=None):
    db = db or get_db()
    if db.val("SELECT 1 FROM settings WHERE k = ?", (key,)):
        db.execute("UPDATE settings SET v = ? WHERE k = ?", (str(value), key))
    else:
        db.execute("INSERT INTO settings(k, v) VALUES (?, ?)", (key, str(value)))


def seed_defaults():
    db = open_db()
    try:
        now = utcnow()
        if not db.val("SELECT COUNT(*) FROM grades"):
            for i, n in enumerate(["6th grade", "7th grade", "8th grade", "9th grade", "10th grade", "11th grade"]):
                db.execute("INSERT INTO grades(name, sort_order, created_at) VALUES (?,?,?)", (n, i + 6, now))
        if not db.val("SELECT COUNT(*) FROM subjects"):
            for n in ["World History", "Uzbekistan History"]:
                db.execute("INSERT INTO subjects(name, description, created_at) VALUES (?,?,?)", (n, "", now))
        db.commit()
    finally:
        db.close()


def paginate(db, sql, params, page, per_page=20, order=""):
    total = db.val(f"SELECT COUNT(*) FROM ({sql}) AS t", params, 0)
    pages = max(1, -(-total // per_page))
    page = min(max(1, page), pages)
    rows = db.all(f"{sql} {order} LIMIT {int(per_page)} OFFSET {(page - 1) * per_page}", params)
    return {"rows": rows, "total": total, "page": page, "pages": pages, "per_page": per_page}
