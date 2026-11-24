"""Create (or promote) an administrator.  The password is read from the environment or a prompt - never from code.

  ADMIN_PASSWORD='...' python -m scripts.create_admin --username boss --phone +998901234567
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RUN_SCHEDULER", "0")
from app import create_app, db as dbm  # noqa: E402
from app.security import USERNAME_RE, hash_password, normalize_phone, validate_password  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--username", required=True)
ap.add_argument("--phone", required=True)
ap.add_argument("--first", default="Site")
ap.add_argument("--last", default="Admin")
a = ap.parse_args()
pw = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
if not USERNAME_RE.match(a.username) or not normalize_phone(a.phone) or validate_password(pw):
    sys.exit("Invalid username / phone / weak password (min 8 chars, letters + digits).")
app = create_app()
with app.app_context():
    db = dbm.get_db()
    now = dbm.utcnow()
    row = db.one("SELECT id FROM users WHERE username_lower = ?", (a.username.lower(),))
    if row:
        db.execute("UPDATE users SET role='admin', password_hash=?, is_blocked=0, updated_at=? WHERE id=?", (hash_password(pw), now, row["id"]))
        print("Existing user promoted to admin and password reset.")
    else:
        db.insert("INSERT INTO users(username,username_lower,first_name,last_name,phone,password_hash,role,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                  (a.username, a.username.lower(), a.first, a.last, normalize_phone(a.phone), hash_password(pw), "admin", now, now))
        print("Administrator created.")
