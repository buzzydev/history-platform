# Deployment (Railway)

1. Push this folder to a GitHub repository (the ZIP contents = repository root).
2. Railway → **New Project → Deploy from GitHub repo**. Railway detects `railway.json` and builds the `Dockerfile` (installs Tesseract + Uzbek language packs).
3. Add a **PostgreSQL** service to the project. In the web service → *Variables* add:
   * `APP_ENV` = `production`
   * `SECRET_KEY` = long random string (`python -c "import secrets;print(secrets.token_urlsafe(48))"`)
   * `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (reference variable)
   * `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_PHONE` (first administrator; created once on first start)
   * optional but recommended: `BACKUP_DATABASE_URL` pointing to a *different* PostgreSQL database
4. Deploy. Health check: `/healthz`. Open the generated domain, log in as the admin, change the password in Profile.
5. Admin → Settings: review defaults. Admin → Backups: press **Run backup now** and confirm it shows *verified*.
6. Do **not** scale to more than 1 replica/worker without disabling the in-process scheduler (`RUN_SCHEDULER=0`) on the extra ones.

Migrations run automatically at boot. HTTPS, secure cookies, HSTS and a strict CSP are enabled when `APP_ENV=production`.

## Verify PostgreSQL before go-live (one command)
Create a **new empty** PostgreSQL database (e.g. a second Railway Postgres, never production) and run the same 82 tests on it:
```bash
pip install -r requirements.txt
TEST_DATABASE_URL='postgresql://...' sh scripts/pg_selftest.sh
```
It drops all tables in that database first. Then run `python -m tests.e2e_browser` is SQLite-based; for the live Railway site just register, import a PDF, take a test and press *Run backup now*.

## Known limitations / honest notes
* **PostgreSQL path not exercised in the build environment** (no PostgreSQL server or psycopg available offline). All tests ran on SQLite through the same SQL layer; the SQL was written to be portable (placeholders converted, `RETURNING id`, `SERIAL`/`BYTEA` DDL). Run the test-suite once against a PostgreSQL URL before go-live (`DATABASE_URL=... python -m unittest discover -s tests -t .` works because tests create their own SQLite files - to test PostgreSQL, start the app against an empty Railway database and click through Admin → Health, register, import a PDF, take a test, run a backup).
* The Docker image and gunicorn start command were written but **not built/run** here (no Docker, gunicorn not installed offline). The app itself was run with the Werkzeug server and Chromium.
* Password reset needs no e-mail/SMS provider: an administrator creates a one-time link (valid 1 hour) and hands it to the user. Self-service e-mail/SMS reset requires integrating a provider.
* OCR quality depends on scan quality; only English OCR could be tested here (Uzbek language packs are installed by the Dockerfile but untested). Always review extracted questions.
* Audit logs are append-only: no edit/delete routes and a database trigger rejects UPDATE/DELETE (tested on SQLite; the PostgreSQL trigger in `migrations/002_audit_append_only.pg.sql` is untested - if it fails at boot it is skipped with a warning and the site still starts). A superuser can still drop the trigger.
* Uzbek translation is dictionary based: audit action names (e.g. `login_failed`), setting keys in logs and any text added later stay English until added to `app/i18n.py`. Text was reviewed by the author only, not by a native-speaker proofreader.
* The "password list" layout requirement (single-row entries, Add Password button above the list) does not apply: the platform has no password-record feature, and passwords are only stored as scrypt hashes.
* Backups stored in the primary database do not survive loss of that database; configure `BACKUP_DATABASE_URL` and download copies.
