import os
import subprocess
import sys

from app import backup
from app import db as dbm
from tests.base import AppTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(args, env):
    e = {**os.environ, **env}
    return subprocess.run([sys.executable, "-m"] + args, cwd=ROOT, env=e, capture_output=True, text=True, timeout=120)


class ScriptTests(AppTestCase):
    def test_production_requires_secret_key(self):
        env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
        env.update(APP_ENV="production", DATABASE_URL="sqlite:///" + os.path.join(self.tmp, "p.db"), RUN_SCHEDULER="0")
        r = subprocess.run([sys.executable, "-c", "from app import create_app; create_app()"], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SECRET_KEY", r.stderr)
        env["SECRET_KEY"] = "x" * 40
        r = subprocess.run([sys.executable, "-c", "from app import create_app; a=create_app(); print(a.config['SESSION_COOKIE_SECURE'])"], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("True", r.stdout)

    def test_create_admin_script(self):
        url = "sqlite:///" + os.path.join(self.tmp, "a.db")
        r = run(["scripts.create_admin", "--username", "chief", "--phone", "+998905550000"], {"DATABASE_URL": url, "ADMIN_PASSWORD": "Chief12345", "ADMIN_USERNAME": ""})
        self.assertEqual(r.returncode, 0, r.stderr)
        d = dbm.Db(url)
        self.assertEqual(d.val("SELECT role FROM users WHERE username='chief'"), "admin")
        r = run(["scripts.create_admin", "--username", "weak", "--phone", "+998905550001"], {"DATABASE_URL": url, "ADMIN_PASSWORD": "short", "ADMIN_USERNAME": ""})
        self.assertNotEqual(r.returncode, 0)

    def test_backup_and_restore_scripts_roundtrip(self):
        self.make_test(4, 2)
        self.make_user("roundtrip")
        src_url = self.app.config["DATABASE_URL"]
        r = run(["scripts.backup"], {"DATABASE_URL": src_url, "RUN_SCHEDULER": "0"})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        d = dbm.Db(src_url)
        blob = d.val("SELECT data FROM backups WHERE status='success' ORDER BY id DESC LIMIT 1")
        path = os.path.join(self.tmp, "b.json.gz")
        with open(path, "wb") as fh:
            fh.write(bytes(blob))
        new_url = "sqlite:///" + os.path.join(self.tmp, "fresh.db")
        r = run(["scripts.restore_backup", path], {"DATABASE_URL": new_url})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        f = dbm.Db(new_url)
        self.assertEqual(f.val("SELECT username FROM users WHERE username='roundtrip'"), "roundtrip")
        self.assertEqual(f.val("SELECT COUNT(*) FROM questions"), 4)
        r = run(["scripts.restore_backup", path], {"DATABASE_URL": new_url})
        self.assertNotEqual(r.returncode, 0)          # refuses non-empty target
