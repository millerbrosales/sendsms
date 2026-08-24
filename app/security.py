import os
import secrets
from fastapi import Request

APP_PASSWORD = os.getenv("APP_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret-change-me")

def is_logged_in(request: Request) -> bool:
    return bool(request.session.get("logged_in"))

def password_ok(value: str) -> bool:
    return bool(APP_PASSWORD) and secrets.compare_digest(value, APP_PASSWORD)
