"""Run one backup now (usable as a Railway cron job):  python -m scripts.backup"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RUN_SCHEDULER", "0")
from app import backup, create_app  # noqa: E402

app = create_app()
res = backup.run_backup(app, "cron")
print(res)
sys.exit(0 if res.get("ok") else 1)
