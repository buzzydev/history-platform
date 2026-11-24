from tests.base import AppTestCase, token


class AuthTests(AppTestCase):
    def reg(self, c, **over):
        d = dict(first_name="Ali", last_name="Valiyev", phone="+998 90 111 22 33", username="ali_v", password="Secret123",
                 password_confirm="Secret123")
        d.update(over)
        d["csrf_token"] = token(c, "/register")
        return c.post("/register", data=d)

    def test_registration_creates_student_and_logs_in(self):
        c = self.client_for()
        r = self.reg(c)
        self.assertEqual(r.status_code, 302)
        row = self.db().one("SELECT * FROM users WHERE username='ali_v'")
        self.assertEqual(row["role"], "student")
        self.assertNotEqual(row["password_hash"], "Secret123")
        self.assertTrue(row["password_hash"].startswith("scrypt:"))
        self.assertEqual(row["phone"], "+998901112233")
        self.assertEqual(c.get("/dashboard").status_code, 200)

    def test_registration_cannot_choose_role(self):
        c = self.client_for()
        self.reg(c, role="admin", username="sneaky", phone="+998901234500")
        self.assertEqual(self.db().val("SELECT role FROM users WHERE username='sneaky'"), "student")

    def test_duplicate_username_and_phone(self):
        self.reg(self.client_for())
        r = self.reg(self.client_for(), phone="+998907776655", username="ALI_V")
        self.assertEqual(r.status_code, 400)
        self.assertIn("already taken", r.get_data(as_text=True))
        r = self.reg(self.client_for(), username="other_one")
        self.assertIn("already registered", r.get_data(as_text=True))

    def test_validation(self):
        c = self.client_for()
        self.assertEqual(self.reg(c, password="short", password_confirm="short").status_code, 400)
        self.assertEqual(self.reg(c, password_confirm="Different1").status_code, 400)
        self.assertEqual(self.reg(c, phone="abc").status_code, 400)
        self.assertEqual(self.reg(c, username="a b").status_code, 400)
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM users WHERE role='student'"), 0)

    def test_login_logout_and_session_revocation(self):
        self.make_user("sam")
        c = self.client_for()
        self.assertEqual(self.login(c, "sam", "wrongpass1").status_code, 401)
        r = self.login(c, "sam", "Passw0rd1")
        self.assertEqual(r.status_code, 302)
        cookie = c.get_cookie("session")
        self.assertEqual(c.get("/dashboard").status_code, 200)
        r = c.post("/logout", data={"csrf_token": token(c, "/profile")})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(c.get("/dashboard").status_code, 302)
        # replaying the old session cookie must fail (server-side revocation)
        c2 = self.client_for()
        c2.set_cookie("session", cookie.value)
        self.assertEqual(c2.get("/dashboard").status_code, 302)
        self.assertGreaterEqual(self.db().val("SELECT COUNT(*) FROM login_history WHERE success=0"), 1)

    def test_session_expiration(self):
        c = self.logged_in("exp")
        db = self.db()
        db.execute("UPDATE user_sessions SET expires_at = '2000-01-01 00:00:00'"); db.commit()
        self.assertEqual(c.get("/dashboard").status_code, 302)

    def test_unauthorized_access_redirects_or_401(self):
        c = self.client_for()
        self.assertEqual(c.get("/dashboard").status_code, 302)
        self.assertEqual(c.get("/api/attempts/1/state").status_code, 401)
        self.assertEqual(c.get("/admin/users").status_code, 302)

    def test_csrf_required(self):
        self.make_user("csrfuser")
        c = self.client_for()
        r = c.post("/login", data={"username": "csrfuser", "password": "Passw0rd1"})
        self.assertEqual(r.status_code, 400)

    def test_rate_limiting_of_login(self):
        self.make_user("victim")
        c = self.client_for()
        for _ in range(8):
            self.login(c, "victim", "nope12345")
        r = self.login(c, "victim", "Passw0rd1")
        self.assertEqual(r.status_code, 429)

    def test_blocked_user_cannot_login(self):
        self.make_user("blocked1")
        db = self.db(); db.execute("UPDATE users SET is_blocked=1 WHERE username='blocked1'"); db.commit()
        self.assertEqual(self.login(self.client_for(), "blocked1", "Passw0rd1").status_code, 403)

    def test_open_redirect_blocked(self):
        self.make_user("redir")
        c = self.client_for()
        t = token(c)
        r = c.post("/login", data={"username": "redir", "password": "Passw0rd1", "csrf_token": t, "next": "//evil.com"})
        self.assertNotIn("evil.com", r.headers["Location"])

    def test_password_change_requires_current_password(self):
        c = self.logged_in("pwuser")
        t = token(c, "/profile")
        r = c.post("/profile", data={"action": "password", "current_password": "bad", "new_password": "Newpass123",
                                     "new_password_confirm": "Newpass123", "csrf_token": t})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.login(self.client_for(), "pwuser", "Newpass123").status_code, 401)
        r = c.post("/profile", data={"action": "password", "current_password": "Passw0rd1", "new_password": "Newpass123",
                                     "new_password_confirm": "Newpass123", "csrf_token": t})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.login(self.client_for(), "pwuser", "Newpass123").status_code, 302)

    def test_admin_reset_link_flow(self):
        uid = self.make_user("forgetful")
        a = self.admin_client()
        r = a.post(f"/admin/users/{uid}/reset-link", data={"csrf_token": token(a, "/admin/users")})
        html = r.get_data(as_text=True)
        import re
        link = re.search(r'/reset/([\w\-]+)', html).group(1)
        c = self.client_for()
        self.assertEqual(c.get(f"/reset/{link}").status_code, 200)
        r = c.post(f"/reset/{link}", data={"password": "Brandnew123", "password_confirm": "Brandnew123", "csrf_token": token(c, f"/reset/{link}")})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.login(self.client_for(), "forgetful", "Brandnew123").status_code, 302)
        self.assertEqual(self.client_for().get(f"/reset/{link}").status_code, 400)  # single use

    def test_admin_bootstrap_from_env_only(self):
        self.assertEqual(self.db().val("SELECT role FROM users WHERE username='boss'"), "admin")
        import os, re
        with open(os.path.join(os.path.dirname(__file__), "..", "app", "__init__.py")) as fh:
            src = fh.read()
        self.assertNotIn("BossPass", src)
