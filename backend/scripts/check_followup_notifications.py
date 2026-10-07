"""
Manual / cron trigger for the follow-up sweep. You normally don't need this:
the worker container (`python -m app.worker`) runs the same sweep once a day.
Use it only if you run without a worker:

    0 8 * * * /path/to/venv/bin/python /path/to/backend/scripts/check_followup_notifications.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.services.notification_service import sweep_followups


def main():
    db = SessionLocal()
    try:
        result = sweep_followups(db)
        print(f"Checked {result['checked']} follow-up(s); sent {result['notifications_sent']} notification(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
