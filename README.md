# History Quiz Platform

Online history testing platform: students register, take randomised multiple-choice tests (any grade, any subject) and see results; admins import questions from PDF (with review before publishing), manage users/teachers/tests and monitor everything; teachers follow student performance.

* UI language: **Uzbek (default)** and English. Switch with the links in the page footer (cookie) or set the site default in Admin → Settings. Translation lives in `app/i18n.py` (exact-match dictionary + patterns; unknown strings simply stay English). Uzbek/Cyrillic **question content** is fully supported.
* Production target: **Railway** (Docker + PostgreSQL). Everything is stored in the database - including uploaded PDFs and backups - because Railway's filesystem is ephemeral.

## Architecture
```
app/
  __init__.py      app factory, error handlers, admin bootstrap from env
  config.py        environment configuration (no secrets in code)
  db.py            tiny DB layer: PostgreSQL in production, SQLite for dev/tests; migrations runner
  security.py      password hashing (scrypt), CSRF, DB-backed rate limiting, server-side sessions, decorators, security headers
  quiz.py          randomisation + exposure history, grading, leaderboard
  pdfimport.py     PDF text extraction + OCR + question/answer parser
  backup.py        logical backups, restore verification, scheduler
  i18n.py          Uzbek translation layer
  exports.py       Excel / PDF reports
  routes/          auth, main (student), api (quiz JSON), teacher, admin
migrations/        SQL migrations (001_init.sql)
templates/         Jinja templates (no inline CSS/JS)
static/css|js|images   theme.css (all colours), base.css, ES-module JavaScript
tests/             unittest suite + Playwright browser tests
scripts/           create_admin, backup, restore_backup
```
Stack: Python 3.12, Flask, PostgreSQL (psycopg 3), pdfplumber + pypdfium2 + Tesseract OCR, openpyxl, reportlab, gunicorn, vanilla JS (ES modules).
*(The brief preferred Next.js/Prisma; the build environment had no network access to install those packages, so a Flask stack that could actually be run and tested here was chosen.)*

### Key design points
* **Roles** `student` (default), `teacher` (per-teacher permissions set by admin), `admin`. Role is checked on the server for every admin/teacher endpoint; registration ignores any role field.
* **Sessions** are server-side rows (`user_sessions`): logout, block, password change/reset and role change revoke them immediately; idle/absolute expiry enforced.
* **Quiz engine**: per-attempt random sample + shuffled options saved in `attempt_questions`; `question_exposure` stores which questions each student already received per cycle, unseen questions are preferred, a new shuffled cycle starts only when the pool is exhausted; start is serialised per user (`SELECT ... FOR UPDATE` on PostgreSQL) with unique constraints as a second guard. Correct answers never leave the server before they are allowed by the test settings.
* **PDF import**: text layer via pdfplumber, OCR fallback per page; handles `A)`/`A.`/`a)`, Cyrillic `А Б В Г`, `1. 2. 3. 4.` options, inline options, `Javob:`/`Answer:` lines, `*A)` markers and answer-key tables. Uncertain answers are flagged *needs review*; nothing is published without admin approval; original PDF stored in DB.
* **Leaderboard**: reliability-weighted average `(C·m + Σ%)/(C + n)` with configurable minimum attempts (default 3) and weight `C` (default 5).

## Local installation
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
sudo apt install tesseract-ocr tesseract-ocr-uzb tesseract-ocr-uzb-cyrl tesseract-ocr-rus   # for scanned PDFs
export ADMIN_USERNAME=admin ADMIN_PASSWORD='ChangeMe123' ADMIN_PHONE=+998901234567
flask --app wsgi run            # SQLite file in instance/dev.db when DATABASE_URL is empty
```
Create/promote an admin later: `ADMIN_PASSWORD=... python -m scripts.create_admin --username boss --phone +998901234567`.

## Environment variables
See `.env.example`. Required in production: `APP_ENV=production`, `SECRET_KEY`, `DATABASE_URL`, and `ADMIN_USERNAME`/`ADMIN_PASSWORD`/`ADMIN_PHONE` for the first start.

## Database setup
Migrations in `migrations/` are applied automatically at startup (tracked in `schema_migrations`). Default grades 6-11 and the subjects *World History* and *Uzbekistan History* are seeded when the tables are empty.

## Tests
```bash
python -m unittest discover -s tests -t . -v      # API/integration/permission/PDF/quiz/backup tests (SQLite)
pip install -r requirements-dev.txt && playwright install chromium
python -m tests.e2e_browser                        # real-browser UI checks
```
Latest recorded results: `docs/TEST_RESULTS.md`.

## Deployment
See `docs/DEPLOYMENT.md` (English) and `docs/RAILWAY_DEPLOY_UZ.md` (oddiy o'zbekcha, qadam-baqadam). Backups: `docs/BACKUP_RESTORE.md`. API: `docs/API.md`.

## Known limitations
See the end of `docs/DEPLOYMENT.md`.
