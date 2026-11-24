import hashlib
import json
import secrets
import time

from flask import (Blueprint, Response, abort, flash, g, jsonify, redirect, render_template, request, url_for)

from .. import backup as backup_mod, exports, pdfimport
from ..audit import audit, notify, notify_admins
from ..db import DEFAULT_SETTINGS, IntegrityError, future, get_db, get_setting, paginate, set_setting, utcnow
from ..helpers import form_flag, form_int, local_to_utc, page_arg, utc_to_local_input
from ..security import (USERNAME_RE, normalize_phone, revoke_sessions, role_required)

bp = Blueprint("admin", __name__, url_prefix="/admin")
TEACHER_PERMS = {"view_students": "View students", "view_results": "View quiz results and history",
                 "view_analytics": "View analytics", "export": "Export reports"}


@bp.before_request
def _guard():
    # Every admin endpoint is admin-only, verified on the server for every request.
    if not g.user:
        from ..security import deny
        return deny(401)
    if g.user["role"] != "admin":
        from ..security import deny
        return deny(403)


# ---------------- overview ----------------
@bp.get("/")
def overview():
    db = get_db()
    c = {k: db.val(sql, (), 0) for k, sql in {
        "users": "SELECT COUNT(*) FROM users", "students": "SELECT COUNT(*) FROM users WHERE role='student'",
        "teachers": "SELECT COUNT(*) FROM users WHERE role='teacher'",
        "tests": "SELECT COUNT(*) FROM test_collections", "published": "SELECT COUNT(*) FROM test_collections WHERE status='published'",
        "questions": "SELECT COUNT(*) FROM questions WHERE status='approved'",
        "pending": "SELECT COUNT(*) FROM questions WHERE status='pending'",
        "attempts": "SELECT COUNT(*) FROM quiz_attempts WHERE status IN ('completed','expired')",
        "open": "SELECT COUNT(*) FROM quiz_attempts WHERE status='in_progress'"}.items()}
    from flask import current_app
    store, _ = backup_mod.storage_db(current_app.config)
    try:
        last_backup = store.one("SELECT id, status, created_at FROM backups ORDER BY id DESC LIMIT 1")
    finally:
        store.close()
    failed = db.all("SELECT * FROM login_history WHERE success = 0 ORDER BY id DESC LIMIT 5")
    recent = db.all("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 8")
    return render_template("admin/dashboard.html", c=c, last_backup=last_backup, failed=failed, recent=recent)


# ---------------- users ----------------
@bp.get("/users")
def users():
    db = get_db()
    sql, params = "SELECT * FROM users WHERE 1=1", []
    q, role, st = request.args.get("q", "").strip().lower(), request.args.get("role", ""), request.args.get("status", "")
    if q:
        sql += " AND (LOWER(username) LIKE ? OR LOWER(first_name) LIKE ? OR LOWER(last_name) LIKE ? OR phone LIKE ?)"
        params += ["%" + q + "%"] * 4
    if role in ("student", "teacher", "admin"):
        sql += " AND role = ?"
        params.append(role)
    if st == "blocked":
        sql += " AND is_blocked = 1"
    pg = paginate(db, sql, params, page_arg(), 20, "ORDER BY created_at DESC, id DESC")
    return render_template("admin/users.html", pg=pg, q=q, role=role, st=st)


def _user_or_404(uid):
    u = get_db().one("SELECT * FROM users WHERE id = ?", (uid,))
    if not u:
        abort(404)
    return u


def _admin_count():
    return get_db().val("SELECT COUNT(*) FROM users WHERE role='admin' AND is_blocked=0", (), 0)


@bp.route("/users/<int:uid>/edit", methods=["GET", "POST"])
def user_edit(uid):
    db, u, errors = get_db(), _user_or_404(uid), {}
    if request.method == "POST":
        first, last = request.form.get("first_name", "").strip(), request.form.get("last_name", "").strip()
        phone = normalize_phone(request.form.get("phone", ""))
        role = request.form.get("role", u["role"])
        if role not in ("student", "teacher", "admin"):
            abort(400)
        if not first or not last:
            errors["name"] = "First and last name are required."
        elif not phone:
            errors["phone"] = "Enter a valid phone number."
        elif db.val("SELECT 1 FROM users WHERE phone = ? AND id <> ?", (phone, uid)):
            errors["phone"] = "This phone number belongs to another account."
        if uid == g.user["id"] and role != "admin":
            errors["role"] = "You cannot remove your own administrator role."
        if u["role"] == "admin" and role != "admin" and _admin_count() <= 1:
            errors["role"] = "At least one administrator is required."
        if not errors:
            perms = {k: 1 for k in TEACHER_PERMS if request.form.get("perm_" + k)} if role == "teacher" else {}
            db.execute("UPDATE users SET first_name=?, last_name=?, phone=?, role=?, teacher_perms=?, updated_at=? WHERE id=?",
                       (first[:60], last[:60], phone, role, json.dumps(perms), utcnow(), uid))
            if role != u["role"]:
                audit("role_changed", "user", uid, old=u["role"], new=role)
                if role == "teacher":
                    audit("teacher_appointed", "user", uid)
                    notify(uid, "You are now a teacher", "An administrator granted you teacher access.", "info")
                elif u["role"] == "teacher":
                    audit("teacher_removed", "user", uid)
                revoke_sessions(uid)
            audit("user_updated", "user", uid)
            flash("User updated.", "success")
            return redirect(url_for("admin.users"))
        flash(next(iter(errors.values())), "error")
    import json as _j
    try:
        perms = _j.loads(u["teacher_perms"] or "{}")
    except ValueError:
        perms = {}
    return render_template("admin/user_edit.html", u=u, perms=perms, perm_labels=TEACHER_PERMS, errors=errors)


@bp.post("/users/<int:uid>/block")
def user_block(uid):
    u, db = _user_or_404(uid), get_db()
    if uid == g.user["id"]:
        flash("You cannot block yourself.", "error")
    elif u["role"] == "admin" and _admin_count() <= 1:
        flash("At least one administrator must stay active.", "error")
    else:
        blocking = not u["is_blocked"]
        db.execute("UPDATE users SET is_blocked = ?, updated_at = ? WHERE id = ?", (1 if blocking else 0, utcnow(), uid))
        if blocking:
            revoke_sessions(uid)
        audit("user_blocked" if blocking else "user_unblocked", "user", uid)
        flash("Account blocked." if blocking else "Account unblocked.", "warning" if blocking else "success")
    return redirect(request.referrer or url_for("admin.users"))


@bp.post("/users/<int:uid>/delete")
def user_delete(uid):
    u, db = _user_or_404(uid), get_db()
    if uid == g.user["id"]:
        flash("You cannot delete your own account.", "error")
    elif u["role"] == "admin":
        flash("Change this administrator to another role before deleting the account.", "error")
    else:
        db.execute("DELETE FROM users WHERE id = ?", (uid,))
        audit("user_deleted", "user", uid, username=u["username"])
        flash(f"User {u['username']} deleted.", "success")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:uid>/reset-link")
def user_reset_link(uid):
    u, db = _user_or_404(uid), get_db()
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO password_resets(user_id,token_hash,expires_at,created_by,created_at) VALUES (?,?,?,?,?)",
               (uid, hashlib.sha256(token.encode()).hexdigest(), future(hours=1), g.user["id"], utcnow()))
    audit("password_reset_issued", "user", uid)
    link = url_for("auth.reset", token=token, _external=True)
    return render_template("admin/reset_link.html", u=u, link=link)


# ---------------- grades / subjects ----------------
CATALOG = {"grades": ("grades", "Grades", "sort_order, name"), "subjects": ("subjects", "Subjects", "name")}


def _catalog(kind):
    if kind not in CATALOG:
        abort(404)
    return CATALOG[kind]


@bp.route("/catalog/<kind>", methods=["GET", "POST"])
def catalog(kind):
    table, label, order = _catalog(kind)
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name or len(name) > 80:
            flash("Name is required (max 80 characters).", "error")
        else:
            try:
                if kind == "grades":
                    db.insert("INSERT INTO grades(name,sort_order,created_at) VALUES (?,?,?)",
                              (name, form_int("sort_order", 0), utcnow()))
                else:
                    db.insert("INSERT INTO subjects(name,description,created_at) VALUES (?,?,?)",
                              (name, request.form.get("description", "").strip()[:300], utcnow()))
                audit(f"{kind[:-1]}_created", kind[:-1], name)
                flash(f"{label[:-1]} created.", "success")
            except IntegrityError:
                db.rollback()
                flash("This name already exists.", "error")
        return redirect(url_for("admin.catalog", kind=kind))
    rows = db.all(f"SELECT * FROM {table} ORDER BY {order}")
    for r in rows:
        col = "subject_id" if kind == "subjects" else "grade_id"
        r["uses"] = db.val(f"SELECT COUNT(*) FROM test_collections WHERE {col} = ?", (r["id"],), 0)
    return render_template("admin/catalog.html", kind=kind, label=label, rows=rows)


@bp.post("/catalog/<kind>/<int:rid>/edit")
def catalog_edit(kind, rid):
    table, label, _ = _catalog(kind)
    db, name = get_db(), request.form.get("name", "").strip()
    if not name:
        flash("Name is required.", "error")
    else:
        try:
            if kind == "grades":
                db.execute("UPDATE grades SET name=?, sort_order=? WHERE id=?", (name, form_int("sort_order", 0), rid))
            else:
                db.execute("UPDATE subjects SET name=?, description=? WHERE id=?",
                           (name, request.form.get("description", "").strip()[:300], rid))
            audit(f"{kind[:-1]}_updated", kind[:-1], rid)
            flash("Saved.", "success")
        except IntegrityError:
            db.rollback()
            flash("This name already exists.", "error")
    return redirect(url_for("admin.catalog", kind=kind))


@bp.post("/catalog/<kind>/<int:rid>/delete")
def catalog_delete(kind, rid):
    table, label, _ = _catalog(kind)
    db = get_db()
    col = "subject_id" if kind == "subjects" else "grade_id"
    if kind == "subjects" and db.val(f"SELECT COUNT(*) FROM test_collections WHERE {col} = ?", (rid,), 0):
        flash("This subject still has tests. Move or delete them first.", "error")
    else:
        db.execute(f"DELETE FROM {table} WHERE id = ?", (rid,))
        audit(f"{kind[:-1]}_deleted", kind[:-1], rid)
        flash("Deleted.", "success")
    return redirect(url_for("admin.catalog", kind=kind))


# ---------------- tests ----------------
def _test_or_404(tid):
    t = get_db().one("SELECT * FROM test_collections WHERE id = ?", (tid,))
    if not t:
        abort(404)
    return t


@bp.get("/tests")
def tests():
    db = get_db()
    sql = ("SELECT t.*, s.name AS subject_name, gr.name AS grade_name, "
           "(SELECT COUNT(*) FROM questions q WHERE q.test_id = t.id AND q.status='approved') AS approved, "
           "(SELECT COUNT(*) FROM questions q WHERE q.test_id = t.id AND q.status='pending') AS pending "
           "FROM test_collections t JOIN subjects s ON s.id = t.subject_id LEFT JOIN grades gr ON gr.id = t.grade_id WHERE 1=1")
    params, q = [], request.args.get("q", "").strip().lower()
    if q:
        sql += " AND LOWER(t.title) LIKE ?"
        params.append("%" + q + "%")
    pg = paginate(db, sql, params, page_arg(), 20, "ORDER BY t.created_at DESC, t.id DESC")
    return render_template("admin/tests.html", pg=pg, q=q)


def _test_form_values(existing=None):
    f = request.form
    title = f.get("title", "").strip()
    errors = []
    if not title or len(title) > 150:
        errors.append("Title is required (max 150 characters).")
    sid = form_int("subject_id", 0)
    if not get_db().val("SELECT 1 FROM subjects WHERE id = ?", (sid,)):
        errors.append("Choose a subject.")
    gid = form_int("grade_id", 0) or None
    vals = dict(title=title, subject_id=sid, grade_id=gid, description=f.get("description", "").strip()[:1000],
                questions_per_attempt=form_int("questions_per_attempt", 20, 1, 500),
                time_limit_minutes=form_int("time_limit_minutes", 0, 0, 600),
                max_attempts=form_int("max_attempts", 0, 0, 1000),
                randomize_questions=form_flag("randomize_questions"), randomize_options=form_flag("randomize_options"),
                show_correct=form_flag("show_correct"), show_explanation=form_flag("show_explanation"),
                show_results=form_flag("show_results"), is_enabled=form_flag("is_enabled"),
                publish_at=local_to_utc(f.get("publish_at")), expires_at=local_to_utc(f.get("expires_at")))
    if vals["publish_at"] and vals["expires_at"] and vals["expires_at"] <= vals["publish_at"]:
        errors.append("Expiration must be after the publication date.")
    return vals, errors


def _test_ctx():
    db = get_db()
    return dict(subjects=db.all("SELECT * FROM subjects ORDER BY name"), grades=db.all("SELECT * FROM grades ORDER BY sort_order"),
                local=utc_to_local_input)


@bp.route("/tests/new", methods=["GET", "POST"])
def test_new():
    if request.method == "POST":
        vals, errors = _test_form_values()
        if not errors:
            cols = list(vals)
            now = utcnow()
            tid = get_db().insert(
                f"INSERT INTO test_collections({','.join(cols)},created_by,created_at,updated_at) VALUES ({','.join('?' * len(cols))},?,?,?)",
                [vals[c] for c in cols] + [g.user["id"], now, now])
            audit("test_created", "test", tid, title=vals["title"])
            flash("Test created. Now add questions.", "success")
            return redirect(url_for("admin.test_questions", tid=tid))
        for e in errors:
            flash(e, "error")
        t = dict(vals)
    else:
        t = dict(title="", subject_id=0, grade_id=None, description="",
                 questions_per_attempt=int(get_setting("default_questions_per_attempt")),
                 time_limit_minutes=int(get_setting("default_time_limit_minutes")),
                 max_attempts=int(get_setting("default_max_attempts")), randomize_questions=1, randomize_options=1,
                 show_correct=int(get_setting("default_show_correct")), show_explanation=1, show_results=1, is_enabled=1,
                 publish_at=None, expires_at=None)
    return render_template("admin/test_form.html", t=t, is_new=True, **_test_ctx())


@bp.route("/tests/<int:tid>/edit", methods=["GET", "POST"])
def test_edit(tid):
    t = _test_or_404(tid)
    if request.method == "POST":
        vals, errors = _test_form_values(t)
        if not errors:
            sets = ", ".join(f"{c}=?" for c in vals)
            get_db().execute(f"UPDATE test_collections SET {sets}, updated_at=? WHERE id=?", list(vals.values()) + [utcnow(), tid])
            audit("test_updated", "test", tid, title=vals["title"])
            flash("Test settings saved.", "success")
            return redirect(url_for("admin.tests"))
        for e in errors:
            flash(e, "error")
        t = {**t, **vals}
    return render_template("admin/test_form.html", t=t, is_new=False, **_test_ctx())


@bp.post("/tests/<int:tid>/delete")
def test_delete(tid):
    t = _test_or_404(tid)
    db = get_db()
    # question rows referenced by attempts are RESTRICTed: remove attempts first (cascade), then the test.
    db.execute("DELETE FROM quiz_attempts WHERE test_id = ?", (tid,))
    db.execute("DELETE FROM test_collections WHERE id = ?", (tid,))
    audit("test_deleted", "test", tid, title=t["title"])
    flash("Test deleted together with its attempts.", "success")
    return redirect(url_for("admin.tests"))


@bp.post("/tests/<int:tid>/toggle")
def test_toggle(tid):
    t = _test_or_404(tid)
    get_db().execute("UPDATE test_collections SET is_enabled = ?, updated_at = ? WHERE id = ?",
                     (0 if t["is_enabled"] else 1, utcnow(), tid))
    audit("test_disabled" if t["is_enabled"] else "test_enabled", "test", tid)
    flash("Test disabled." if t["is_enabled"] else "Test enabled.", "info")
    return redirect(request.referrer or url_for("admin.tests"))


@bp.post("/tests/<int:tid>/publish")
def test_publish(tid):
    t, db = _test_or_404(tid), get_db()
    approved = db.val("SELECT COUNT(*) FROM questions WHERE test_id=? AND status='approved'", (tid,), 0)
    pending = db.val("SELECT COUNT(*) FROM questions WHERE test_id=? AND status='pending'", (tid,), 0)
    if request.form.get("action") == "unpublish":
        db.execute("UPDATE test_collections SET status='draft', updated_at=? WHERE id=?", (utcnow(), tid))
        audit("test_unpublished", "test", tid)
        flash("Test moved back to draft.", "info")
    elif approved == 0:
        flash("Approve at least one question before publishing.", "error")
    elif pending:
        flash(f"{pending} question(s) are still awaiting approval. Review and approve them first.", "error")
    else:
        db.execute("UPDATE test_collections SET status='published', updated_at=? WHERE id=?", (utcnow(), tid))
        audit("test_published", "test", tid, title=t["title"], questions=approved)
        flash("Test published. Students can now take it.", "success")
    return redirect(request.referrer or url_for("admin.tests"))


# ---------------- question review / editor ----------------
@bp.get("/tests/<int:tid>/questions")
def test_questions(tid):
    t = _test_or_404(tid)
    doc = get_db().one("SELECT id, filename, method, page_count, warnings, created_at FROM uploaded_documents "
                       "WHERE test_id = ? ORDER BY id DESC LIMIT 1", (tid,))
    return render_template("admin/questions.html", t=t, doc=doc)


def _questions_json(db, tid):
    out = []
    for q in db.all("SELECT * FROM questions WHERE test_id = ? AND status <> 'archived' ORDER BY position, id", (tid,)):
        opts = db.all("SELECT id, text, is_correct FROM answer_options WHERE question_id = ? ORDER BY position, id", (q["id"],))
        out.append({"id": q["id"], "text": q["text"], "explanation": q["explanation"], "status": q["status"],
                    "needs_review": bool(q["needs_review"]), "confidence": q["confidence"],
                    "warnings": json.loads(q["warnings"] or "[]"),
                    "options": [{"id": o["id"], "text": o["text"], "is_correct": bool(o["is_correct"])} for o in opts]})
    return out


def _validate_q(q):
    errs = []
    if not (q.get("text") or "").strip():
        errs.append("question text is empty")
    opts = [o for o in q.get("options", []) if (o.get("text") or "").strip()]
    if len(opts) != len(q.get("options", [])):
        errs.append("an option is empty")
    if len(q.get("options", [])) < 2:
        errs.append("needs at least two options")
    if sum(1 for o in q.get("options", []) if o.get("is_correct")) != 1:
        errs.append("select exactly one correct answer")
    return errs


@bp.get("/api/tests/<int:tid>/questions")
def api_questions(tid):
    _test_or_404(tid)
    return jsonify(questions=_questions_json(get_db(), tid))


@bp.post("/api/tests/<int:tid>/questions")
def api_questions_save(tid):
    _test_or_404(tid)
    db = get_db()
    data = request.get_json(silent=True) or {}
    items = data.get("questions")
    if not isinstance(items, list) or len(items) > 2000:
        return jsonify(error="Invalid payload."), 400
    approve = bool(data.get("approve"))
    problems = []
    for i, q in enumerate(items):
        if not isinstance(q, dict) or not isinstance(q.get("options", []), list) or len(q.get("options", [])) > 10:
            return jsonify(error="Invalid payload."), 400
        e = _validate_q(q)
        if e:
            problems.append({"index": i, "errors": e})
    if approve and problems:
        return jsonify(error=f"{len(problems)} question(s) are incomplete.", problems=problems), 422
    existing = {r["id"]: r for r in db.all("SELECT * FROM questions WHERE test_id = ? AND status <> 'archived'", (tid,))}
    keep, now = set(), utcnow()
    for pos, q in enumerate(items):
        valid = not _validate_q(q)
        text, expl = q["text"].strip()[:2000], (q.get("explanation") or "").strip()[:2000]
        qid = q.get("id") if q.get("id") in existing else None
        opt_texts = [(o.get("text") or "").strip()[:500] for o in q.get("options", [])]
        h = pdfimport.question_hash(text, opt_texts)
        if qid:
            st = "approved" if (valid and (approve or existing[qid]["status"] == "approved")) else "pending"
            db.execute("UPDATE questions SET text=?, explanation=?, position=?, status=?, needs_review=?, content_hash=?, updated_at=? WHERE id=?",
                       (text, expl, pos, st, 0 if valid else 1, h, now, qid))
        else:
            st = "approved" if (valid and approve) else "pending"
            qid = db.insert("INSERT INTO questions(test_id,text,explanation,position,status,needs_review,confidence,content_hash,created_at,updated_at) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?)", (tid, text, expl, pos, st, 0 if valid else 1, 1.0, h, now, now))
        keep.add(qid)
        old_opts = {o["id"]: o for o in db.all("SELECT id FROM answer_options WHERE question_id = ?", (qid,))}
        used = set()
        for op, o in enumerate(q.get("options", [])):
            ot, oc = (o.get("text") or "").strip()[:500], 1 if o.get("is_correct") else 0
            if o.get("id") in old_opts and o["id"] not in used:
                db.execute("UPDATE answer_options SET text=?, is_correct=?, position=? WHERE id=?", (ot, oc, op, o["id"]))
                used.add(o["id"])
            else:
                used.add(db.insert("INSERT INTO answer_options(question_id,text,is_correct,position) VALUES (?,?,?,?)", (qid, ot, oc, op)))
        for oid in set(old_opts) - used:
            db.execute("DELETE FROM answer_options WHERE id = ?", (oid,))
    for qid in set(existing) - keep:
        if db.val("SELECT 1 FROM attempt_questions WHERE question_id = ?", (qid,)):
            db.execute("UPDATE questions SET status='archived', updated_at=? WHERE id=?", (now, qid))
        else:
            db.execute("DELETE FROM questions WHERE id = ?", (qid,))
    audit("questions_approved" if approve else "questions_saved", "test", tid, count=len(items))
    return jsonify(ok=True, questions=_questions_json(db, tid), problems=problems)


# ---------------- PDF import ----------------
@bp.route("/pdf", methods=["GET", "POST"])
def pdf():
    db = get_db()
    if request.method == "POST":
        f = request.files.get("file")
        title = request.form.get("title", "").strip()
        sid = form_int("subject_id", 0)
        target = form_int("test_id", 0)
        if not f or not f.filename or not f.filename.lower().endswith(".pdf"):
            flash("Choose a PDF file (.pdf).", "error")
            return redirect(url_for("admin.pdf"))
        data = f.read()
        if not data:
            flash("The file is empty.", "error")
            return redirect(url_for("admin.pdf"))
        if not target and (not title or not db.val("SELECT 1 FROM subjects WHERE id = ?", (sid,))):
            flash("Enter a collection name and choose a subject.", "error")
            return redirect(url_for("admin.pdf"))
        t0 = time.time()
        try:
            res = pdfimport.process_pdf(data, current_max_pages(), current_ocr())
        except pdfimport.PdfError as e:
            audit("pdf_extraction_failed", "document", f.filename, error=str(e))
            notify_admins("PDF extraction failed", f"{f.filename}: {e}", "error")
            flash(f"PDF extraction failed: {e}", "error")
            return redirect(url_for("admin.pdf"))
        now, sha = utcnow(), hashlib.sha256(data).hexdigest()
        if target:
            t = _test_or_404(target)
            tid = t["id"]
        else:
            tid = db.insert(
                "INSERT INTO test_collections(title,subject_id,grade_id,description,questions_per_attempt,time_limit_minutes,max_attempts,"
                "show_correct,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (title[:150], sid, form_int("grade_id", 0) or None, "", int(get_setting("default_questions_per_attempt")),
                 int(get_setting("default_time_limit_minutes")), int(get_setting("default_max_attempts")),
                 int(get_setting("default_show_correct")), g.user["id"], now, now))
        warnings = list(res["warnings"])
        if db.val("SELECT 1 FROM uploaded_documents WHERE sha256 = ?", (sha,)):
            warnings.append("This exact file was uploaded before.")
        existing = {r["content_hash"] for r in db.all("SELECT content_hash FROM questions WHERE test_id = ? AND status <> 'archived'", (tid,))}
        doc_id = db.insert(
            "INSERT INTO uploaded_documents(test_id,filename,sha256,size_bytes,page_count,method,status,questions_found,warnings,data,uploaded_by,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, f.filename[:200], sha, len(data), res["page_count"], res["method"], "processed", len(res["questions"]),
             json.dumps(warnings, ensure_ascii=False), data, g.user["id"], now))
        pos = db.val("SELECT COALESCE(MAX(position), -1) FROM questions WHERE test_id = ?", (tid,), -1) + 1
        added = skipped = 0
        for q in res["questions"]:
            if q["hash"] in existing:
                skipped += 1
                continue
            qid = db.insert(
                "INSERT INTO questions(test_id,text,position,status,needs_review,confidence,warnings,document_id,content_hash,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (tid, q["text"], pos, "pending", 1 if q["needs_review"] else 0, q["confidence"],
                 json.dumps(q["warnings"], ensure_ascii=False), doc_id, q["hash"], now, now))
            pos += 1
            for i, o in enumerate(q["options"]):
                db.execute("INSERT INTO answer_options(question_id,text,is_correct,position) VALUES (?,?,?,?)",
                           (qid, o["text"], 1 if o["is_correct"] else 0, i))
            existing.add(q["hash"])
            added += 1
        audit("pdf_uploaded", "document", doc_id, filename=f.filename, test_id=tid, added=added, skipped_duplicates=skipped,
              method=res["method"], seconds=round(time.time() - t0, 1))
        flash(f"Extracted {added} question(s)" + (f", skipped {skipped} duplicate(s)" if skipped else "") +
              ". Review and approve them before publishing.", "success" if added else "warning")
        return redirect(url_for("admin.test_questions", tid=tid))
    docs = db.all("SELECT d.id, d.filename, d.size_bytes, d.page_count, d.method, d.questions_found, d.created_at, d.test_id, "
                  "t.title FROM uploaded_documents d LEFT JOIN test_collections t ON t.id = d.test_id ORDER BY d.id DESC LIMIT 30")
    return render_template("admin/pdf.html", docs=docs, subjects=db.all("SELECT * FROM subjects ORDER BY name"),
                           grades=db.all("SELECT * FROM grades ORDER BY sort_order"),
                           tests=db.all("SELECT id, title FROM test_collections ORDER BY title"))


def current_max_pages():
    from flask import current_app
    return current_app.config["PDF_MAX_PAGES"]


def current_ocr():
    from flask import current_app
    return current_app.config["OCR_LANGS"]


@bp.get("/pdf/<int:did>/download")
def pdf_download(did):
    d = get_db().one("SELECT filename, data FROM uploaded_documents WHERE id = ?", (did,))
    if not d:
        abort(404)
    audit("pdf_downloaded", "document", did)
    safe = "".join(c for c in d["filename"] if c.isalnum() or c in "._- ") or "document.pdf"
    return Response(d["data"], mimetype="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe}"'})


# ---------------- attempts / results ----------------
@bp.get("/attempts")
def attempts():
    db = get_db()
    sql = ("SELECT a.*, u.username, u.first_name, u.last_name, t.title FROM quiz_attempts a JOIN users u ON u.id = a.user_id "
           "JOIN test_collections t ON t.id = a.test_id WHERE 1=1")
    params, q, st = [], request.args.get("q", "").strip().lower(), request.args.get("status", "")
    if q:
        sql += " AND (LOWER(u.username) LIKE ? OR LOWER(t.title) LIKE ?)"
        params += ["%" + q + "%"] * 2
    if st in ("in_progress", "completed", "expired"):
        sql += " AND a.status = ?"
        params.append(st)
    pg = paginate(db, sql, params, page_arg(), 25, "ORDER BY a.started_at DESC, a.id DESC")
    return render_template("admin/attempts.html", pg=pg, q=q, st=st)


@bp.post("/attempts/<int:aid>/delete")
def attempt_delete(aid):
    db = get_db()
    a = db.one("SELECT * FROM quiz_attempts WHERE id = ?", (aid,))
    if not a:
        abort(404)
    db.execute("DELETE FROM quiz_attempts WHERE id = ?", (aid,))
    audit("attempt_deleted", "attempt", aid, user_id=a["user_id"], test_id=a["test_id"])
    flash("Attempt deleted (the student gets this attempt back).", "success")
    return redirect(request.referrer or url_for("admin.attempts"))


@bp.get("/results")
def results():
    from .teacher import RESULT_SQL, result_filter
    db = get_db()
    sql, params, q, tid = result_filter(RESULT_SQL, [])
    pg = paginate(db, sql, params, page_arg(), 25, "ORDER BY a.completed_at DESC, a.id DESC")
    return render_template("teacher/results.html", pg=pg, q=q, tid=tid, base="admin.results", export="admin.export",
                           tests=db.all("SELECT id, title FROM test_collections ORDER BY title"))


@bp.get("/export.<fmt>")
def export(fmt):
    from .teacher import RESULT_SQL, result_filter
    if fmt not in ("xlsx", "pdf"):
        abort(404)
    db = get_db()
    sql, params, _, _ = result_filter(RESULT_SQL, [])
    rows = db.all(sql + " ORDER BY a.completed_at DESC LIMIT 5000", params)
    audit("export_results", "report", fmt, rows=len(rows))
    if fmt == "xlsx":
        return Response(exports.results_xlsx(rows), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": "attachment; filename=results.xlsx"})
    return Response(exports.results_pdf(rows), mimetype="application/pdf", headers={"Content-Disposition": "attachment; filename=results.pdf"})


@bp.get("/leaderboard")
def leaderboard():
    from .. import quiz
    db = get_db()
    return render_template("leaderboard.html", rows=quiz.leaderboard(db, 200), min_attempts=get_setting("leaderboard_min_attempts"))


# ---------------- audit / logins ----------------
@bp.get("/audit")
def audit_log():
    db = get_db()
    sql, params = "SELECT * FROM audit_logs WHERE 1=1", []
    f = {k: request.args.get(k, "").strip() for k in ("user", "action", "target", "from", "to")}
    if f["user"]:
        sql += " AND LOWER(actor_username) LIKE ?"
        params.append("%" + f["user"].lower() + "%")
    if f["action"]:
        sql += " AND action = ?"
        params.append(f["action"])
    if f["target"]:
        sql += " AND target_type = ?"
        params.append(f["target"])
    if f["from"]:
        sql += " AND created_at >= ?"
        params.append(f["from"] + " 00:00:00")
    if f["to"]:
        sql += " AND created_at <= ?"
        params.append(f["to"] + " 23:59:59")
    pg = paginate(db, sql, params, page_arg(), 30, "ORDER BY id DESC")
    actions = [r["action"] for r in db.all("SELECT DISTINCT action FROM audit_logs ORDER BY action")]
    targets = [r["target_type"] for r in db.all("SELECT DISTINCT target_type FROM audit_logs WHERE target_type IS NOT NULL ORDER BY target_type")]
    return render_template("admin/audit.html", pg=pg, f=f, actions=actions, targets=targets)


@bp.get("/logins")
def logins():
    db = get_db()
    sql, params = "SELECT * FROM login_history WHERE 1=1", []
    q, ok = request.args.get("q", "").strip().lower(), request.args.get("ok", "")
    if q:
        sql += " AND LOWER(username) LIKE ?"
        params.append("%" + q + "%")
    if ok in ("0", "1"):
        sql += " AND success = ?"
        params.append(int(ok))
    pg = paginate(db, sql, params, page_arg(), 30, "ORDER BY id DESC")
    return render_template("admin/logins.html", pg=pg, q=q, ok=ok)


# ---------------- notifications / settings / backups / health ----------------
@bp.route("/notifications", methods=["GET", "POST"])
def notifications():
    db = get_db()
    if request.method == "POST":
        title, body = request.form.get("title", "").strip(), request.form.get("body", "").strip()
        level = request.form.get("level", "info")
        if not title or len(title) > 120 or level not in ("info", "success", "warning", "error"):
            flash("Title is required (max 120 characters).", "error")
        else:
            nid = notify(None, title, body[:1000], level, announcement=True, created_by=g.user["id"])
            audit("announcement_created", "notification", nid, title=title)
            flash("Announcement sent to all users.", "success")
        return redirect(url_for("admin.notifications"))
    rows = db.all("SELECT * FROM notifications WHERE is_announcement = 1 ORDER BY id DESC LIMIT 50")
    return render_template("admin/notifications.html", rows=rows)


@bp.post("/notifications/<int:nid>/delete")
def notification_delete(nid):
    get_db().execute("DELETE FROM notifications WHERE id = ? AND is_announcement = 1", (nid,))
    audit("announcement_deleted", "notification", nid)
    flash("Announcement deleted.", "success")
    return redirect(url_for("admin.notifications"))


SETTING_FIELDS = [("site_name", "Site name", "text"), ("language", "Default interface language", "lang"), ("registration_open", "Open registration", "flag"),
                  ("default_questions_per_attempt", "Default questions per attempt", "int"),
                  ("default_time_limit_minutes", "Default time limit (minutes, 0 = none)", "int"),
                  ("default_max_attempts", "Default max attempts (0 = unlimited)", "int"),
                  ("default_show_correct", "Show correct answer after each question (default)", "flag"),
                  ("leaderboard_min_attempts", "Leaderboard: minimum completed attempts", "int"),
                  ("leaderboard_prior_strength", "Leaderboard: reliability weight (higher = stricter)", "int"),
                  ("backup_enabled", "Automatic backups", "flag"), ("backup_interval_hours", "Backup interval (hours)", "int"),
                  ("backup_retention_count", "Keep last N backups", "int"), ("backup_include_pdfs", "Include uploaded PDFs in backups", "flag")]


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    db = get_db()
    if request.method == "POST":
        changed = {}
        for key, label, kind in SETTING_FIELDS:
            if kind == "flag":
                val = "1" if request.form.get(key) else "0"
            elif kind == "int":
                val = str(form_int(key, int(DEFAULT_SETTINGS[key]), 0, 100000))
            elif kind == "lang":
                val = request.form.get(key) if request.form.get(key) in ("uz", "en") else "uz"
            else:
                val = request.form.get(key, "").strip()[:60] or DEFAULT_SETTINGS[key]
            if key in ("backup_interval_hours", "leaderboard_prior_strength") and val == "0":
                val = "1"
            if get_setting(key) != val:
                changed[key] = val
                set_setting(key, val)
        audit("settings_changed", "settings", None, **changed)
        flash("Settings saved.", "success")
        return redirect(url_for("admin.settings"))
    vals = {k: get_setting(k) for k, _, _ in SETTING_FIELDS}
    return render_template("admin/settings.html", fields=SETTING_FIELDS, vals=vals)


@bp.get("/backups")
def backups():
    from flask import current_app
    store, separate = backup_mod.storage_db(current_app.config)
    try:
        rows = store.all("SELECT id, kind, status, size_bytes, sha256, row_counts, verified, error, created_at, finished_at "
                         "FROM backups ORDER BY id DESC LIMIT 50")
    finally:
        store.close()
    return render_template("admin/backups.html", rows=rows, separate=separate, state=backup_mod.STATE)


@bp.post("/backups/run")
def backup_run():
    from flask import current_app
    res = backup_mod.run_backup(current_app._get_current_object(), "manual")
    audit("backup_created" if res["ok"] else "backup_failed", "backup", res.get("id"), error=res.get("error"))
    if res["ok"]:
        flash("Backup completed and restore-verified.", "success")
        notify(g.user["id"], "Backup completed", f"{res['size']} bytes", "success")
    else:
        flash(f"Backup failed: {res['error']}", "error")
    return redirect(url_for("admin.backups"))


@bp.get("/backups/<int:bid>/download")
def backup_download(bid):
    from flask import current_app
    store, _ = backup_mod.storage_db(current_app.config)
    try:
        b = store.one("SELECT id, data, created_at FROM backups WHERE id = ? AND status = 'success'", (bid,))
    finally:
        store.close()
    if not b:
        abort(404)
    audit("backup_downloaded", "backup", bid)
    return Response(b["data"], mimetype="application/gzip",
                    headers={"Content-Disposition": f"attachment; filename=backup-{bid}.json.gz"})


@bp.get("/health")
def health():
    from flask import current_app
    db = get_db()
    t0 = time.time()
    db.val("SELECT 1")
    latency = round((time.time() - t0) * 1000, 1)
    ocr = []
    try:
        import pytesseract
        ocr = pytesseract.get_languages(config="")
    except Exception as e:
        ocr = [f"unavailable ({type(e).__name__})"]
    info = {"Database engine": "PostgreSQL" if db.pg else "SQLite (development only)", "DB latency": f"{latency} ms",
            "Separate backup DB": "yes" if current_app.config["BACKUP_DATABASE_URL"] else "no (backups share the primary DB)",
            "Backup scheduler thread": "running" if backup_mod.STATE["alive"] else "not running in this process",
            "OCR languages": ", ".join(ocr) or "none", "Environment": current_app.config["APP_ENV"],
            "Active sessions": db.val("SELECT COUNT(*) FROM user_sessions WHERE revoked = 0 AND expires_at > ?", (utcnow(),), 0),
            "Stored PDFs": db.val("SELECT COUNT(*) FROM uploaded_documents", (), 0)}
    return render_template("admin/health.html", info=info)
