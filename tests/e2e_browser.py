"""Real-browser (Chromium via Playwright) checks. Run:  python -m tests.e2e_browser
Needs: pip install playwright && playwright install chromium"""
import logging
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["ADMIN_USERNAME"] = "boss"
os.environ["ADMIN_PASSWORD"] = "BossPass123"
os.environ["ADMIN_PHONE"] = "+998901000001"

from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from app import create_app, db as dbm  # noqa: E402
from app.security import hash_password  # noqa: E402

SHOTS = os.environ.get("SHOTS_DIR", "")
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


def seed(app):
    with app.app_context():
        db = dbm.open_db()
        now = dbm.utcnow()
        db.insert("INSERT INTO users(username,username_lower,first_name,last_name,phone,password_hash,role,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                  ("student1", "student1", "Dilnoza", "Karimova", "+998901112233", hash_password("Student123"), "student", now, now))
        sid = db.val("SELECT id FROM subjects LIMIT 1")
        tid = db.insert("INSERT INTO test_collections(title,subject_id,questions_per_attempt,status,created_at,updated_at,time_limit_minutes) VALUES (?,?,?,?,?,?,?)",
                        ("Amir Temur davri", sid, 5, "published", now, now, 10))
        for i in range(8):
            q = db.insert("INSERT INTO questions(test_id,text,explanation,position,status,content_hash,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                          (tid, f"Savol {i}: Amir Temur qachon tug'ilgan?", "Tushuntirish matni", i, "approved", f"h{i}", now, now))
            for j in range(4):
                db.execute("INSERT INTO answer_options(question_id,text,is_correct,position) VALUES (?,?,?,?)", (q, f"Variant {j}", 1 if j == 0 else 0, j))
        dbm.set_setting("language", "en", db)
        db.commit(); db.close()


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def login(page, base, user, pw):
    page.goto(base + "/login")
    page.fill("#f-username", user)
    page.fill("#f-password", pw)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def main():
    tmp = tempfile.mkdtemp()
    app = create_app({"DATABASE_URL": "sqlite:///" + os.path.join(tmp, "e2e.db"), "TESTING": True, "RUN_SCHEDULER": False, "SESSION_COOKIE_SECURE": False})
    seed(app)
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    srv = make_server("127.0.0.1", 5099, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:5099"
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        errors = []
        ctx = b.new_context(viewport={"width": 390, "height": 800}, color_scheme="light")
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        # --- theme ---
        page.goto(base + "/")
        check("system light preference applied on first visit", page.evaluate("document.documentElement.dataset.theme") == "light")
        bg_light = page.evaluate("getComputedStyle(document.body).backgroundColor")
        page.click("[data-theme-toggle]")
        page.wait_for_timeout(450)
        check("toggle switches to dark", page.evaluate("document.documentElement.dataset.theme") == "dark")
        bg_dark = page.evaluate("getComputedStyle(document.body).backgroundColor")
        check("dark background differs", bg_light != bg_dark, f"{bg_light} / {bg_dark}")
        page.reload()
        check("theme persisted after reload", page.evaluate("document.documentElement.dataset.theme") == "dark")
        ctx2 = b.new_context(viewport={"width": 390, "height": 800}, color_scheme="dark")
        p2 = ctx2.new_page(); p2.goto(base + "/")
        check("system dark preference respected on first visit", p2.evaluate("document.documentElement.dataset.theme") == "dark")
        ctx2.close()
        if SHOTS: page.screenshot(path=f"{SHOTS}/home-dark-390.png")
        page.click("[data-theme-toggle]")

        # --- registration via UI, validation display, password toggle ---
        page.goto(base + "/register")
        page.fill("#f-first_name", "Ali"); page.fill("#f-last_name", "Valiyev"); page.fill("#f-phone", "+998 93 555 44 33")
        page.fill("#f-username", "ali_ui"); page.fill("#f-password", "weak"); page.fill("#f-password_confirm", "weak")
        page.click("[data-pw-toggle] >> nth=0")
        check("password visibility toggle", page.get_attribute("#f-password", "type") == "text")
        page.click("button[type=submit]"); page.wait_for_load_state("networkidle")
        check("weak password shows inline error", "at least 8" in page.content())
        page.fill("#f-password", "Strong123"); page.fill("#f-password_confirm", "Strong123")
        page.click("button[type=submit]"); page.wait_for_load_state("networkidle")
        check("registered and landed on dashboard", page.url.endswith("/dashboard"))
        check("welcome toast shown", page.locator(".toast").count() >= 1)

        # --- navbar dropdown ---
        check("navbar shows username", "ali_ui" in page.inner_text(".user-btn"))
        check("dropdown hidden initially", not page.is_visible(".dropdown-menu >> nth=1"))
        page.click(".user-btn")
        page.wait_for_timeout(300)
        check("dropdown opens", page.is_visible("text=Sign Out"))
        page.click("h1")
        page.wait_for_timeout(300)
        check("dropdown closes on outside click", not page.is_visible("text=Sign Out"))
        page.click(".user-btn"); page.click("text=Sign Out"); page.wait_for_load_state("networkidle")
        check("sign out returns to home as guest", page.is_visible("text=Log in"))

        # --- responsive overflow on every width ---
        for w in (320, 360, 375, 390, 414, 768, 1024, 1440):
            ctxw = b.new_context(viewport={"width": w, "height": 900}); pw = ctxw.new_page()
            bad = []
            for path in ("/", "/login", "/register"):
                pw.goto(base + path)
                if overflow(pw) > 0: bad.append(path)
            login(pw, base, "student1", "Student123")
            for path in ("/dashboard", "/tests", "/history", "/leaderboard", "/profile", "/notifications", "/tests/1"):
                pw.goto(base + path)
                if overflow(pw) > 0: bad.append(path)
            ctxw.close()
            check(f"no horizontal overflow @ {w}px (public + student pages)", not bad, str(bad))
        ctxa = b.new_context(viewport={"width": 320, "height": 900}); pa = ctxa.new_page()
        login(pa, base, "boss", "BossPass123")
        bad = []
        for path in ("/admin/", "/admin/users", "/admin/tests", "/admin/pdf", "/admin/audit", "/admin/logins", "/admin/settings", "/admin/backups", "/admin/health", "/admin/tests/1/questions", "/admin/catalog/subjects", "/admin/tests/new"):
            pa.goto(base + path); pa.wait_for_load_state("networkidle")
            if overflow(pa) > 0: bad.append(path)
        check("no horizontal overflow @ 320px (admin pages)", not bad, str(bad))
        if SHOTS:
            pa.goto(base + "/admin/users"); pa.screenshot(path=f"{SHOTS}/admin-users-320.png")

        # --- quiz in the browser ---
        ctxs = b.new_context(viewport={"width": 390, "height": 844}); ps = ctxs.new_page()
        ps.on("pageerror", lambda e: errors.append(str(e)))
        login(ps, base, "student1", "Student123")
        ps.goto(base + "/tests/1"); ps.click("text=Start test"); ps.wait_for_selector(".q-text")
        check("quiz renders 5 question buttons", ps.locator(".qnav button").count() == 5)
        check("timer visible", ps.is_visible("#timer"))
        src = ps.content()
        check("correct answer not present in page source", "is_correct" not in src)
        first_q = ps.inner_text(".q-text")
        ps.click(".option:not(:has-text('Variant 0')) >> nth=0")
        ps.wait_for_selector(".option.correct")
        check("wrong pick highlighted red and correct highlighted green", ps.locator(".option.wrong").count() == 1 and ps.locator(".option.correct").count() == 1)
        check("explanation shown", ps.is_visible(".explain"))
        if SHOTS: ps.screenshot(path=f"{SHOTS}/quiz-answered-390.png")
        ps.reload(); ps.wait_for_selector(".q-text")
        check("refresh restores progress (1 answered)", "1 answered" in ps.inner_text(".quiz-top"))
        for _ in range(14):
            if ps.locator(".option:not([disabled])").count():
                ps.click(".option:has-text('Variant 0')"); ps.wait_for_selector(".option.correct")
            elif ps.locator("text=Submit and see results").count():
                break
            elif ps.locator("text=Next →").count():
                ps.click("text=Next →"); ps.wait_for_timeout(100)
            else:
                break
        ps.click("text=Submit and see results"); ps.wait_for_url("**/attempts/*")
        check("result page shows score", ps.is_visible(".score-ring"))
        if SHOTS: ps.screenshot(path=f"{SHOTS}/result-390.png")

        # --- admin confirm modal & toast, review editor ---
        pa.set_viewport_size({"width": 390, "height": 844})
        pa.goto(base + "/admin/users")
        pa.click('form[action$="/delete"] button >> nth=0')
        check("custom confirm modal appears for delete", pa.is_visible(".modal"))
        pa.click(".modal .btn >> text=Cancel")
        check("modal closes on cancel and nothing deleted", not pa.is_visible(".modal"))
        pa.goto(base + "/admin/tests/1/questions"); pa.wait_for_selector(".rq")
        check("review editor lists questions", pa.locator(".rq").count() == 8)
        pa.click("text=+ Add question")
        pa.fill(".rq >> nth=-1 >> textarea >> nth=0", "Yangi savol?")
        pa.click("text=Approve all questions")
        pa.wait_for_selector(".toast")
        check("incomplete question blocked with toast", "incomplete" in pa.inner_text("#toasts") or "Question #" in pa.inner_text("#toasts"))
        if SHOTS: pa.screenshot(path=f"{SHOTS}/review-390.png")
        # --- Uzbek interface (cookie) ---
        ctxu = b.new_context(viewport={"width": 390, "height": 844}); pu = ctxu.new_page()
        pu.goto(base + "/lang/uz"); login(pu, base, "student1", "Student123")
        pu.goto(base + "/tests/1"); pu.wait_for_load_state("networkidle")
        pu.click("text=Urinishni davom ettirish") if pu.locator("text=Urinishni davom ettirish").count() else pu.click("text=Testni boshlash")
        pu.wait_for_selector(".q-text")
        check("quiz UI strings are Uzbek", "savol" in pu.inner_text(".quiz-top") and pu.locator("text=Keyingi →").count() == 1)
        pu.click(".option >> nth=0"); pu.wait_for_selector(".option.correct")
        check("feedback text Uzbek", pu.locator("text=/To'g'ri!|Noto'g'ri\\./").count() >= 1)
        pu.goto(base + "/dashboard"); pu.click("button[aria-label='Bildirishnomalar']"); pu.wait_for_timeout(300)
        check("bell dropdown lists notifications", pu.locator("#notif-menu .note").count() >= 1 and pu.is_visible("#notif-menu"))
        check("no JavaScript console errors", not errors, "; ".join(errors[:3]))
        b.close()
    srv.shutdown()
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} browser checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
