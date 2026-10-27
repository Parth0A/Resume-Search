"""SQLite-backed local authentication for the Resume Search prototype.

Passwords use per-user salts and PBKDF2-HMAC-SHA256. This is a local/demo
implementation, not a substitute for a managed identity provider in production.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(os.getenv("RESUME_SEARCH_DB", str(Path(__file__).with_name("resume_search.db"))))
_ITERATIONS = 310_000
MAX_PASSWORD_CHARS = 1024
LOGIN_WINDOW_SECONDS = 15 * 60
MAX_FAILED_LOGINS = 5
_DUMMY_SALT = b"resume-search-dummy-salt"
_DUMMY_HASH = hashlib.pbkdf2_hmac("sha256", b"not-a-real-password", _DUMMY_SALT, _ITERATIONS).hex()


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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS login_attempts (
                email TEXT NOT NULL,
                attempted_at REAL NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_login_attempts_email_time "
            "ON login_attempts(email, attempted_at)"
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
    if not password or len(password) < 12:
        raise ValueError("Use a password with at least 12 characters.")
    if len(password) > MAX_PASSWORD_CHARS:
        raise ValueError(f"Password must be {MAX_PASSWORD_CHARS} characters or fewer.")
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
    if not password or len(password) > MAX_PASSWORD_CHARS:
        # Perform a bounded hash so nonexistent users and invalid passwords do not
        # immediately bypass the same general verification path.
        _hash_password("invalid-password", _DUMMY_SALT)
        return None

    now = time.time()
    cutoff = now - LOGIN_WINDOW_SECONDS
    with _connect() as connection:
        connection.execute("DELETE FROM login_attempts WHERE attempted_at < ?", (cutoff,))
        attempts = connection.execute(
            "SELECT COUNT(*) FROM login_attempts WHERE email = ? AND attempted_at >= ?",
            (normalized_email, cutoff),
        ).fetchone()[0]
        if attempts >= MAX_FAILED_LOGINS:
            return None
        user = connection.execute(
            "SELECT id, email, password_hash, salt, role FROM users WHERE email = ?",
            (normalized_email,),
        ).fetchone()

    if user is None:
        expected = _hash_password(password, _DUMMY_SALT)
        hmac.compare_digest(expected, _DUMMY_HASH)
        valid = False
    else:
        expected = _hash_password(password, bytes.fromhex(user["salt"]))
        valid = hmac.compare_digest(expected, user["password_hash"])

    with _connect() as connection:
        if not valid:
            connection.execute(
                "INSERT INTO login_attempts(email, attempted_at) VALUES (?, ?)",
                (normalized_email, now),
            )
            return None
        connection.execute("DELETE FROM login_attempts WHERE email = ?", (normalized_email,))

    return {"id": user["id"], "email": user["email"], "role": user["role"]}


def get_user_by_id(user_id: int) -> dict | None:
    """Revalidate an authenticated session against the current account record."""
    with _connect() as connection:
        user = connection.execute(
            "SELECT id, email, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if user is None:
        return None
    return {"id": user["id"], "email": user["email"], "role": user["role"]}
