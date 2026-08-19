"""Registration and authentication use cases."""

from __future__ import annotations

import re
import secrets
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from mfe_study_cloud.db.repositories import AuthRepository, TenantPrincipal
from mfe_study_cloud.db.session import session_scope
from mfe_study_cloud.security import (
    hash_password,
    normalize_email,
    validate_display_name,
    verify_password,
)
from mfe_study_cloud.services.errors import AuthenticationError, ConflictError


def _personal_slug(display_name: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", display_name.casefold()).strip("-")[:40]
    return f"{stem or 'workspace'}-{secrets.token_hex(5)}"


class AuthService:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def register(self, *, email: str, display_name: str, password: str) -> TenantPrincipal:
        normalized_email = normalize_email(email)
        clean_name = validate_display_name(display_name)
        password_hash = hash_password(password)
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        try:
            with session_scope(self._sessions) as session:
                repository = AuthRepository(session)
                if repository.user_by_email(normalized_email) is not None:
                    raise ConflictError("An account with this email already exists.")
                return repository.add_personal_account(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    email=normalized_email,
                    display_name=clean_name,
                    password_hash=password_hash,
                    tenant_slug=_personal_slug(clean_name),
                )
        except IntegrityError as exc:
            raise ConflictError("An account with this email already exists.") from exc

    def authenticate(self, *, email: str, password: str) -> TenantPrincipal:
        try:
            normalized_email = normalize_email(email)
        except ValueError as exc:
            raise AuthenticationError("Invalid email or password.") from exc
        with self._sessions() as session:
            repository = AuthRepository(session)
            user = repository.user_by_email(normalized_email)
            if (
                user is None
                or not user.is_active
                or not verify_password(user.password_hash, password)
            ):
                raise AuthenticationError("Invalid email or password.")
            principal = repository.first_principal(user.id)
            if principal is None:
                raise AuthenticationError("Account has no active workspace.")
            return principal

    def resolve_principal(
        self, *, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> TenantPrincipal | None:
        with self._sessions() as session:
            return AuthRepository(session).principal(user_id, tenant_id)
