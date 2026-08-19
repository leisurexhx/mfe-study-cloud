"""Persistence for idempotent jobs and database-backed worker leases."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from mfe_study_cloud.analysis.models import PageAnalysisOutput
from mfe_study_cloud.analysis.provider import AnalysisResult
from mfe_study_cloud.db.models import AnalysisJob, Document, PageAnalysis
from mfe_study_cloud.jobs.errors import LeaseLostError


def utcnow() -> datetime:
    return datetime.now(UTC)


def analysis_idempotency_key(
    *,
    document_sha256: str,
    first_page: int,
    last_page: int,
    provider: str,
    model: str,
    prompt_version: str,
    schema_version: str,
) -> str:
    material = ":".join(
        (
            document_sha256,
            str(first_page),
            str(last_page),
            provider,
            model,
            prompt_version,
            schema_version,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RecentJob:
    id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    status: str
    completed_pages: int
    total_pages: int
    error_summary: str | None


class TenantJobRepository:
    def __init__(self, session: Session, tenant_id: uuid.UUID) -> None:
        self._session = session
        self.tenant_id = tenant_id

    def job(self, job_id: uuid.UUID) -> AnalysisJob | None:
        return self._session.scalar(
            select(AnalysisJob).where(
                AnalysisJob.tenant_id == self.tenant_id,
                AnalysisJob.id == job_id,
            )
        )

    def by_idempotency_key(self, key: str) -> AnalysisJob | None:
        return self._session.scalar(
            select(AnalysisJob).where(
                AnalysisJob.tenant_id == self.tenant_id,
                AnalysisJob.idempotency_key == key,
            )
        )

    def latest_for_document(self, document_id: uuid.UUID) -> AnalysisJob | None:
        return self._session.scalar(
            select(AnalysisJob)
            .where(
                AnalysisJob.tenant_id == self.tenant_id,
                AnalysisJob.document_id == document_id,
            )
            .order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc())
            .limit(1)
        )

    def recent(self, *, limit: int = 6) -> list[RecentJob]:
        rows = self._session.execute(
            select(
                AnalysisJob.id,
                AnalysisJob.document_id,
                Document.title,
                AnalysisJob.status,
                AnalysisJob.completed_pages,
                AnalysisJob.total_pages,
                AnalysisJob.error_summary,
            )
            .join(
                Document,
                (Document.id == AnalysisJob.document_id)
                & (Document.tenant_id == AnalysisJob.tenant_id),
            )
            .where(AnalysisJob.tenant_id == self.tenant_id)
            .order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc())
            .limit(max(1, min(limit, 20)))
        )
        return [
            RecentJob(
                id=row.id,
                document_id=row.document_id,
                document_title=row.title,
                status=row.status,
                completed_pages=row.completed_pages,
                total_pages=row.total_pages,
                error_summary=row.error_summary,
            )
            for row in rows
        ]

    def add_job(
        self,
        *,
        job_id: uuid.UUID,
        document: Document,
        provider: str,
        model: str,
        prompt_version: str,
        schema_version: str,
        idempotency_key: str,
        max_attempts: int,
    ) -> AnalysisJob:
        job = AnalysisJob(
            id=job_id,
            tenant_id=self.tenant_id,
            document_id=document.id,
            status="queued",
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            schema_version=schema_version,
            idempotency_key=idempotency_key,
            total_pages=document.page_count,
            completed_pages=0,
            failed_pages=0,
            next_page=1,
            attempt_count=0,
            max_attempts=max_attempts,
            cancel_requested=False,
            input_tokens=0,
            output_tokens=0,
        )
        document.status = "queued"
        self._session.add(job)
        self._session.flush()
        return job

    def request_cancel(self, job_id: uuid.UUID) -> AnalysisJob | None:
        job = self.job(job_id)
        if job is None:
            return None
        if job.status in {"completed", "failed", "cancelled"}:
            return job
        job.cancel_requested = True
        if job.status in {"queued", "partial"}:
            job.status = "cancelled"
            job.completed_at = utcnow()
            job.lease_owner = None
            job.lease_expires_at = None
        self._session.flush()
        return job

    def retry(self, job_id: uuid.UUID) -> AnalysisJob | None:
        job = self.job(job_id)
        if job is None:
            return None
        if job.status not in {"failed", "partial", "cancelled"}:
            return job
        job.status = "queued"
        job.cancel_requested = False
        job.attempt_count = 0
        job.failed_pages = 0
        job.error_summary = None
        job.completed_at = None
        job.lease_owner = None
        job.lease_expires_at = None
        self._session.flush()
        return job


class JobQueueRepository:
    """Trusted worker-only cross-tenant queue operations.

    The global claim is the sole intentional cross-tenant query. Once claimed, all
    subsequent operations include the returned tenant identifier and lease owner.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def claim(
        self, *, worker_id: str, lease_seconds: int, now: datetime | None = None
    ) -> AnalysisJob | None:
        claimed_at = now or utcnow()
        job = self._session.scalar(
            select(AnalysisJob)
            .where(
                AnalysisJob.cancel_requested.is_(False),
                AnalysisJob.attempt_count < AnalysisJob.max_attempts,
                or_(
                    AnalysisJob.status == "queued",
                    and_(
                        AnalysisJob.status == "running",
                        AnalysisJob.lease_expires_at < claimed_at,
                    ),
                ),
            )
            .order_by(AnalysisJob.created_at, AnalysisJob.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return None
        job.status = "running"
        job.lease_owner = worker_id
        job.lease_expires_at = claimed_at + timedelta(seconds=lease_seconds)
        job.heartbeat_at = claimed_at
        job.started_at = job.started_at or claimed_at
        self._session.flush()
        return job

    def heartbeat(
        self,
        *,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
        worker_id: str,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> bool:
        heartbeat_at = now or utcnow()
        job = self._claimed_job(
            tenant_id=tenant_id,
            job_id=job_id,
            worker_id=worker_id,
        )
        if job is None:
            return False
        job.heartbeat_at = heartbeat_at
        job.lease_expires_at = heartbeat_at + timedelta(seconds=lease_seconds)
        self._session.flush()
        return True

    def claimed_document(
        self, *, tenant_id: uuid.UUID, job_id: uuid.UUID, worker_id: str
    ) -> tuple[AnalysisJob, Document]:
        row = self._session.execute(
            select(AnalysisJob, Document)
            .join(
                Document,
                and_(
                    Document.id == AnalysisJob.document_id,
                    Document.tenant_id == AnalysisJob.tenant_id,
                ),
            )
            .where(
                AnalysisJob.tenant_id == tenant_id,
                AnalysisJob.id == job_id,
                AnalysisJob.status == "running",
                AnalysisJob.lease_owner == worker_id,
            )
        ).one_or_none()
        if row is None:
            raise LeaseLostError("Analysis job lease is no longer owned by this worker.")
        return row[0], row[1]

    def complete_batch(
        self,
        *,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
        worker_id: str,
        document_sha256: str,
        result: AnalysisResult,
    ) -> AnalysisJob:
        job, document = self.claimed_document(
            tenant_id=tenant_id,
            job_id=job_id,
            worker_id=worker_id,
        )
        if job.cancel_requested:
            return self.finish_cancelled(
                tenant_id=tenant_id,
                job_id=job_id,
                worker_id=worker_id,
            )
        expected_first = job.next_page
        actual_pages = [page.page_number for page in result.output.pages]
        if not actual_pages or actual_pages != list(
            range(expected_first, expected_first + len(actual_pages))
        ):
            raise ValueError("Analysis batch does not continue at the job's next page.")
        if actual_pages[-1] > job.total_pages:
            raise ValueError("Analysis batch exceeds the document page count.")
        if (
            result.provider != job.provider
            or result.model != job.model
            or result.prompt_version != job.prompt_version
            or result.schema_version != job.schema_version
        ):
            raise ValueError("Analysis result provenance does not match the claimed job.")

        for page in result.output.pages:
            self._upsert_page(
                tenant_id=tenant_id,
                document=document,
                job=job,
                page=page,
                result=result,
                document_sha256=document_sha256,
            )
        last_page = actual_pages[-1]
        job.completed_pages = max(job.completed_pages, last_page)
        job.next_page = last_page + 1
        job.failed_pages = 0
        job.attempt_count = 0
        job.input_tokens += result.input_tokens
        job.output_tokens += result.output_tokens
        job.error_summary = None
        job.lease_owner = None
        job.lease_expires_at = None
        if job.next_page > job.total_pages:
            job.status = "completed"
            job.completed_at = utcnow()
            document.status = "complete"
        else:
            job.status = "queued"
            document.status = "processing"
        self._session.flush()
        return job

    def record_failure(
        self,
        *,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
        worker_id: str,
        retryable: bool,
        summary: str,
    ) -> AnalysisJob:
        job, document = self.claimed_document(
            tenant_id=tenant_id,
            job_id=job_id,
            worker_id=worker_id,
        )
        job.attempt_count += 1
        job.error_summary = summary[:2000]
        job.lease_owner = None
        job.lease_expires_at = None
        if retryable and job.attempt_count < job.max_attempts and not job.cancel_requested:
            job.status = "queued"
            document.status = "processing" if job.completed_pages else "queued"
        else:
            job.failed_pages = job.total_pages - job.completed_pages
            job.status = "partial" if job.completed_pages else "failed"
            job.completed_at = utcnow()
            document.status = "partial" if job.completed_pages else "error"
        self._session.flush()
        return job

    def finish_cancelled(
        self, *, tenant_id: uuid.UUID, job_id: uuid.UUID, worker_id: str
    ) -> AnalysisJob:
        job, document = self.claimed_document(
            tenant_id=tenant_id,
            job_id=job_id,
            worker_id=worker_id,
        )
        job.status = "cancelled"
        job.cancel_requested = True
        job.completed_at = utcnow()
        job.lease_owner = None
        job.lease_expires_at = None
        document.status = "partial" if job.completed_pages else "registered"
        self._session.flush()
        return job

    def _claimed_job(
        self, *, tenant_id: uuid.UUID, job_id: uuid.UUID, worker_id: str
    ) -> AnalysisJob | None:
        return self._session.scalar(
            select(AnalysisJob).where(
                AnalysisJob.tenant_id == tenant_id,
                AnalysisJob.id == job_id,
                AnalysisJob.status == "running",
                AnalysisJob.lease_owner == worker_id,
            )
        )

    def _upsert_page(
        self,
        *,
        tenant_id: uuid.UUID,
        document: Document,
        job: AnalysisJob,
        page: PageAnalysisOutput,
        result: AnalysisResult,
        document_sha256: str,
    ) -> None:
        payload = page.model_dump(mode="json")
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        content_hash = hashlib.sha256(
            ":".join(
                (
                    document_sha256,
                    str(page.page_number),
                    result.provider,
                    result.model,
                    result.prompt_version,
                    result.schema_version,
                    canonical,
                )
            ).encode("utf-8")
        ).hexdigest()
        active = self._session.scalar(
            select(PageAnalysis)
            .where(
                PageAnalysis.tenant_id == tenant_id,
                PageAnalysis.document_id == document.id,
                PageAnalysis.page_number == page.page_number,
                PageAnalysis.is_active.is_(True),
            )
            .with_for_update()
        )
        if active is not None and active.content_hash == content_hash:
            return
        version = 1
        if active is not None:
            active.is_active = False
            version = active.version + 1
        self._session.add(
            PageAnalysis(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                document_id=document.id,
                job_id=job.id,
                page_number=page.page_number,
                version=version,
                is_active=True,
                payload=payload,
                searchable_text=_searchable_text(payload),
                content_hash=content_hash,
                provider=result.provider,
                model=result.model,
                response_id=result.response_id,
                prompt_version=result.prompt_version,
                schema_version=result.schema_version,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
            )
        )


def _searchable_text(
    value: Mapping[str, Any] | Sequence[Any] | str | int | float | bool | None,
) -> str:
    parts: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, str):
            if item.strip():
                parts.append(item.strip())
        elif isinstance(item, Mapping):
            for child in item.values():
                visit(child)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for child in item:
                visit(child)

    visit(value)
    return "\n".join(parts)
