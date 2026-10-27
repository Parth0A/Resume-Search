from __future__ import annotations

import pytest

import auth


@pytest.fixture
def isolated_auth_db(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "DB_PATH", tmp_path / "test_auth.db")
    monkeypatch.setattr(auth, "_ITERATIONS", 1_000)
    auth.initialize_auth_db()
    return auth


def test_register_and_authenticate_user(isolated_auth_db):
    isolated_auth_db.register_user("  User@Example.com ", "a-long-test-password", "Recruiter")
    user = isolated_auth_db.authenticate_user("user@example.com", "a-long-test-password")
    assert user is not None
    assert user["email"] == "user@example.com"
    assert user["role"] == "Recruiter"
    assert "password_hash" not in user


def test_password_is_not_stored_as_plaintext(isolated_auth_db):
    password = "another-long-test-password"
    isolated_auth_db.register_user("user@example.com", password, "Job seeker")
    with isolated_auth_db._connect() as connection:
        row = connection.execute(
            "SELECT password_hash, salt FROM users WHERE email = ?",
            ("user@example.com",),
        ).fetchone()
    assert row["password_hash"] != password
    assert row["salt"]
    assert len(row["salt"]) >= 32


def test_wrong_password_does_not_authenticate(isolated_auth_db):
    isolated_auth_db.register_user("user@example.com", "a-long-test-password", "Recruiter")
    assert isolated_auth_db.authenticate_user("user@example.com", "wrong-password") is None


def test_duplicate_email_is_rejected(isolated_auth_db):
    isolated_auth_db.register_user("user@example.com", "a-long-test-password", "Recruiter")
    with pytest.raises(ValueError, match="already exists"):
        isolated_auth_db.register_user("USER@example.com", "another-long-password", "Job seeker")


@pytest.mark.parametrize("password", ["", "short", "x" * (auth.MAX_PASSWORD_CHARS + 1)])
def test_weak_or_oversized_password_rejected(isolated_auth_db, password):
    with pytest.raises(ValueError):
        isolated_auth_db.register_user("user@example.com", password, "Recruiter")


def test_invalid_role_is_rejected(isolated_auth_db):
    with pytest.raises(ValueError, match="valid account type"):
        isolated_auth_db.register_user("user@example.com", "a-long-test-password", "Administrator")


def test_login_attempts_are_throttled(isolated_auth_db):
    isolated_auth_db.register_user("user@example.com", "a-long-test-password", "Recruiter")
    for _ in range(auth.MAX_FAILED_LOGINS):
        assert isolated_auth_db.authenticate_user("user@example.com", "incorrect-password") is None
    # Correct password is temporarily blocked after repeated failed attempts.
    assert isolated_auth_db.authenticate_user("user@example.com", "a-long-test-password") is None


def test_user_can_be_revalidated_by_id(isolated_auth_db):
    isolated_auth_db.register_user("user@example.com", "a-long-test-password", "Job seeker")
    user = isolated_auth_db.authenticate_user("user@example.com", "a-long-test-password")
    assert user is not None
    assert isolated_auth_db.get_user_by_id(user["id"]) == {
        "id": user["id"],
        "email": "user@example.com",
        "role": "Job seeker",
    }
    assert isolated_auth_db.get_user_by_id(-1) is None
