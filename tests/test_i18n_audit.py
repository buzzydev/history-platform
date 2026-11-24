import json
import re

from app import db as dbm
from app import i18n
from tests.base import AppTestCase, token


class UzbekAndAuditTests(AppTestCase):
    def uz(self, client):
        client.set_cookie("lang", "uz")
        return client

    def test_pages_translate_to_uzbek_and_english_unchanged(self):
        c = self.client_for()
        en = c.get("/login").get_data(as_text=True)
        self.assertIn("Log in", en)
        self.assertIn('lang="en"', en)
        self.uz(c)
        uz = c.get("/login").get_data(as_text=True)
        self.assertIn("Kirish", uz)
        self.assertIn("Parol", uz)
        self.assertIn('lang="uz"', uz)
        self.assertNotIn(">Log in<", uz)

    def test_language_switch_route_and_site_default(self):
        c = self.client_for()
        r = c.get("/lang/uz?next=/login")
        self.assertEqual(r.status_code, 302)
        self.assertIn("Kirish", c.get("/login").get_data(as_text=True))
        c.get("/lang/en")
        self.assertIn("Log in", c.get("/login").get_data(as_text=True))
        self.assertEqual(c.get("/lang/xx").status_code, 404)
        # site-wide default without cookie
        d = self.db(); dbm.set_setting("language", "uz", d); d.commit()
        self.assertIn("Kirish", self.client_for().get("/login").get_data(as_text=True))

    def test_navbar_dashboard_flash_and_errors_in_uzbek(self):
        c = self.logged_in("uzuser")
        self.uz(c)
        html = c.get("/dashboard").get_data(as_text=True)
        self.assertIn("Chiqish", html)           # Sign Out
        self.assertIn("Profil", html)
        self.assertIn("Salom, ", html)
        self.assertIn("Yakunlangan testlar", html)
        r = c.get("/api/attempts/999/state")
        self.assertIn("Urinish topilmadi", r.get_json()["error"])
        # validation flash goes through the translated toast payload
        v = self.client_for(); self.uz(v)
        t = token(v, "/register")
        r = v.post("/register", data={"first_name": "A", "last_name": "B", "phone": "x", "username": "ab", "password": "p", "password_confirm": "p", "csrf_token": t})
        body = r.get_data(as_text=True)
        self.assertIn("Belgilangan maydonlarni to", body)
        self.assertIn("Kamida 8 belgi", body) if "Kamida 8 belgi" in body else self.assertIn("kamida 8 belgi", body.lower())

    def test_bell_menu_lists_notifications(self):
        c = self.logged_in("belluser")
        a = self.admin_client()
        a.post("/admin/notifications", data={"title": "Imtihon haftasi", "body": "Omad!", "level": "info", "csrf_token": token(a, "/admin/notifications")})
        menu = re.search(r'id="notif-menu">(.*?)</div>\s*</div>\s*<div class="dropdown">', c.get("/dashboard").get_data(as_text=True), re.S).group(1)
        self.assertIn("Imtihon haftasi", menu)
        self.assertIn("unread", menu)

    def test_every_js_key_exists_and_patterns_are_safe(self):
        for k in i18n.JS_KEYS:
            self.assertIn(k, i18n.UZ, k)
        self.assertEqual(i18n.tr("Totally unknown sentence"), "Totally unknown sentence")
        self.assertEqual(i18n.tr("<b>"), "<b>")
        self.assertTrue(all(v.strip() for v in i18n.UZ.values()))

    def test_user_content_is_not_executed_after_translation(self):
        db = self.db(); uid = self.make_user("xss2")
        db.execute("UPDATE users SET first_name=? WHERE id=?", ("<img src=x onerror=alert(1)>", uid)); db.commit()
        c = self.logged_in("xss2"); self.uz(c)
        html = c.get("/dashboard").get_data(as_text=True)
        self.assertNotIn("<img src=x", html)

    def test_audit_log_is_append_only_in_database(self):
        db = self.db()
        db.execute("INSERT INTO audit_logs(action,created_at) VALUES ('t','2026-01-01 00:00:00')"); db.commit()
        with self.assertRaises(dbm.IntegrityError):
            db.execute("UPDATE audit_logs SET action='x'")
        db.rollback()
        with self.assertRaises(dbm.IntegrityError):
            db.execute("DELETE FROM audit_logs")
        db.rollback()
        self.assertEqual(db.val("SELECT COUNT(*) FROM audit_logs WHERE action='t'"), 1)

    def test_deleting_user_keeps_their_audit_trail(self):
        uid = self.make_user("gone")
        self.login(self.client_for(), "gone", "Passw0rd1")
        a = self.admin_client()
        a.post(f"/admin/users/{uid}/delete", data={"csrf_token": token(a, "/admin/users")})
        self.assertGreaterEqual(self.db().val("SELECT COUNT(*) FROM audit_logs WHERE actor_username='gone'"), 1)
