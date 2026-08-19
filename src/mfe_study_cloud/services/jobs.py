"""Authenticated analysis job commands and status queries."""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from mfe_study_cloud.analysis.models import PROMPT_VERSION, SCHEMA_VERSION
from mfe_study_cloud.config import Settings
from mfe_study_cloud.db.models import AnalysisJob
from mfe_study_cloud.db.repositories import StudyRepository, TenantPrincipal
from mfe_study_cloud.db.session import session_scope
from mfe_study_cloud.jobs.repository import TenantJobRepository, analysis_idempotency_key
from mfe_study_cloud.services.errors import NotFoundError, ValidationError


def configured_model(settings: Settings) -> str:
    if settings.analysis_provider == "fake":
        return "fake-v1"
    if settings.analysis_provider == "openai" and settings.openai_model:
        return settings.openai_model
    raise ValidationError("Analysis is disabled until a server provider is configured.")


class JobService:
    def __init__(self, sessions: sessionmaker[Session], settings: Settings) -> None:
        self._sessions = sessions
        self._settings = settings

    def start(self, principal: TenantPrincipal, *, document_id: uuid.UUID) -> AnalysisJob:
        provider = self._settings.analysis_provider
        model = configured_model(self._settings)
        try:
            with session_scope(self._sessions) as session:
                study = StudyRepository(session, principal.tenant_id)
                document = study.document(document_id)
                if document is None:
                    raise NotFoundError("Document was not found.")
                key = analysis_idempotency_key(
                    document_sha256=document.sha256,
                    first_page=1,
                    last_page=document.page_count,
                    provider=provider,
                    model=model,
                    prompt_version=PROMPT_VERSION,
                    schema_version=SCHEMA_VERSION,
                )
                jobs = TenantJobRepository(session, principal.tenant_id)
                existing = jobs.by_idempotency_key(key)
                if existing is not None:
                    return existing
                return jobs.add_job(
                    job_id=uuid.uuid4(),
                    document=document,
                    provider=provider,
                    model=model,
                    prompt_version=PROMPT_VERSION,
                    schema_version=SCHEMA_VERSION,
                    idempotency_key=key,
                    max_attempts=self._settings.analysis_max_attempts,
                )
        except IntegrityError:
            with self._sessions() as session:
                document = StudyRepository(session, principal.tenant_id).document(document_id)
                if document is None:
                    raise NotFoundError("Document was not found.") from None
                key = analysis_idempotency_key(
                    document_sha256=document.sha256,
                    first_page=1,
                    last_page=document.page_count,
                    provider=provider,
                    model=model,
                    prompt_version=PROMPT_VERSION,
                    schema_version=SCHEMA_VERSION,
                )
                existing = TenantJobRepository(
                    session, principal.tenant_id
                ).by_idempotency_key(key)
                if existing is None:
                    raise
                return existing

    def status(self, principal: TenantPrincipal, *, job_id: uuid.UUID) -> AnalysisJob:
        with self._sessions() as session:
            job = TenantJobRepository(session, principal.tenant_id).job(job_id)
            if job is None:
                raise NotFoundError("Analysis job was not found.")
            return job

    def latest_for_document(
        self, principal: TenantPrincipal, *, document_id: uuid.UUID
    ) -> AnalysisJob | None:
        with self._sessions() as session:
            if StudyRepository(session, principal.tenant_id).document(document_id) is None:
                raise NotFoundError("Document was not found.")
            return TenantJobRepository(
                session, principal.tenant_id
            ).latest_for_document(document_id)

    def cancel(self, principal: TenantPrincipal, *, job_id: uuid.UUID) -> AnalysisJob:
        with session_scope(self._sessions) as session:
            job = TenantJobRepository(session, principal.tenant_id).request_cancel(job_id)
            if job is None:
                raise NotFoundError("Analysis job was not found.")
            return job

    def retry(self, principal: TenantPrincipal, *, job_id: uuid.UUID) -> AnalysisJob:
        with session_scope(self._sessions) as session:
            job = TenantJobRepository(session, principal.tenant_id).retry(job_id)
            if job is None:
                raise NotFoundError("Analysis job was not found.")
            return job
