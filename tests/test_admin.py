import io
import json
import os
import zipfile

from app import backup
from app import db as dbm
from tests.base import AppTestCase, token


class AdminTests(AppTestCase):
    def test_subject_and_grade_management(self):
        a = self.admin_client()
        t = token(a, "/admin/catalog/subjects")
        a.post("/admin/catalog/subjects", data={"name": "Ancient History", "description": "d", "csrf_token": t})
        a.post("/admin/catalog/grades", data={"name": "12th grade", "sort_order": "12", "csrf_token": t})
        db = self.db()
        sid = db.val("SELECT id FROM subjects WHERE name='Ancient History'")
        self.assertTrue(sid)
        self.assertTrue(db.val("SELECT id FROM grades WHERE name='12th grade'"))
        a.post(f"/admin/catalog/subjects/{sid}/edit", data={"name": "Ancient World", "description": "", "csrf_token": t})
        self.assertEqual(self.db().val("SELECT name FROM subjects WHERE id=?", (sid,)), "Ancient World")
        r = a.post("/admin/catalog/subjects", data={"name": "Ancient World", "csrf_token": t}, follow_redirects=True)
        self.assertIn("already exists", r.get_data(as_text=True))
        a.post(f"/admin/catalog/subjects/{sid}/delete", data={"csrf_token": t})
        self.assertIsNone(self.db().one("SELECT id FROM subjects WHERE id=?", (sid,)))

    def test_subject_with_tests_cannot_be_deleted(self):
        self.make_test(3, 3)
        a = self.admin_client()
        sid = self.db().val("SELECT subject_id FROM test_collections")
        a.post(f"/admin/catalog/subjects/{sid}/delete", data={"csrf_token": token(a, "/admin/catalog/subjects")})
        self.assertIsNotNone(self.db().one("SELECT id FROM subjects WHERE id=?", (sid,)))

    def test_create_edit_toggle_delete_test_with_settings(self):
        a = self.admin_client()
        sid = self.db().val("SELECT id FROM subjects LIMIT 1")
        t = token(a, "/admin/tests")
        r = a.post("/admin/tests/new", data={"title": "Manual test", "subject_id": sid, "questions_per_attempt": "12", "time_limit_minutes": "15",
                                              "max_attempts": "3", "randomize_questions": "1", "show_correct": "1", "is_enabled": "1",
                                              "publish_at": "2030-01-01T10:00", "expires_at": "2031-01-01T10:00", "csrf_token": t})
        self.assertEqual(r.status_code, 302)
        row = self.db().one("SELECT * FROM test_collections")
        self.assertEqual((row["questions_per_attempt"], row["time_limit_minutes"], row["max_attempts"], row["randomize_options"]), (12, 15, 3, 0))
        self.assertEqual(row["publish_at"], "2030-01-01 05:00:00")     # site time zone UTC+5 -> UTC
        tid = row["id"]
        a.post(f"/admin/tests/{tid}/edit", data={"title": "Renamed", "subject_id": sid, "max_attempts": "0", "csrf_token": t})
        self.assertEqual(self.db().val("SELECT title FROM test_collections WHERE id=?", (tid,)), "Renamed")
        a.post(f"/admin/tests/{tid}/toggle", data={"csrf_token": t})
        self.assertEqual(self.db().val("SELECT is_enabled FROM test_collections WHERE id=?", (tid,)), 1)  # edit unchecked -> 0, toggled back -> 1
        a.post(f"/admin/tests/{tid}/delete", data={"csrf_token": t})
        self.assertIsNone(self.db().one("SELECT id FROM test_collections WHERE id=?", (tid,)))
        actions = {r["action"] for r in self.db().all("SELECT action FROM audit_logs")}
        self.assertTrue({"test_created", "test_updated", "test_deleted"} <= actions)

    def test_block_unblock_delete_user_and_session_kill(self):
        uid = self.make_user("target")
        c = self.logged_in("target")
        self.assertEqual(c.get("/dashboard").status_code, 200)
        a = self.admin_client()
        t = token(a, "/admin/users")
        a.post(f"/admin/users/{uid}/block", data={"csrf_token": t})
        self.assertEqual(c.get("/dashboard").status_code, 302)           # live session killed
        self.assertEqual(self.login(self.client_for(), "target", "Passw0rd1").status_code, 403)
        a.post(f"/admin/users/{uid}/block", data={"csrf_token": t})
        self.assertEqual(self.login(self.client_for(), "target", "Passw0rd1").status_code, 302)
        a.post(f"/admin/users/{uid}/delete", data={"csrf_token": t})
        self.assertIsNone(self.db().one("SELECT id FROM users WHERE id=?", (uid,)))

    def test_user_search_and_filters(self):
        self.make_user("findme_x"); self.make_user("someone_else")
        a = self.admin_client()
        html = a.get("/admin/users?q=findme").get_data(as_text=True)
        self.assertIn("findme_x", html)
        self.assertNotIn("someone_else", html)

    def test_audit_log_and_login_history(self):
        self.make_user("audited")
        self.login(self.client_for(), "audited", "bad-password1")
        self.login(self.client_for(), "audited", "Passw0rd1")
        a = self.admin_client()
        html = a.get("/admin/audit").get_data(as_text=True)
        self.assertIn("login_failed", html)
        self.assertIn("login", html)
        html = a.get("/admin/audit?action=login_failed").get_data(as_text=True)
        self.assertNotIn(">logout<", html)
        html = a.get("/admin/logins?ok=0").get_data(as_text=True)
        self.assertIn("bad_credentials", html)
        row = self.db().one("SELECT * FROM audit_logs WHERE action='login' ORDER BY id DESC LIMIT 1")
        self.assertTrue(row["ip"] is not None and row["created_at"])
        # no route lets anyone edit or delete audit rows
        rules = [str(r) for r in self.app.url_map.iter_rules()]
        self.assertFalse([r for r in rules if "audit" in r and r != "/admin/audit"])

    def test_notifications_and_announcements(self):
        c = self.logged_in("noter")
        a = self.admin_client()
        a.post("/admin/notifications", data={"title": "Exam week", "body": "Good luck", "level": "warning", "csrf_token": token(a, "/admin/notifications")})
        html = c.get("/notifications").get_data(as_text=True)
        self.assertIn("Exam week", html)
        self.assertIn("badge-dot", c.get("/dashboard").get_data(as_text=True))
        r = self.api(c, "/api/notifications/read", {})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("badge-dot", c.get("/dashboard").get_data(as_text=True))
        # per-user read state: other user still has it unread
        c2 = self.logged_in("noter2")
        self.assertIn("badge-dot", c2.get("/dashboard").get_data(as_text=True))

    def test_settings_change_is_audited_and_used(self):
        a = self.admin_client()
        data = {"site_name": "Tarix Quiz", "language": "en", "registration_open": "", "default_questions_per_attempt": "7", "csrf_token": token(a, "/admin/settings")}
        a.post("/admin/settings", data=data)
        self.assertIn("Tarix Quiz", self.client_for().get("/").get_data(as_text=True))
        self.assertIn("closed", self.client_for().get("/register").get_data(as_text=True))
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM audit_logs WHERE action='settings_changed'"), 1)

    def test_backup_run_verified_and_restorable(self):
        tid = self.make_test(6, 3)
        s = self.logged_in("backed")
        a = self.admin_client()
        r = a.post("/admin/backups/run", data={"csrf_token": token(a, "/admin/backups")})
        row = self.db().one("SELECT * FROM backups ORDER BY id DESC LIMIT 1")
        self.assertEqual((row["status"], row["verified"]), ("success", 1))
        counts = json.loads(row["row_counts"])
        self.assertEqual(counts["questions"], 6)
        self.assertGreaterEqual(counts["users"], 2)
        blob = a.get(f"/admin/backups/{row['id']}/download").data
        self.assertEqual(blob[:2], b"\x1f\x8b")
        # restore into a brand-new empty database and compare
        fresh = dbm.Db("sqlite:///" + os.path.join(self.tmp, "restored.db"))
        dbm.migrate(fresh)
        for t in ("settings", "grades", "subjects"):
            fresh.execute(f"DELETE FROM {t}")
        restored = backup.restore_into(fresh, blob)
        fresh.commit()
        self.assertEqual(restored, counts)
        self.assertEqual(fresh.val("SELECT COUNT(*) FROM answer_options"), 24)
        self.assertEqual(fresh.val("SELECT username FROM users WHERE username='backed'"), "backed")

    def test_backup_failure_is_recorded_and_notified(self):
        orig = backup.dump
        backup.dump = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk full"))
        try:
            res = backup.run_backup(self.app, "manual")
        finally:
            backup.dump = orig
        self.assertFalse(res["ok"])
        row = self.db().one("SELECT * FROM backups ORDER BY id DESC LIMIT 1")
        self.assertEqual(row["status"], "failed")
        self.assertIn("disk full", row["error"])
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM notifications WHERE title='Backup failed'"), 1)

    def test_backup_retention_and_due_logic(self):
        db = self.db()
        dbm.set_setting("backup_retention_count", "2", db); db.commit()
        for _ in range(4):
            self.assertTrue(backup.run_backup(self.app, "manual")["ok"])
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM backups WHERE status='success'"), 2)
        self.assertFalse(backup.due(self.app))                      # just ran
        d = self.db(); d.execute("UPDATE backups SET created_at='2000-01-01 00:00:00'"); d.commit()
        self.assertTrue(backup.due(self.app))

    def test_separate_backup_database(self):
        self.app.config["BACKUP_DATABASE_URL"] = "sqlite:///" + os.path.join(self.tmp, "offsite.db")
        self.assertTrue(backup.run_backup(self.app, "manual")["ok"])
        off = dbm.Db(self.app.config["BACKUP_DATABASE_URL"])
        self.assertEqual(off.val("SELECT COUNT(*) FROM backups WHERE status='success'"), 1)
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM backups"), 0)

    def test_exports_xlsx_and_pdf(self):
        tid = self.make_test(3, 3)
        c = self.logged_in("exported")
        r = c.post(f"/tests/{tid}/start", data={"csrf_token": token(c, "/tests")})
        aid = int(r.headers["Location"].rsplit("/", 1)[1])
        c.post(f"/api/attempts/{aid}/finish", json={}, headers={"X-CSRF-Token": token(c, "/profile")})
        a = self.admin_client()
        x = a.get("/admin/export.xlsx")
        self.assertEqual(x.status_code, 200)
        z = zipfile.ZipFile(io.BytesIO(x.data))
        self.assertIn("xl/workbook.xml", z.namelist())
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(x.data)).active
        self.assertEqual(ws.max_row, 2)
        self.assertEqual(ws["A2"].value, "exported")
        p = a.get("/admin/export.pdf")
        self.assertEqual(p.data[:5], b"%PDF-")
        self.assertIn("exported", a.get("/admin/results").get_data(as_text=True))

    def test_delete_attempt_returns_attempt_to_student(self):
        tid = self.make_test(3, 3, max_attempts=1)
        c = self.logged_in("reset_me")
        aid = int(c.post(f"/tests/{tid}/start", data={"csrf_token": token(c, "/tests")}).headers["Location"].rsplit("/", 1)[1])
        c.post(f"/api/attempts/{aid}/finish", json={}, headers={"X-CSRF-Token": token(c, "/profile")})
        a = self.admin_client()
        a.post(f"/admin/attempts/{aid}/delete", data={"csrf_token": token(a, "/admin/attempts")})
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM quiz_attempts"), 0)
        self.assertEqual(c.post(f"/tests/{tid}/start", data={"csrf_token": token(c, "/tests")}).status_code, 302)
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM quiz_attempts"), 1)

    def test_pages_render_for_each_role(self):
        self.make_test(5, 5)
        a = self.admin_client()
        for p in ["/admin/", "/admin/users", "/admin/catalog/subjects", "/admin/catalog/grades", "/admin/tests", "/admin/tests/new", "/admin/pdf",
                  "/admin/attempts", "/admin/results", "/admin/leaderboard", "/admin/audit", "/admin/logins", "/admin/notifications",
                  "/admin/settings", "/admin/backups", "/admin/health", "/profile", "/notifications"]:
            self.assertEqual(a.get(p).status_code, 200, p)
        tid = self.db().val("SELECT id FROM test_collections")
        self.assertEqual(a.get(f"/admin/tests/{tid}/questions").status_code, 200)
        self.assertEqual(a.get(f"/admin/tests/{tid}/edit").status_code, 200)
        t = self.logged_in("tt", "teacher", perms=json.dumps({"view_students": 1, "view_results": 1, "view_analytics": 1, "export": 1}))
        for p in ["/teacher/", "/teacher/students", "/teacher/results", "/teacher/analytics", "/leaderboard", "/profile"]:
            self.assertEqual(t.get(p).status_code, 200, p)
        s = self.logged_in("ss")
        for p in ["/dashboard", "/tests", f"/tests/{tid}", "/history", "/leaderboard", "/profile", "/notifications"]:
            self.assertEqual(s.get(p).status_code, 200, p)

    def test_teacher_analytics_frequently_missed(self):
        tid = self.make_test(2, 2)
        db = self.db()
        q = db.val("SELECT id FROM questions LIMIT 1")
        wrong = db.val("SELECT id FROM answer_options WHERE question_id=? AND is_correct=0 LIMIT 1", (q,))
        for i in range(4):
            u = self.make_user(f"miss{i}")
            aid = db.insert("INSERT INTO quiz_attempts(user_id,test_id,attempt_no,status,started_at) VALUES (?,?,?,?,?)", (u, tid, 1, "completed", "2026-01-01 00:00:00"))
            db.execute("INSERT INTO attempt_questions(attempt_id,question_id,position,option_order) VALUES (?,?,?,?)", (aid, q, 1, "[]"))
            db.execute("INSERT INTO student_answers(attempt_id,question_id,option_id,is_correct,answered_at) VALUES (?,?,?,?,?)", (aid, q, wrong, 0, "2026-01-01 00:00:00"))
            db.commit()
        t = self.logged_in("tt2", "teacher", perms=json.dumps({"view_analytics": 1}))
        self.assertIn("100%", t.get("/teacher/analytics").get_data(as_text=True))
