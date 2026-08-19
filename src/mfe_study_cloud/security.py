"""Password, session identifier, and CSRF helpers."""

from __future__ import annotations

import hmac
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=65_536, parallelism=2)


def normalize_email(value: str) -> str:
    email = value.strip().casefold()
    if len(email) > 320 or not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    return email


def validate_display_name(value: str) -> str:
    name = value.strip()
    if not 1 <= len(name) <= 120:
        raise ValueError("Display name must be 1 to 120 characters.")
    return name


def validate_password(value: str) -> str:
    if len(value) < 12 or len(value) > 256:
        raise ValueError("Password must be 12 to 256 characters.")
    return value


def hash_password(value: str) -> str:
    return _PASSWORD_HASHER.hash(validate_password(value))


def verify_password(password_hash: str, candidate: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, candidate)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_matches(expected: str | None, supplied: str | None) -> bool:
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))
