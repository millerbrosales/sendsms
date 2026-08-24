import os
from datetime import datetime, timezone
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError

from .db import Base, engine, SessionLocal
from .models import Customer, ScheduledMessage, InboundMessage
from .security import is_logged_in, password_ok, SESSION_SECRET
from .csv_import import read_csv_bytes, normalize_phone, parse_date
from .messaging import schedule_times, render_templates

app = FastAPI(title="Miller Bros SMS")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, https_only=False)
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

def require_login(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=303)
    return None

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, password: str = Form(...)):
    if not password_ok(password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Incorrect password."}, status_code=401)
    request.session["logged_in"] = True
    return RedirectResponse("/", status_code=303)

@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect
    db = SessionLocal()
    try:
        customers = db.query(Customer).order_by(Customer.created_at.desc()).limit(50).all()
        counts = {
            "customers": db.query(func.count(Customer.id)).scalar() or 0,
            "scheduled": db.query(func.count(ScheduledMessage.id)).filter(ScheduledMessage.status == "scheduled").scalar() or 0,
            "sent": db.query(func.count(ScheduledMessage.id)).filter(ScheduledMessage.status.in_(["accepted","queued","sending","sent","delivered"])).scalar() or 0,
            "failed": db.query(func.count(ScheduledMessage.id)).filter(ScheduledMessage.status.in_(["failed","undelivered"])).scalar() or 0,
            "replies": db.query(func.count(InboundMessage.id)).scalar() or 0,
        }
        replies = db.query(InboundMessage).order_by(InboundMessage.received_at.desc()).limit(20).all()
        return templates.TemplateResponse("dashboard.html", {
            "request": request, "customers": customers, "counts": counts, "replies": replies
        })
    finally:
        db.close()

@app.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse("upload.html", {"request": request, "result": None})

@app.post("/upload", response_class=HTMLResponse)
async def upload_csv(request: Request, file: UploadFile = File(...)):
    redirect = require_login(request)
    if redirect:
        return redirect

    data = await file.read()
    headers, mapping, rows = read_csv_bytes(data)

    required = ["customer_name", "phone"]
    missing = [x for x in required if x not in mapping]
    if missing:
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "result": {
                "error": f"Could not find required column(s): {', '.join(missing)}",
                "headers": headers,
                "mapping": mapping
            }
        }, status_code=400)

    db = SessionLocal()
    added = duplicates = invalid = 0
    scheduled_count = 0
    notes = []

    try:
        for i, row in enumerate(rows, start=2):
            name = (row.get(mapping["customer_name"]) or "").strip()
            phone = normalize_phone(row.get(mapping["phone"]) or "", os.getenv("DEFAULT_COUNTRY", "US"))
            rep = (row.get(mapping.get("rep_name", "")) or "").strip() if mapping.get("rep_name") else ""
            install_date = parse_date(row.get(mapping.get("install_date", "")) or "") if mapping.get("install_date") else None
            order_id = (row.get(mapping.get("order_id", "")) or "").strip() if mapping.get("order_id") else ""

            if not name or not phone:
                invalid += 1
                notes.append(f"Row {i}: skipped because name/phone was invalid.")
                continue

            # Prefer stable order ID. If none exists, use phone + install date as a conservative import key.
            dedupe_key = order_id or f"{phone}:{install_date.isoformat() if install_date else 'nodate'}"

            existing = db.query(Customer).filter(
                or_(Customer.order_id == dedupe_key,
                    (Customer.phone_e164 == phone) & (Customer.install_date == install_date))
            ).first()
            if existing:
                duplicates += 1
                continue

            customer = Customer(
                order_id=dedupe_key,
                customer_name=name,
                phone_e164=phone,
                rep_name=rep,
                install_date=install_date
            )
            db.add(customer)
            db.flush()

            templates_map = render_templates(name, rep, install_date)
            times = schedule_times(install_date)

            for msg_type, send_at in times.items():
                # If a reminder/followup date is already past, do not send it.
                if send_at <= datetime.now(timezone.utc) and msg_type != "welcome":
                    continue
                db.add(ScheduledMessage(
                    customer_id=customer.id,
                    message_type=msg_type,
                    body=templates_map[msg_type],
                    scheduled_for=send_at,
                    status="scheduled"
                ))
                scheduled_count += 1

            added += 1

        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    finally:
        db.close()

    result = {
        "filename": file.filename,
        "rows": len(rows),
        "added": added,
        "duplicates": duplicates,
        "invalid": invalid,
        "scheduled": scheduled_count,
        "mapping": mapping,
        "headers": headers,
        "notes": notes[:20],
    }
    return templates.TemplateResponse("upload.html", {"request": request, "result": result})

@app.post("/twilio/inbound")
async def twilio_inbound(request: Request):
    form = await request.form()
    sid = str(form.get("MessageSid") or "")
    from_number = str(form.get("From") or "")
    to_number = str(form.get("To") or "")
    body = str(form.get("Body") or "")

    if sid:
        db = SessionLocal()
        try:
            exists = db.query(InboundMessage).filter(InboundMessage.twilio_sid == sid).first()
            if not exists:
                db.add(InboundMessage(
                    twilio_sid=sid,
                    from_number=from_number,
                    to_number=to_number,
                    body=body,
                ))
                db.commit()
        finally:
            db.close()

    # Empty TwiML response = receive/store the SMS without auto-replying.
    return PlainTextResponse('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml")

@app.post("/twilio/status")
async def twilio_status(request: Request):
    form = await request.form()
    sid = str(form.get("MessageSid") or "")
    status = str(form.get("MessageStatus") or "")
    error_code = str(form.get("ErrorCode") or "")
    db = SessionLocal()
    try:
        msg = db.query(ScheduledMessage).filter(ScheduledMessage.twilio_sid == sid).first()
        if msg:
            msg.status = status or msg.status
            if error_code:
                msg.error = f"Twilio error {error_code}"
            db.commit()
    finally:
        db.close()
    return PlainTextResponse("ok")
