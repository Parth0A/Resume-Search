"""Local SQLite authentication for the Resume Search prototype.

Passwords are salted and hashed with PBKDF2; plaintext passwords are never stored.
For public production deployment, configure persistent storage and review the auth design.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("RESUME_SEARCH_DB", str(Path(__file__).with_name("resume_search.db"))))
_ITERATIONS = 310_000


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_auth_db() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('Recruiter', 'Job seeker')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if len(normalized) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
        raise ValueError("Enter a valid email address.")
    return normalized


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS).hex()


def register_user(email: str, password: str, role: str) -> None:
    normalized_email = _normalize_email(email)
    if len(password) < 8:
        raise ValueError("Use a password with at least 8 characters.")
    if role not in {"Recruiter", "Job seeker"}:
        raise ValueError("Choose a valid account type.")

    salt = secrets.token_bytes(16)
    password_hash = _hash_password(password, salt)
    try:
        with _connect() as connection:
            connection.execute(
                "INSERT INTO users (email, password_hash, salt, role) VALUES (?, ?, ?, ?)",
                (normalized_email, password_hash, salt.hex(), role),
            )
    except sqlite3.IntegrityError as error:
        raise ValueError("An account with this email already exists. Sign in instead.") from error


def authenticate_user(email: str, password: str) -> dict | None:
    normalized_email = _normalize_email(email)
    with _connect() as connection:
        user = connection.execute(
            "SELECT id, email, password_hash, salt, role FROM users WHERE email = ?",
            (normalized_email,),
        ).fetchone()
    if user is None:
        return None
    expected = _hash_password(password, bytes.fromhex(user["salt"]))
    if not hmac.compare_digest(expected, user["password_hash"]):
        return None
    return {"id": user["id"], "email": user["email"], "role": user["role"]}
