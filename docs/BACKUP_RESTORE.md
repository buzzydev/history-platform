# Backup and recovery

**What is backed up:** users, grades, subjects, tests, questions, options, attempts, answers, exposure history, notifications, audit/login history, settings and (optionally) the uploaded PDFs. Format: gzip-compressed portable JSON (`backup-N.json.gz`).

**How it runs:** a scheduler thread inside the app (one gunicorn worker) checks every 5 minutes and creates a backup when the last one is older than `backup_interval_hours` (default 24). Admin → Backups shows history and lets you run or download backups. You may also run `python -m scripts.backup` from a Railway cron service.

**Verification:** after each dump the archive is restored into a scratch in-memory database and row counts are compared. Only then is the backup marked *verified*. A failed backup is recorded with its error and all admins get a notification.

**Separate storage:** set `BACKUP_DATABASE_URL` to a second PostgreSQL database (e.g. another Railway project). Without it backups share the primary database and do **not** protect you from losing that database - download copies from the Backups page regularly.

**Retention:** the newest `backup_retention_count` (default 14) successful backups are kept.

## Restore procedure
1. Create an **empty** PostgreSQL database and set `DATABASE_URL` to it.
2. Download the backup file from Admin → Backups (or read it from the backup database).
3. `python -m scripts.restore_backup backup-12.json.gz` (runs migrations, refuses non-empty databases, restores all rows, fixes sequences).
4. Start the app with the same `SECRET_KEY` (sessions of users are restored but will be re-created on login).
5. Log in and check Admin → Health and a few tests.
