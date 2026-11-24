import glob
import os
import re
import subprocess
import unittest

from tests.base import AppTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _r(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as fh:
        return fh.read()


class StaticUiTests(AppTestCase):
    def test_both_themes_defined_with_required_primary_colours(self):
        css = read("static/css/theme.css").lower()
        self.assertIn("#bdb08e", css)
        self.assertIn("#2e104a", css)
        self.assertIn(':root[data-theme="dark"]', css)

    def test_no_hardcoded_colours_outside_theme_file(self):
        hexre = re.compile(r"#[0-9a-fA-F]{3,8}\b")
        for f in glob.glob(os.path.join(ROOT, "static/css/*.css")):
            if f.endswith("theme.css"):
                continue
            body = re.sub(r"/\*.*?\*/", "", _r(f), flags=re.S)
            self.assertFalse(hexre.findall(body), f)
            self.assertNotRegex(body, r"rgba?\(")

    def test_no_inline_css_or_js_in_templates(self):
        for f in glob.glob(os.path.join(ROOT, "templates/**/*.html"), recursive=True):
            t = _r(f)
            self.assertNotRegex(t, r'\sstyle="', f)
            self.assertNotRegex(t, r"<style", f)
            for m in re.finditer(r"<script(?![^>]*\ssrc=)[^>]*>", t):
                self.fail(f"inline script in {f}")
            self.assertNotRegex(t, r"\son(click|change|submit|load)=", f)

    def test_static_structure(self):
        for p in ("static/css/theme.css", "static/css/base.css", "static/js/main.js", "static/js/quiz.js", "static/js/review.js", "static/js/theme-init.js"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, p)), p)
        self.assertTrue(os.path.isdir(os.path.join(ROOT, "static/images")))

    def test_js_files_parse(self):
        for f in glob.glob(os.path.join(ROOT, "static/js/*.js")):
            r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f + r.stderr)

    def test_no_alert_calls(self):
        for f in glob.glob(os.path.join(ROOT, "static/js/*.js")):
            self.assertNotRegex(_r(f), r"\balert\(|\bconfirm\(")

    def test_navbar_shows_username_and_dropdown(self):
        c = self.logged_in("navuser")
        html = c.get("/dashboard").get_data(as_text=True)
        nav = html.split("</header>")[0]
        self.assertIn("navuser", nav)
        self.assertIn("data-theme-toggle", nav)
        self.assertIn("Sign Out", nav)
        # "Profile" appears only inside the dropdown menu, not as a direct navbar link
        self.assertEqual(nav.count("Profile"), 1)
        self.assertLess(nav.index("dropdown-menu"), nav.index("Profile"))
        self.assertNotIn("Add Password", nav)

    def test_theme_init_runs_before_stylesheets_and_viewport_present(self):
        html = self.client_for().get("/").get_data(as_text=True)
        self.assertLess(html.index("theme-init.js"), html.index("theme.css"))
        self.assertIn("width=device-width", html)

    def test_security_headers(self):
        r = self.client_for().get("/")
        self.assertIn("script-src 'self'", r.headers["Content-Security-Policy"])
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")

    def test_xss_is_escaped(self):
        db = self.db()
        uid = self.make_user("xss")
        db.execute("UPDATE users SET first_name=? WHERE id=?", ("<script>alert(1)</script>", uid)); db.commit()
        c = self.logged_in("xss")
        html = c.get("/dashboard").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_sql_injection_attempts_are_harmless(self):
        self.make_user("realuser")
        a = self.admin_client()
        r = a.get("/admin/users?q=' OR 1=1 --")
        self.assertEqual(r.status_code, 200)
        r = self.login(self.client_for(), "realuser' OR '1'='1", "x")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.db().val("SELECT COUNT(*) FROM users"), 2)


if __name__ == "__main__":
    unittest.main()
