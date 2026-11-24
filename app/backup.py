"""Logical database backups (portable JSON, gzip) with restore-verification into a scratch SQLite DB."""
import base64
import gzip
import hashlib
import json
import threading
import time
from datetime import datetime, timezone

from .db import Db, IntegrityError, migrate, open_db, parse, past, utcnow, get_setting, render_ddl

TABLES = ["users", "grades", "subjects", "test_collections", "uploaded_documents", "questions", "answer_options",
          "quiz_attempts", "attempt_questions", "student_answers", "question_exposure", "notifications",
          "notification_reads", "audit_logs", "login_history", "password_resets", "settings"]
BLOB_COLS = {"uploaded_documents": ["data"]}
SERIAL = {"users", "grades", "subjects", "test_collections", "uploaded_documents", "questions", "answer_options",
          "quiz_attempts", "attempt_questions", "student_answers", "question_exposure", "notifications",
          "audit_logs", "login_history", "password_resets"}

BACKUP_DDL = ("CREATE TABLE IF NOT EXISTS backups (id {{PK}}, kind TEXT NOT NULL DEFAULT 'scheduled', "
              "status TEXT NOT NULL DEFAULT 'running', size_bytes INTEGER NOT NULL DEFAULT 0, sha256 TEXT, "
              "row_counts TEXT NOT NULL DEFAULT '{}', verified INTEGER NOT NULL DEFAULT 0, error TEXT, data {{BLOB}}, "
              "created_at TEXT NOT NULL, finished_at TEXT)")


def storage_db(app_cfg):
    """Backups go to BACKUP_DATABASE_URL when configured (separate from the primary database)."""
    url = app_cfg.get("BACKUP_DATABASE_URL")
    if url:
        d = Db(url)
        d.execute(render_ddl(BACKUP_DDL, d.pg))
        d.commit()
        return d, True
    return open_db(app_cfg["DATABASE_URL"]), False


def dump(db, include_pdfs=True):
    payload = {"version": 1, "created_at": utcnow(), "tables": {}}
    counts = {}
    for t in TABLES:
        rows = db.all(f"SELECT * FROM {t}" + (" ORDER BY id" if t in SERIAL else ""))
        if t == "uploaded_documents" and not include_pdfs:
            for r in rows:
                r["data"] = b""
        for col in BLOB_COLS.get(t, []):
            for r in rows:
                r[col] = base64.b64encode(r[col] or b"").decode()
        payload["tables"][t] = rows
        counts[t] = len(rows)
    raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    return gzip.compress(raw), counts


def restore_into(target, blob):
    """Load a backup into an EMPTY database that already has the schema. Returns row counts."""
    payload = json.loads(gzip.decompress(blob).decode("utf-8"))
    counts = {}
    for t in TABLES:
        rows = payload["tables"].get(t, [])
        for r in rows:
            for col in BLOB_COLS.get(t, []):
                r[col] = base64.b64decode(r[col] or "")
            cols = list(r.keys())
            target.execute(f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [r[c] for c in cols])
        counts[t] = len(rows)
        if target.pg and t in SERIAL:
            target.execute(f"SELECT setval(pg_get_serial_sequence('{t}','id'), COALESCE((SELECT MAX(id) FROM {t}),1), "
                           f"(SELECT COUNT(*) FROM {t}) > 0)")
    return counts


def verify_restore(blob, expected):
    """Prove the archive restores: load into an in-memory SQLite and compare row counts."""
    scratch = Db("sqlite:///:memory:")
    migrate(scratch)
    got = restore_into(scratch, blob)
    scratch.close()
    return got == expected


def run_backup(app, kind="scheduled"):
    with app.app_context():
        primary = open_db()
        store, separate = storage_db(app.config)
        bid = None
        try:
            bid = store.insert("INSERT INTO backups(kind,status,created_at) VALUES (?,?,?)", (kind, "running", utcnow()))
            store.commit()
            blob, counts = dump(primary, get_setting("backup_include_pdfs", primary) == "1")
            verified = verify_restore(blob, counts)
            if not verified:
                raise RuntimeError("restore verification failed")
            store.execute(
                "UPDATE backups SET status='success', size_bytes=?, sha256=?, row_counts=?, verified=1, data=?, finished_at=? WHERE id=?",
                (len(blob), hashlib.sha256(blob).hexdigest(), json.dumps(counts), blob, utcnow(), bid))
            keep = int(get_setting("backup_retention_count", primary) or 14)
            old = store.all("SELECT id FROM backups WHERE status='success' ORDER BY id DESC")
            for r in old[keep:]:
                store.execute("DELETE FROM backups WHERE id = ?", (r["id"],))
            store.commit()
            return {"ok": True, "id": bid, "size": len(blob), "separate": separate}
        except Exception as e:
            try:
                store.rollback()
                if bid:
                    store.execute("UPDATE backups SET status='failed', error=?, finished_at=? WHERE id=?",
                                  (str(e)[:500], utcnow(), bid))
                    store.commit()
            except Exception:
                pass
            from .audit import notify_admins
            try:
                notify_admins("Backup failed", str(e)[:200], "error", db=primary)
                primary.commit()
            except Exception:
                pass
            return {"ok": False, "error": str(e)}
        finally:
            store.close()
            primary.close()


def due(app):
    with app.app_context():
        db = open_db()
        try:
            if get_setting("backup_enabled", db) != "1":
                return False
            hours = max(1, int(get_setting("backup_interval_hours", db) or 24))
        finally:
            db.close()
        store, _ = storage_db(app.config)
        try:
            last = store.val("SELECT MAX(created_at) FROM backups WHERE status IN ('success','running')")
        finally:
            store.close()
        return not last or last < past(hours=hours)


STATE = {"alive": False, "last_check": None}


def start_scheduler(app):
    if STATE["alive"]:
        return

    def loop():
        STATE["alive"] = True
        time.sleep(30)
        while True:
            try:
                STATE["last_check"] = utcnow()
                if due(app):
                    run_backup(app, "scheduled")
            except Exception:
                app.logger.exception("backup scheduler error")
            time.sleep(300)

    threading.Thread(target=loop, daemon=True, name="backup-scheduler").start()
