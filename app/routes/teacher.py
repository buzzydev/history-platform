from flask import Blueprint, Response, abort, g, render_template, request

from .. import exports
from ..audit import audit
from ..db import get_db, paginate
from ..helpers import page_arg
from ..security import perm_required, role_required

bp = Blueprint("teacher", __name__, url_prefix="/teacher")

RESULT_SQL = ("SELECT a.*, u.username, u.first_name, u.last_name, t.title FROM quiz_attempts a "
              "JOIN users u ON u.id = a.user_id JOIN test_collections t ON t.id = a.test_id "
              "WHERE a.status IN ('completed','expired') AND u.role = 'student'")


def result_filter(sql, params):
    q = request.args.get("q", "").strip().lower()
    if q:
        sql += " AND (LOWER(u.username) LIKE ? OR LOWER(u.first_name) LIKE ? OR LOWER(u.last_name) LIKE ?)"
        params += ["%" + q + "%"] * 3
    tid = request.args.get("test", "")
    if tid.isdigit():
        sql += " AND a.test_id = ?"
        params.append(int(tid))
    return sql, params, q, tid


@bp.get("/")
@role_required("teacher", "admin")
def dashboard():
    db = get_db()
    totals = db.one("SELECT COUNT(*) AS attempts, AVG(percentage) AS avg FROM quiz_attempts WHERE status IN ('completed','expired')")
    students = db.val("SELECT COUNT(*) FROM users WHERE role = 'student'", (), 0)
    subj = db.all("SELECT s.name, COUNT(a.id) AS attempts, AVG(a.percentage) AS avg FROM quiz_attempts a "
                  "JOIN test_collections t ON t.id = a.test_id JOIN subjects s ON s.id = t.subject_id "
                  "WHERE a.status IN ('completed','expired') GROUP BY s.name ORDER BY attempts DESC")
    recent = db.all(RESULT_SQL + " ORDER BY a.completed_at DESC, a.id DESC LIMIT 8")
    return render_template("teacher/dashboard.html", totals=totals, students=students, subj=subj, recent=recent)


@bp.get("/students")
@perm_required("view_students")
def students():
    db = get_db()
    sql = ("SELECT u.id, u.username, u.first_name, u.last_name, u.created_at, "
           "(SELECT COUNT(*) FROM quiz_attempts a WHERE a.user_id = u.id AND a.status IN ('completed','expired')) AS attempts, "
           "(SELECT AVG(percentage) FROM quiz_attempts a WHERE a.user_id = u.id AND a.status IN ('completed','expired')) AS avg "
           "FROM users u WHERE u.role = 'student'")
    params, q = [], request.args.get("q", "").strip().lower()
    if q:
        sql += " AND (LOWER(u.username) LIKE ? OR LOWER(u.first_name) LIKE ? OR LOWER(u.last_name) LIKE ?)"
        params = ["%" + q + "%"] * 3
    pg = paginate(db, sql, params, page_arg(), 20, "ORDER BY u.username")
    return render_template("teacher/students.html", pg=pg, q=q)


@bp.get("/students/<int:uid>")
@perm_required("view_results")
def student_detail(uid):
    db = get_db()
    s = db.one("SELECT id, username, first_name, last_name, created_at FROM users WHERE id = ? AND role = 'student'", (uid,))
    if not s:
        abort(404)
    from ..quiz import user_stats
    pg = paginate(db, "SELECT a.*, t.title FROM quiz_attempts a JOIN test_collections t ON t.id = a.test_id WHERE a.user_id = ?",
                  (uid,), page_arg(), 20, "ORDER BY a.started_at DESC, a.id DESC")
    return render_template("teacher/student_detail.html", s=s, pg=pg, stats=user_stats(db, uid))


@bp.get("/results")
@perm_required("view_results")
def results():
    db = get_db()
    sql, params, q, tid = result_filter(RESULT_SQL, [])
    pg = paginate(db, sql, params, page_arg(), 20, "ORDER BY a.completed_at DESC, a.id DESC")
    return render_template("teacher/results.html", pg=pg, q=q, tid=tid, base="teacher.results", export="teacher.export",
                           tests=db.all("SELECT id, title FROM test_collections ORDER BY title"))


@bp.get("/analytics")
@perm_required("view_analytics")
def analytics():
    db = get_db()
    hard = db.all(
        "SELECT q.id, q.text, t.title, COUNT(sa.id) AS answers, SUM(CASE WHEN sa.is_correct = 0 THEN 1 ELSE 0 END) AS wrong "
        "FROM student_answers sa JOIN questions q ON q.id = sa.question_id JOIN test_collections t ON t.id = q.test_id "
        "GROUP BY q.id, q.text, t.title HAVING COUNT(sa.id) >= 3 ORDER BY (1.0 * SUM(CASE WHEN sa.is_correct = 0 THEN 1 ELSE 0 END) / COUNT(sa.id)) DESC, COUNT(sa.id) DESC LIMIT 25")
    for h in hard:
        h["rate"] = round(100.0 * h["wrong"] / h["answers"])
    tests = db.all("SELECT t.title, COUNT(a.id) AS attempts, AVG(a.percentage) AS avg FROM test_collections t "
                   "JOIN quiz_attempts a ON a.test_id = t.id WHERE a.status IN ('completed','expired') "
                   "GROUP BY t.id, t.title ORDER BY attempts DESC LIMIT 25")
    return render_template("teacher/analytics.html", hard=hard, tests=tests)


@bp.get("/export.<fmt>")
@perm_required("export")
def export(fmt):
    if fmt not in ("xlsx", "pdf"):
        abort(404)
    db = get_db()
    sql, params, _, _ = result_filter(RESULT_SQL, [])
    rows = db.all(sql + " ORDER BY a.completed_at DESC LIMIT 5000", params)
    audit("export_results", "report", fmt, rows=len(rows))
    if fmt == "xlsx":
        return Response(exports.results_xlsx(rows), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": "attachment; filename=results.xlsx"})
    return Response(exports.results_pdf(rows), mimetype="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=results.pdf"})
