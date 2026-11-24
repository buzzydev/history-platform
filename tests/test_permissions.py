import json

from tests.base import AppTestCase, token


class PermissionTests(AppTestCase):
    def test_student_cannot_access_admin_or_teacher(self):
        c = self.logged_in("stud")
        for path in ("/admin/", "/admin/users", "/admin/settings", "/admin/audit", "/admin/backups", "/teacher/", "/admin/export.xlsx"):
            self.assertEqual(c.get(path).status_code, 403, path)

    def test_student_cannot_appoint_teacher_or_self_promote(self):
        c = self.logged_in("stud2")
        uid = self.db().val("SELECT id FROM users WHERE username='stud2'")
        r = c.post(f"/admin/users/{uid}/edit", data={"role": "admin", "first_name": "a", "last_name": "b", "phone": "+998901119999",
                                                       "csrf_token": token(c, "/profile")})
        self.assertEqual(r.status_code, 403)
        c.post("/profile", data={"action": "info", "first_name": "x", "last_name": "y", "phone": "+998901118888", "role": "admin",
                                 "csrf_token": token(c, "/profile")})
        self.assertEqual(self.db().val("SELECT role FROM users WHERE id=?", (uid,)), "student")

    def test_teacher_limits(self):
        perms = json.dumps({"view_students": 1, "view_results": 1})
        t = self.logged_in("teach", "teacher", perms=perms)
        self.assertEqual(t.get("/teacher/").status_code, 200)
        self.assertEqual(t.get("/teacher/students").status_code, 200)
        self.assertEqual(t.get("/teacher/analytics").status_code, 403)       # permission not granted
        self.assertEqual(t.get("/teacher/export.xlsx").status_code, 403)
        for path in ("/admin/", "/admin/settings", "/admin/users", "/admin/audit", "/admin/logins"):
            self.assertEqual(t.get(path).status_code, 403, path)
        boss = self.db().val("SELECT id FROM users WHERE username='boss'")
        r = t.post(f"/admin/users/{boss}/edit", data={"role": "student", "first_name": "a", "last_name": "b", "phone": "+998901119998",
                                                         "csrf_token": token(t, "/profile")})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.db().val("SELECT role FROM users WHERE id=?", (boss,)), "admin")

    def test_teacher_with_export_permission_can_export(self):
        t = self.logged_in("teach2", "teacher", perms=json.dumps({"export": 1, "view_results": 1}))
        r = t.get("/teacher/export.xlsx")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data[:2], b"PK")

    def test_admin_can_appoint_and_remove_teacher(self):
        uid = self.make_user("future_teacher")
        a = self.admin_client()
        t = token(a, "/admin/users")
        r = a.post(f"/admin/users/{uid}/edit", data={"role": "teacher", "first_name": "F", "last_name": "T", "phone": "+998901112000",
                                                      "perm_view_students": "1", "csrf_token": t})
        self.assertEqual(r.status_code, 302)
        row = self.db().one("SELECT * FROM users WHERE id=?", (uid,))
        self.assertEqual(row["role"], "teacher")
        self.assertEqual(json.loads(row["teacher_perms"]), {"view_students": 1})
        a.post(f"/admin/users/{uid}/edit", data={"role": "student", "first_name": "F", "last_name": "T", "phone": "+998901112000", "csrf_token": t})
        self.assertEqual(self.db().val("SELECT role FROM users WHERE id=?", (uid,)), "student")
        actions = [r["action"] for r in self.db().all("SELECT action FROM audit_logs")]
        self.assertIn("teacher_appointed", actions)
        self.assertIn("teacher_removed", actions)

    def test_admin_cannot_demote_self_or_last_admin(self):
        a = self.admin_client()
        boss = self.db().val("SELECT id FROM users WHERE username='boss'")
        r = a.post(f"/admin/users/{boss}/edit", data={"role": "student", "first_name": "a", "last_name": "b", "phone": "+998901000001",
                                                        "csrf_token": token(a, "/admin/users")})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.db().val("SELECT role FROM users WHERE id=?", (boss,)), "admin")
        a.post(f"/admin/users/{boss}/delete", data={"csrf_token": token(a, "/admin/users")})
        self.assertIsNotNone(self.db().one("SELECT id FROM users WHERE id=?", (boss,)))

    def test_students_cannot_view_other_students_results(self):
        self.make_test(5, 3)
        a = self.logged_in("alice")
        b = self.logged_in("bob")
        tid = self.db().val("SELECT id FROM test_collections")
        r = a.post(f"/tests/{tid}/start", data={"csrf_token": token(a, "/tests")})
        aid = int(r.headers["Location"].rsplit("/", 1)[1])
        self.assertEqual(a.get(f"/api/attempts/{aid}/state").status_code, 200)
        self.assertEqual(b.get(f"/api/attempts/{aid}/state").status_code, 404)
        self.assertEqual(b.get(f"/attempts/{aid}").status_code, 404)
        r = self.api(b, f"/api/attempts/{aid}/answer", {"question_id": 1, "option_id": 1})
        self.assertEqual(r.status_code, 404)

    def test_leaderboard_hides_private_data(self):
        c = self.logged_in("viewer")
        html = c.get("/leaderboard").get_data(as_text=True)
        self.assertNotIn("+998", html)
