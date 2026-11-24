import hashlib
import secrets

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from ..audit import audit, login_record, notify
from ..db import IntegrityError, get_db, get_setting, past, utcnow
from ..security import (client_ip, create_session, hash_password, login_required, normalize_phone, rl_blocked, rl_hit,
                        revoke_sessions, safe_next, validate_password, verify_password, USERNAME_RE)

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("main.dashboard"))
    errors, form = {}, request.form
    if get_setting("registration_open") != "1":
        return render_template("register.html", errors={"_": "Registration is currently closed."}, form={}, closed=True)
    if request.method == "POST":
        ip = client_ip()
        if rl_blocked(f"register:{ip}", 10, 3600):
            flash("Too many registration attempts. Try again later.", "error")
            return render_template("register.html", errors={}, form=form), 429
        rl_hit(f"register:{ip}")
        first, last = form.get("first_name", "").strip(), form.get("last_name", "").strip()
        username, phone = form.get("username", "").strip(), normalize_phone(form.get("phone", ""))
        pw, pw2 = form.get("password", ""), form.get("password_confirm", "")
        if not first or len(first) > 60:
            errors["first_name"] = "First name is required (max 60 characters)."
        if not last or len(last) > 60:
            errors["last_name"] = "Last name is required (max 60 characters)."
        if not phone:
            errors["phone"] = "Enter a valid phone number, e.g. +998 90 123 45 67."
        if not USERNAME_RE.match(username):
            errors["username"] = "3-30 characters: letters, digits, underscore or dot."
        pe = validate_password(pw)
        if pe:
            errors["password"] = " ".join(pe)
        elif pw != pw2:
            errors["password_confirm"] = "Passwords do not match."
        db = get_db()
        if "username" not in errors and db.val("SELECT 1 FROM users WHERE username_lower = ?", (username.lower(),)):
            errors["username"] = "This username is already taken."
        if "phone" not in errors and db.val("SELECT 1 FROM users WHERE phone = ?", (phone,)):
            errors["phone"] = "This phone number is already registered."
        if not errors:
            now = utcnow()
            try:
                uid = db.insert(
                    "INSERT INTO users(username,username_lower,first_name,last_name,phone,password_hash,role,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (username, username.lower(), first, last, phone, hash_password(pw), "student", now, now))
            except IntegrityError:
                db.rollback()
                errors["username"] = "This username or phone number is already registered."
                return render_template("register.html", errors=errors, form=form), 400
            user = db.one("SELECT * FROM users WHERE id = ?", (uid,))
            audit("register", "user", uid, actor=user)
            notify(uid, "Welcome!", "Your account is ready. Pick a test and start learning.", "success")
            sid = create_session(uid, True)
            login_record(username, True, "registration", uid, sid)
            flash("Registration successful. Welcome!", "success")
            return redirect(url_for("main.dashboard"))
        flash("Please fix the highlighted fields.", "error")
        return render_template("register.html", errors=errors, form=form), 400
    return render_template("register.html", errors={}, form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    nxt = safe_next(request.values.get("next"))
    if g.user:
        return redirect(nxt or url_for("main.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        ip = client_ip()
        ukey = f"loginfail:user:{username.lower()}"
        ikey = f"loginfail:ip:{ip}"
        if rl_blocked(ukey, 8, 600) or rl_blocked(ikey, 25, 600):
            login_record(username, False, "rate_limited")
            audit("login_rate_limited", "user", username)
            flash("Too many failed attempts. Please wait a few minutes.", "error")
            return render_template("login.html", next=nxt), 429
        db = get_db()
        user = db.one("SELECT * FROM users WHERE username_lower = ?", (username.lower(),))
        if not user or not verify_password(user["password_hash"], password):
            rl_hit(ukey)
            rl_hit(ikey)
            login_record(username, False, "bad_credentials", user["id"] if user else None)
            audit("login_failed", "user", username)
            flash("Invalid username or password.", "error")
            return render_template("login.html", next=nxt), 401
        if user["is_blocked"]:
            login_record(username, False, "blocked", user["id"])
            audit("login_blocked", "user", user["id"], actor=user)
            flash("Your account is blocked. Contact the administrator.", "error")
            return render_template("login.html", next=nxt), 403
        sid = create_session(user["id"], request.form.get("remember") == "1")
        db.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (utcnow(), user["id"]))
        login_record(username, True, "", user["id"], sid)
        audit("login", "user", user["id"], actor=user)
        flash("Login successful.", "success")
        return redirect(nxt or url_for("main.dashboard"))
    return render_template("login.html", next=nxt)


@bp.post("/logout")
def logout():
    if g.user:
        get_db().execute("UPDATE user_sessions SET revoked = 1 WHERE id = ?", (g.sid,))
        audit("logout", "user", g.user["id"])
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))


@bp.get("/forgot")
def forgot():
    return render_template("forgot.html")


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    db = get_db()
    th = hashlib.sha256(token.encode()).hexdigest()
    row = db.one("SELECT * FROM password_resets WHERE token_hash = ?", (th,))
    if not row or row["used_at"] or row["expires_at"] <= utcnow():
        return render_template("reset.html", invalid=True), 400
    if request.method == "POST":
        if rl_blocked(f"reset:{client_ip()}", 10, 3600):
            return render_template("reset.html", invalid=False, errors={"password": "Too many attempts."}), 429
        rl_hit(f"reset:{client_ip()}")
        pw, pw2 = request.form.get("password", ""), request.form.get("password_confirm", "")
        errs = validate_password(pw)
        if not errs and pw != pw2:
            errs = ["Passwords do not match."]
        if errs:
            return render_template("reset.html", invalid=False, errors={"password": " ".join(errs)}), 400
        db.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                   (hash_password(pw), utcnow(), row["user_id"]))
        db.execute("UPDATE password_resets SET used_at = ? WHERE id = ?", (utcnow(), row["id"]))
        revoke_sessions(row["user_id"])
        audit("password_reset_completed", "user", row["user_id"])
        flash("Password updated. You can log in now.", "success")
        return redirect(url_for("auth.login"))
    return render_template("reset.html", invalid=False, errors={})
