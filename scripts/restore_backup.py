"""Restore a backup archive (backup-N.json.gz) into an EMPTY database.

Usage:  DATABASE_URL=postgresql://... python -m scripts.restore_backup backup-12.json.gz
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import backup, db  # noqa: E402
from app.config import load_config  # noqa: E402


def main(path):
    url = load_config()["DATABASE_URL"]
    target = db.Db(url)
    db.migrate(target)
    if target.val("SELECT COUNT(*) FROM users", (), 0):
        sys.exit("Refusing to restore: the target database already contains users. Use an empty database.")
    target.execute("DELETE FROM settings")          # drop defaults seeded by the app
    for t in ("grades", "subjects"):
        target.execute(f"DELETE FROM {t}")
    with open(path, "rb") as fh:
        counts = backup.restore_into(target, fh.read())
    target.commit()
    print("Restored rows:", counts)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
