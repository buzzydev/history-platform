import json

from flask import g, has_request_context, request

from .db import get_db, utcnow


def audit(action, target_type=None, target_id=None, actor=None, **meta):
    db = get_db()
    actor = actor or (g.get("user") if has_request_context() else None)
    ip = ua = None
    if has_request_context():
        ip = request.remote_addr
        ua = (request.headers.get("User-Agent") or "")[:300]
    db.execute(
        "INSERT INTO audit_logs(actor_id,actor_username,action,target_type,target_id,metadata,ip,user_agent,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (actor["id"] if actor else None, actor["username"] if actor else None, action, target_type,
         None if target_id is None else str(target_id), json.dumps(meta, default=str, ensure_ascii=False), ip, ua, utcnow()))


def login_record(username, success, reason="", user_id=None, session_id=None):
    get_db().execute(
        "INSERT INTO login_history(user_id,username,success,reason,session_id,ip,user_agent,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (user_id, (username or "")[:60], 1 if success else 0, reason, session_id,
         request.remote_addr, (request.headers.get("User-Agent") or "")[:300], utcnow()))


def notify(user_id, title, body="", level="info", announcement=False, created_by=None, db=None):
    db = db or get_db()
    return db.insert(
        "INSERT INTO notifications(user_id,title,body,level,is_announcement,created_by,created_at) VALUES (?,?,?,?,?,?,?)",
        (user_id, title, body, level, 1 if announcement else 0, created_by, utcnow()))


def notify_admins(title, body="", level="info", db=None):
    db = db or get_db()
    for a in db.all("SELECT id FROM users WHERE role = 'admin' AND is_blocked = 0"):
        notify(a["id"], title, body, level, db=db)


def unread_count(user_id):
    return get_db().val(
        "SELECT COUNT(*) FROM notifications n WHERE (n.user_id = ? OR n.user_id IS NULL) AND NOT EXISTS "
        "(SELECT 1 FROM notification_reads r WHERE r.notification_id = n.id AND r.user_id = ?)",
        (user_id, user_id), 0)
