import os
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo
from twilio.rest import Client

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "America/Chicago")
WELCOME_DELAY_MINUTES = int(os.getenv("WELCOME_DELAY_MINUTES", "1"))
REMINDER_DAYS_BEFORE = int(os.getenv("REMINDER_DAYS_BEFORE", "2"))
FOLLOWUP_DAYS_AFTER = int(os.getenv("FOLLOWUP_DAYS_AFTER", "1"))
MESSAGE_HOUR_LOCAL = int(os.getenv("MESSAGE_HOUR_LOCAL", "10"))

def local_to_utc(d, hour=MESSAGE_HOUR_LOCAL):
    tz = ZoneInfo(APP_TIMEZONE)
    local_dt = datetime.combine(d, time(hour=hour), tzinfo=tz)
    return local_dt.astimezone(timezone.utc)

def schedule_times(install_date):
    now = datetime.now(timezone.utc)
    times = {"welcome": now + timedelta(minutes=WELCOME_DELAY_MINUTES)}
    if install_date:
        times["reminder"] = local_to_utc(install_date - timedelta(days=REMINDER_DAYS_BEFORE))
        times["followup"] = local_to_utc(install_date + timedelta(days=FOLLOWUP_DAYS_AFTER))
    return times

def render_templates(customer_name, rep_name, install_date):
    first = (customer_name or "there").split()[0]
    rep = rep_name or "your rep"
    date_text = install_date.strftime("%a, %b %-d") if install_date else "your scheduled date"

    # Keep these concise. Edit them to match your approved A2P campaign language.
return {
    "welcome": (
        f"Hi {first}, this is {rep} with Socket Fiber. Happy to get you signed up for a "
        f"free install + free month! Feel free to reach out with questions. STOP to opt out."
    ),
    "reminder": (
        f"Hi {first}! Your Socket Fiber install is a couple days away on {date_text}. "
        f"We'll see you soon! Reply here if you have any questions."
    ),
    "followup": (
        f"Hi {first}! Checking in after your install. Did it go well? "
        f"If we missed you, send a day next week + time that works best to reschedule."
    ),
}
def send_sms(to_number: str, body: str):
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    service_sid = os.environ["TWILIO_MESSAGING_SERVICE_SID"]
    client = Client(account_sid, auth_token)
    msg = client.messages.create(
    to=to_number,
    from_="+15736854720",
    body=body,
    messaging_service_sid=service_sid,
)
    return msg
