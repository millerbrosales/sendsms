from datetime import datetime, timezone
from .db import Base, engine, SessionLocal
from .models import ScheduledMessage
from .messaging import send_sms

def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    processed = 0
    try:
        now = datetime.now(timezone.utc)
        due = (
            db.query(ScheduledMessage)
            .filter(
                ScheduledMessage.status == "scheduled",
                ScheduledMessage.scheduled_for <= now,
            )
            .order_by(ScheduledMessage.scheduled_for.asc())
            .limit(250)
            .all()
        )

        for item in due:
            try:
                response = send_sms(item.customer.phone_e164, item.body)
                item.twilio_sid = response.sid
                item.status = response.status or "accepted"
                item.sent_at = datetime.now(timezone.utc)
                item.error = None
            except Exception as exc:
                # Keep failed API attempts visible. They are NOT automatically retried,
                # avoiding accidental duplicate sends until you deliberately implement retries.
                item.status = "failed"
                item.error = str(exc)[:1000]
            processed += 1

        db.commit()
        print(f"Processed {processed} due message(s).")
    finally:
        db.close()

if __name__ == "__main__":
    run()
