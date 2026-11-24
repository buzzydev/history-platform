import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["ADMIN_USERNAME"] = "boss"
os.environ["ADMIN_PASSWORD"] = "BossPass123"
os.environ["ADMIN_PHONE"] = "+998901000001"

from app import create_app  # noqa: E402
from app import db as dbm  # noqa: E402
from app.security import hash_password  # noqa: E402

CSRF_RE = re.compile(r'name="csrf-token" content="([^"]+)"')


def token(client, path="/login"):
    html = client.get(path).get_data(as_text=True)
    m = CSRF_RE.search(html)
    return m.group(1) if m else ""


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        url = "sqlite:///" + os.path.join(self.tmp, "t.db")
        pg = os.environ.get("TEST_DATABASE_URL")
        if pg:  # run the whole suite against PostgreSQL (wipes the target database!)
            if os.environ.get("CONFIRM_WIPE_TEST_DB") != "yes":
                raise RuntimeError("Set CONFIRM_WIPE_TEST_DB=yes: the test run DROPS ALL TABLES in TEST_DATABASE_URL.")
            d = dbm.Db(pg)
            d.execute("DROP SCHEMA public CASCADE")
            d.execute("CREATE SCHEMA public")
            d.commit(); d.close()
            url = pg
        self.app = create_app({"DATABASE_URL": url, "TESTING": True,
                               "RUN_SCHEDULER": False, "SESSION_COOKIE_SECURE": False,
                               "OCR_LANGS": "eng"})
        _d = dbm.open_db(url); dbm.set_setting("language", "en", _d); _d.commit(); _d.close()
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- helpers ---
    def db(self):
        return dbm.open_db(self.app.config["DATABASE_URL"])

    def client_for(self):
        return self.app.test_client()

    def login(self, client, username, password):
        t = token(client, "/login")
        return client.post("/login", data={"username": username, "password": password, "csrf_token": t})

    def post(self, client, path, data=None, page=None, **kw):
        t = token(client, page or "/profile" if client.get("/profile").status_code == 200 else "/login")
        d = dict(data or {})
        d["csrf_token"] = t
        return client.post(path, data=d, **kw)

    def api(self, client, path, body):
        t = token(client, "/profile")
        return client.post(path, json=body, headers={"X-CSRF-Token": t})

    def make_user(self, username, role="student", password="Passw0rd1", phone=None, perms="{}"):
        db = self.db()
        now = dbm.utcnow()
        uid = db.insert("INSERT INTO users(username,username_lower,first_name,last_name,phone,password_hash,role,teacher_perms,created_at,updated_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (username, username.lower(), "F" + username, "L" + username,
                         phone or "+99890%07d" % (abs(hash(username)) % 10 ** 7), hash_password(password), role, perms, now, now))
        db.commit(); db.close()
        return uid

    def logged_in(self, username, role="student", password="Passw0rd1", **kw):
        if not self.db().val("SELECT 1 FROM users WHERE username_lower = ?", (username.lower(),)):
            self.make_user(username, role, password, **kw)
        c = self.client_for()
        r = self.login(c, username, password)
        assert r.status_code == 302, r.status_code
        return c

    def admin_client(self):
        c = self.client_for()
        r = self.login(c, "boss", "BossPass123")
        assert r.status_code == 302
        return c

    def make_test(self, n_questions=30, per_attempt=10, publish=True, **over):
        db = self.db()
        now = dbm.utcnow()
        sid = db.val("SELECT id FROM subjects ORDER BY id LIMIT 1")
        tid = db.insert("INSERT INTO test_collections(title,subject_id,questions_per_attempt,status,created_at,updated_at,"
                        "time_limit_minutes,max_attempts,show_correct,randomize_questions,randomize_options) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (over.get("title", "Sample test"), sid, per_attempt, "published" if publish else "draft", now, now,
                         over.get("time_limit_minutes", 0), over.get("max_attempts", 0), over.get("show_correct", 1),
                         over.get("randomize_questions", 1), over.get("randomize_options", 1)))
        for i in range(n_questions):
            qid = db.insert("INSERT INTO questions(test_id,text,position,status,content_hash,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                            (tid, f"Question {i}?", i, "approved", f"h{tid}-{i}", now, now))
            for j in range(4):
                db.execute("INSERT INTO answer_options(question_id,text,is_correct,position) VALUES (?,?,?,?)",
                           (qid, f"Q{i} option {j}", 1 if j == 0 else 0, j))
        db.commit(); db.close()
        return tid
