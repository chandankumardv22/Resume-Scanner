"""Pluggable auth store: supports both cloud PostgreSQL database and local JSON file fallback."""

from __future__ import annotations

# ==============================================================================
# TECH STACK: [Cryptography & Security] - PBKDF2-HMAC-SHA256 & Session Token Auth
# ==============================================================================
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any

from database import get_db_session, is_database_configured
from logger import logger
from models import User, UserSession

_BACKEND_DIR = Path(__file__).resolve().parent
_DATA_DIR = Path(os.getenv("DATA_DIR", str(_BACKEND_DIR)))
try:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
_USERS_FILE = _DATA_DIR / "users_data.json"
_SESSION_TTL_SEC = 60 * 60 * 24 * 14  # 14 days
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_DURATION_SEC = 15 * 60  # 15 minutes lockout

# In-memory session and lockout fallback (for JSON mode)
_sessions: dict[str, dict[str, Any]] = {}
_failed_logins: dict[str, dict[str, Any]] = {}

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def normalize_email(raw: str) -> str:
    cleaned = (raw or "").strip().lower()
    if not cleaned or not EMAIL_REGEX.match(cleaned):
        raise ValueError("Please enter a valid email address.")
    return cleaned


def normalize_phone(raw: str) -> str:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if digits and (len(digits) != 10 or digits[0] not in "6789"):
        raise ValueError("Enter a valid 10-digit Indian mobile number.")
    return digits


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()
    return salt, digest


def _verify_password(password: str, salt: str, expected: str) -> bool:
    _, digest = _hash_password(password, salt)
    return hmac.compare_digest(digest, expected)


# ==============================================================================
# JSON File Fallback Helpers (Active when DATABASE_URL is not set)
# ==============================================================================
def _load_users() -> dict[str, Any]:
    if not _USERS_FILE.is_file():
        return {"users": {}}
    try:
        data = json.loads(_USERS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("users"), dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"users": {}}


def _save_users(data: dict[str, Any]) -> None:
    _USERS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ==============================================================================
# Core Authentication API Methods (Pluggable: Database vs JSON Fallback)
# ==============================================================================
def register_user(name: str, email: str, password: str, phone: str = "") -> dict[str, Any]:
    clean_name = " ".join((name or "").split())
    if len(clean_name) < 2:
        raise ValueError("Full name must be at least 2 characters.")

    email_n = normalize_email(email)

    if len(password or "") < 8:
        raise ValueError("Password must be at least 8 characters long.")

    phone_clean = ""
    if phone and phone.strip():
        phone_clean = normalize_phone(phone)

    salt, pwd_hash = _hash_password(password)
    created_at = int(time.time())

    if is_database_configured():
        with get_db_session() as session:
            existing = session.query(User).filter_by(email=email_n).first()
            if existing:
                raise ValueError("An account with this email already exists. Please sign in.")
            new_user = User(
                name=clean_name,
                email=email_n,
                phone=phone_clean,
                salt=salt,
                password_hash=pwd_hash,
                created_at=created_at,
            )
            session.add(new_user)
            logger.info(f"[Auth] Registered new user via PostgreSQL: {email_n}")
            return {"name": clean_name, "email": email_n, "phone": phone_clean}

    # Fallback to local JSON store
    data = _load_users()
    if email_n in data["users"]:
        raise ValueError("An account with this email already exists. Please sign in.")

    user = {
        "name": clean_name,
        "email": email_n,
        "phone": phone_clean,
        "salt": salt,
        "password_hash": pwd_hash,
        "created_at": created_at,
    }
    data["users"][email_n] = user
    _save_users(data)
    logger.info(f"[Auth] Registered new user via JSON store: {email_n}")
    return {"name": clean_name, "email": email_n, "phone": phone_clean}


def login_user(email: str, password: str) -> dict[str, Any]:
    email_n = normalize_email(email)
    if not password:
        raise ValueError("Please enter your password.")

    now = time.time()
    lockout_info = _failed_logins.get(email_n)
    if lockout_info and lockout_info.get("locked_until", 0) > now:
        remaining_mins = max(1, int((lockout_info["locked_until"] - now) // 60) + 1)
        raise ValueError(
            f"Account temporarily locked due to repeated failed login attempts. Please try again in {remaining_mins} minutes."
        )

    def _record_failure():
        rec = _failed_logins.get(email_n, {"count": 0, "first_failed": now})
        if now - rec.get("first_failed", now) > _LOCKOUT_DURATION_SEC:
            rec = {"count": 1, "first_failed": now}
        else:
            rec["count"] = rec.get("count", 0) + 1
        if rec["count"] >= _MAX_FAILED_ATTEMPTS:
            rec["locked_until"] = now + _LOCKOUT_DURATION_SEC
        _failed_logins[email_n] = rec

    token = secrets.token_urlsafe(32)
    expires_at = now + _SESSION_TTL_SEC

    if is_database_configured():
        with get_db_session() as session:
            user = session.query(User).filter_by(email=email_n).first()
            if not user or not _verify_password(password, user.salt, user.password_hash):
                _record_failure()
                raise ValueError("Invalid email or password. Please try again.")

            _failed_logins.pop(email_n, None)
            new_session = UserSession(
                token=token,
                email=email_n,
                expires_at=expires_at,
                created_at=now,
            )
            session.add(new_session)
            logger.info(f"[Auth] Successful login via PostgreSQL: {email_n}")
            return {
                "token": token,
                "user": {
                    "name": user.name,
                    "email": email_n,
                    "phone": user.phone or "",
                },
            }

    # Fallback to local JSON store
    data = _load_users()
    user = data["users"].get(email_n)

    if not user or not _verify_password(password, user.get("salt", ""), user.get("password_hash", "")):
        _record_failure()
        raise ValueError("Invalid email or password. Please try again.")

    _failed_logins.pop(email_n, None)
    _sessions[token] = {"email": email_n, "expires_at": expires_at}
    logger.info(f"[Auth] Successful login via JSON store: {email_n}")
    return {
        "token": token,
        "user": {
            "name": user["name"],
            "email": email_n,
            "phone": user.get("phone", ""),
        },
    }


def get_user_by_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None

    now = time.time()

    if is_database_configured():
        with get_db_session() as session:
            user_session = session.query(UserSession).filter_by(token=token).first()
            if not user_session:
                return None
            if user_session.expires_at < now:
                session.delete(user_session)
                return None
            user = session.query(User).filter_by(email=user_session.email).first()
            if not user:
                return None
            return {
                "name": user.name,
                "email": user.email,
                "phone": user.phone or "",
            }

    # Fallback to in-memory / JSON store
    session_data = _sessions.get(token)
    if not session_data:
        return None
    if now > float(session_data["expires_at"]):
        _sessions.pop(token, None)
        return None
    data = _load_users()
    user = data["users"].get(session_data["email"])
    if not user:
        return None
    return {
        "name": user["name"],
        "email": user.get("email", session_data["email"]),
        "phone": user.get("phone", ""),
    }


def logout(token: str | None) -> None:
    if not token:
        return

    if is_database_configured():
        with get_db_session() as session:
            user_session = session.query(UserSession).filter_by(token=token).first()
            if user_session:
                session.delete(user_session)
                logger.info("[Auth] User logged out, session terminated from DB.")
                return

    if token in _sessions:
        _sessions.pop(token, None)
        logger.info("[Auth] User logged out, session terminated from memory.")


def reset_failed_attempts(email: str) -> None:
    """Helper for testing or administrative unlock."""
    try:
        clean = normalize_email(email)
        _failed_logins.pop(clean, None)
    except Exception:
        pass
