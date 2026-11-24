from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for, abort

from .. import quiz
from ..audit import audit, unread_count
from ..db import IntegrityError, get_db, paginate, utcnow
from ..helpers import page_arg
from ..security import (hash_password, login_required, normalize_phone, revoke_sessions, rl_blocked, rl_hit,
                        validate_password, verify_password)

bp = Blueprint("main", __name__)

AVAILABLE_SQL = (
    "SELECT t.*, s.name AS subject_name, gr.name AS grade_name, "
    "(SELECT COUNT(*) FROM questions q WHERE q.test_id = t.id AND q.status = 'approved') AS qcount, "
    "(SELECT COUNT(*) FROM quiz_attempts a WHERE a.test_id = t.id AND a.user_id = ?) AS my_attempts, "
    "(SELECT COUNT(*) FROM quiz_attempts a WHERE a.test_id = t.id AND a.user_id = ? AND a.status = 'in_progress') AS my_open "
    "FROM test_collections t JOIN subjects s ON s.id = t.subject_id LEFT JOIN grades gr ON gr.id = t.grade_id "
    "WHERE t.status = 'published' AND t.is_enabled = 1 AND (t.publish_at IS NULL OR t.publish_at <= ?) "
    "AND (t.expires_at IS NULL OR t.expires_at > ?)")


@bp.get("/")
def index():
    db = get_db()
    stats = {"tests": db.val("SELECT COUNT(*) FROM test_collections WHERE status='published' AND is_enabled=1", (), 0),
             "students": db.val("SELECT COUNT(*) FROM users WHERE role='student'", (), 0),
             "questions": db.val("SELECT COUNT(*) FROM questions WHERE status='approved'", (), 0)}
    return render_template("index.html", stats=stats)


@bp.get("/dashboard")
@login_required
def dashboard():
    if g.user["role"] == "admin":
        return redirect(url_for("admin.overview"))
    if g.user["role"] == "teacher":
        return redirect(url_for("teacher.dashboard"))
    db, uid, now = get_db(), g.user["id"], utcnow()
    tests = db.all(AVAILABLE_SQL + " ORDER BY t.created_at DESC, t.id DESC LIMIT 6", (uid, uid, now, now))
    recent = db.all(
        "SELECT a.*, t.title FROM quiz_attempts a JOIN test_collections t ON t.id = a.test_id "
        "WHERE a.user_id = ? ORDER BY a.started_at DESC, a.id DESC LIMIT 5", (uid,))
    notes = _notifications(db, uid, 5)
    return render_template("dashboard.html", tests=tests, recent=recent, stats=quiz.user_stats(db, uid), notes=notes)


@bp.get("/tests")
@login_required
def tests():
    db, uid, now = get_db(), g.user["id"], utcnow()
    sql, params = AVAILABLE_SQL, [uid, uid, now, now]
    q, sid, gid = request.args.get("q", "").strip(), request.args.get("subject", ""), request.args.get("grade", "")
    if q:
        sql += " AND LOWER(t.title) LIKE ?"
        params.append("%" + q.lower() + "%")
    if sid.isdigit():
        sql += " AND t.subject_id = ?"
        params.append(int(sid))
    if gid.isdigit():
        sql += " AND t.grade_id = ?"
        params.append(int(gid))
    pg = paginate(db, sql, params, page_arg(), 12, "ORDER BY t.created_at DESC, t.id DESC")
    return render_template("tests.html", pg=pg, q=q, sid=sid, gid=gid,
                           subjects=db.all("SELECT * FROM subjects ORDER BY name"),
                           grades=db.all("SELECT * FROM grades ORDER BY sort_order"))


@bp.get("/tests/<int:test_id>")
@login_required
def test_detail(test_id):
    db, uid, now = get_db(), g.user["id"], utcnow()
    t = db.one(AVAILABLE_SQL + " AND t.id = ?", (uid, uid, now, now, test_id))
    if not t:
        abort(404)
    attempts = db.all("SELECT * FROM quiz_attempts WHERE user_id = ? AND test_id = ? ORDER BY attempt_no DESC", (uid, test_id))
    return render_template("test_detail.html", t=t, attempts=attempts)


@bp.post("/tests/<int:test_id>/start")
@login_required
def start(test_id):
    if g.user["role"] != "student":
        flash("Only students can take tests. Admins and teachers can preview results.", "warning")
        return redirect(url_for("main.tests"))
    db = get_db()
    for _ in range(3):
        try:
            aid, new = quiz.start_or_resume(db, g.user, test_id)
            break
        except IntegrityError:
            db.rollback()
        except quiz.QuizError as e:
            db.rollback()
            flash(str(e), "error")
            return redirect(url_for("main.tests"))
    else:
        flash("Could not start the test. Please try again.", "error")
        return redirect(url_for("main.test_detail", test_id=test_id))
    if new:
        audit("quiz_started", "attempt", aid)
    return redirect(url_for("main.take", attempt_id=aid))


@bp.get("/quiz/<int:attempt_id>")
@login_required
def take(attempt_id):
    db = get_db()
    try:
        a = quiz.get_attempt_for(db, attempt_id, g.user["id"])
    except quiz.QuizError:
        abort(404)
    if a["status"] != "in_progress":
        return redirect(url_for("main.result", attempt_id=attempt_id))
    return render_template("quiz.html", attempt=a)


@bp.get("/attempts/<int:attempt_id>")
@login_required
def result(attempt_id):
    db = get_db()
    try:
        a = quiz.get_attempt_for(db, attempt_id, g.user["id"])
    except quiz.QuizError:
        abort(404)
    if a["status"] == "in_progress":
        return redirect(url_for("main.take", attempt_id=attempt_id))
    t = db.one("SELECT * FROM test_collections WHERE id = ?", (a["test_id"],))
    review = []
    if t["show_correct"] and t["show_results"]:
        review = db.all(
            "SELECT aq.position, q.text, q.explanation, sa.is_correct, "
            "(SELECT o.text FROM answer_options o WHERE o.id = sa.option_id) AS chosen, "
            "(SELECT o.text FROM answer_options o WHERE o.question_id = q.id AND o.is_correct = 1) AS right "
            "FROM attempt_questions aq JOIN questions q ON q.id = aq.question_id "
            "LEFT JOIN student_answers sa ON sa.attempt_id = aq.attempt_id AND sa.question_id = aq.question_id "
            "WHERE aq.attempt_id = ? ORDER BY aq.position", (attempt_id,))
    can_retry = not t["max_attempts"] or db.val(
        "SELECT COUNT(*) FROM quiz_attempts WHERE user_id = ? AND test_id = ?", (g.user["id"], t["id"]), 0) < t["max_attempts"]
    return render_template("result.html", a=a, t=t, review=review, can_retry=can_retry)


@bp.get("/history")
@login_required
def history():
    db = get_db()
    pg = paginate(db, "SELECT a.*, t.title FROM quiz_attempts a JOIN test_collections t ON t.id = a.test_id WHERE a.user_id = ?",
                  (g.user["id"],), page_arg(), 15, "ORDER BY a.started_at DESC, a.id DESC")
    return render_template("history.html", pg=pg)


@bp.get("/leaderboard")
@login_required
def leaderboard():
    db = get_db()
    return render_template("leaderboard.html", rows=quiz.leaderboard(db, 100),
                           min_attempts=db.val("SELECT v FROM settings WHERE k='leaderboard_min_attempts'", (), "3"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db, u, errors = get_db(), g.user, {}
    if request.method == "POST":
        action = request.form.get("action")
        if action == "info":
            first, last = request.form.get("first_name", "").strip(), request.form.get("last_name", "").strip()
            phone = normalize_phone(request.form.get("phone", ""))
            if not first or not last:
                errors["info"] = "First and last name are required."
            elif not phone:
                errors["info"] = "Enter a valid phone number."
            elif db.val("SELECT 1 FROM users WHERE phone = ? AND id <> ?", (phone, u["id"])):
                errors["info"] = "This phone number is already used by another account."
            else:
                db.execute("UPDATE users SET first_name=?, last_name=?, phone=?, updated_at=? WHERE id=?",
                           (first[:60], last[:60], phone, utcnow(), u["id"]))
                audit("profile_updated", "user", u["id"])
                flash("Profile updated.", "success")
                return redirect(url_for("main.profile"))
        elif action == "password":
            key = f"pwchange:{u['id']}"
            if rl_blocked(key, 5, 3600):
                errors["password"] = "Too many attempts. Try again later."
            else:
                rl_hit(key)
                cur, new, new2 = request.form.get("current_password", ""), request.form.get("new_password", ""), request.form.get("new_password_confirm", "")
                pe = validate_password(new)
                if not verify_password(u["password_hash"], cur):
                    errors["password"] = "Current password is incorrect."
                elif pe:
                    errors["password"] = " ".join(pe)
                elif new != new2:
                    errors["password"] = "New passwords do not match."
                else:
                    db.execute("UPDATE users SET password_hash=?, updated_at=? WHERE id=?", (hash_password(new), utcnow(), u["id"]))
                    revoke_sessions(u["id"], except_sid=g.sid)
                    audit("password_changed", "user", u["id"])
                    flash("Password changed. Other devices were signed out.", "success")
                    return redirect(url_for("main.profile"))
        if errors:
            flash(next(iter(errors.values())), "error")
    u = db.one("SELECT * FROM users WHERE id = ?", (u["id"],))
    recent = db.all("SELECT a.*, t.title FROM quiz_attempts a JOIN test_collections t ON t.id = a.test_id "
                    "WHERE a.user_id = ? ORDER BY a.started_at DESC, a.id DESC LIMIT 8", (u["id"],))
    return render_template("profile.html", u=u, stats=quiz.user_stats(db, u["id"]), recent=recent, errors=errors)


def _notifications(db, uid, limit):
    return db.all(
        "SELECT n.*, (SELECT COUNT(*) FROM notification_reads r WHERE r.notification_id = n.id AND r.user_id = ?) AS is_read "
        "FROM notifications n WHERE n.user_id = ? OR n.user_id IS NULL ORDER BY n.created_at DESC, n.id DESC LIMIT " + str(limit),
        (uid, uid))


@bp.get("/notifications")
@login_required
def notifications():
    return render_template("notifications.html", notes=_notifications(get_db(), g.user["id"], 100))


@bp.post("/api/notifications/read")
@login_required
def notifications_read():
    db, uid = get_db(), g.user["id"]
    ids = [r["id"] for r in db.all(
        "SELECT n.id FROM notifications n WHERE (n.user_id = ? OR n.user_id IS NULL) AND NOT EXISTS "
        "(SELECT 1 FROM notification_reads r WHERE r.notification_id = n.id AND r.user_id = ?)", (uid, uid))]
    for i in ids:
        db.execute("INSERT INTO notification_reads(notification_id,user_id,read_at) VALUES (?,?,?)", (i, uid, utcnow()))
    return jsonify(ok=True, unread=0)
