from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from mfe_study_cloud.analysis.errors import ProviderSchemaError, ProviderTransientError
from mfe_study_cloud.analysis.provider import (
    AnalysisProvider,
    AnalysisRequest,
    AnalysisResult,
    FakeAnalysisProvider,
)
from mfe_study_cloud.config import Settings
from mfe_study_cloud.db.models import Document, PageAnalysis
from mfe_study_cloud.db.repositories import TenantPrincipal
from mfe_study_cloud.db.session import session_scope
from mfe_study_cloud.jobs.repository import JobQueueRepository
from mfe_study_cloud.jobs.runner import WorkerRunner
from mfe_study_cloud.services.auth import AuthService
from mfe_study_cloud.services.errors import NotFoundError
from mfe_study_cloud.services.jobs import JobService
from mfe_study_cloud.services.study import StudyService
from mfe_study_cloud.storage import InMemoryObjectStore

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "anonymous-demo.pdf"


class FlakyProvider:
    name = "fake"

    def __init__(self, *, transient_failures: int = 0, fail_from_page: int | None = None) -> None:
        self.transient_failures = transient_failures
        self.fail_from_page = fail_from_page
        self.calls = 0
        self._fake = FakeAnalysisProvider()

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        self.calls += 1
        if self.calls <= self.transient_failures:
            raise ProviderTransientError("test transient failure")
        if self.fail_from_page is not None and request.first_page >= self.fail_from_page:
            raise ProviderSchemaError("test permanent failure")
        return self._fake.analyze(request)


def _settings(*, batch_pages: int = 1, attempts: int = 3) -> Settings:
    return Settings(
        MFE_ENV="test",
        MFE_ANALYSIS_PROVIDER="fake",
        MFE_ANALYSIS_BATCH_PAGES=batch_pages,
        MFE_ANALYSIS_MAX_ATTEMPTS=attempts,
        MFE_ANALYSIS_JOB_LEASE_SECONDS=30,
    )


def _document_setup(
    sessions: sessionmaker[Session],
    *,
    email: str = "jobs@example.test",
) -> tuple[TenantPrincipal, InMemoryObjectStore, Document]:
    auth = AuthService(sessions)
    principal = auth.register(
        email=email,
        display_name="Job Owner",
        password="job owner secure password",
    )
    objects = InMemoryObjectStore()
    study = StudyService(
        sessions,
        objects,
        max_upload_bytes=1_000_000,
        max_document_pages=10,
    )
    course = study.create_course(principal, code="JOB-101", name="Jobs")
    chapter = study.create_chapter(
        principal,
        course_id=course.id,
        number="1",
        title="Queue",
    )
    document = study.upload_document(
        principal,
        course_id=course.id,
        chapter_id=chapter.id,
        filename="jobs.pdf",
        data=FIXTURE.read_bytes(),
    )
    return principal, objects, document


def _runner(
    sessions: sessionmaker[Session],
    objects: InMemoryObjectStore,
    provider: AnalysisProvider,
    settings: Settings,
    *,
    worker_id: str = "test-worker",
) -> WorkerRunner:
    return WorkerRunner(
        sessions=sessions,
        object_store=objects,
        provider=provider,
        settings=settings,
        worker_id=worker_id,
    )


def test_fake_job_runs_in_batches_and_persists_page_aligned_output(
    sessions: sessionmaker[Session],
) -> None:
    settings = _settings(batch_pages=1)
    principal, objects, document = _document_setup(sessions)
    service = JobService(sessions, settings)
    job = service.start(principal, document_id=document.id)

    assert service.start(principal, document_id=document.id).id == job.id
    runner = _runner(sessions, objects, FakeAnalysisProvider(), settings)
    assert runner.process_one() is True
    after_first = service.status(principal, job_id=job.id)
    assert (after_first.status, after_first.completed_pages, after_first.next_page) == (
        "queued",
        1,
        2,
    )
    assert runner.process_one() is True
    completed = service.status(principal, job_id=job.id)
    assert completed.status == "completed"
    assert completed.completed_pages == 2
    assert runner.process_one() is False

    with sessions() as session:
        pages = list(
            session.scalars(
                select(PageAnalysis)
                .where(
                    PageAnalysis.tenant_id == principal.tenant_id,
                    PageAnalysis.document_id == document.id,
                    PageAnalysis.is_active.is_(True),
                )
                .order_by(PageAnalysis.page_number)
            )
        )
    assert [page.page_number for page in pages] == [1, 2]
    assert all(page.provider == "fake" for page in pages)
    assert "匿名演示内容" in pages[0].searchable_text


def test_transient_failure_retries_then_completes(
    sessions: sessionmaker[Session],
) -> None:
    settings = _settings(batch_pages=2, attempts=2)
    principal, objects, document = _document_setup(sessions, email="retry@example.test")
    service = JobService(sessions, settings)
    job = service.start(principal, document_id=document.id)
    provider = FlakyProvider(transient_failures=1)
    runner = _runner(sessions, objects, provider, settings)

    runner.process_one()
    retrying = service.status(principal, job_id=job.id)
    assert retrying.status == "queued"
    assert retrying.attempt_count == 1
    assert retrying.error_summary is not None

    runner.process_one()
    completed = service.status(principal, job_id=job.id)
    assert completed.status == "completed"
    assert completed.attempt_count == 0
    assert provider.calls == 2


def test_partial_job_preserves_pages_and_can_resume(
    sessions: sessionmaker[Session],
) -> None:
    settings = _settings(batch_pages=1)
    principal, objects, document = _document_setup(sessions, email="partial@example.test")
    service = JobService(sessions, settings)
    job = service.start(principal, document_id=document.id)
    provider = FlakyProvider(fail_from_page=2)
    runner = _runner(sessions, objects, provider, settings)

    runner.process_one()
    runner.process_one()
    partial = service.status(principal, job_id=job.id)
    assert (partial.status, partial.completed_pages, partial.failed_pages) == ("partial", 1, 1)

    provider.fail_from_page = None
    assert service.retry(principal, job_id=job.id).status == "queued"
    runner.run_until_idle()
    completed = service.status(principal, job_id=job.id)
    assert (completed.status, completed.completed_pages, completed.failed_pages) == (
        "completed",
        2,
        0,
    )
    with sessions() as session:
        pages = list(
            session.scalars(
                select(PageAnalysis).where(
                    PageAnalysis.tenant_id == principal.tenant_id,
                    PageAnalysis.document_id == document.id,
                )
            )
        )
    assert len(pages) == 2


def test_cancel_and_job_status_are_tenant_scoped(
    sessions: sessionmaker[Session],
) -> None:
    settings = _settings(batch_pages=2)
    alice, objects, document = _document_setup(sessions, email="job-a@example.test")
    bob = AuthService(sessions).register(
        email="job-b@example.test",
        display_name="Job B",
        password="job b secure password",
    )
    service = JobService(sessions, settings)
    job = service.start(alice, document_id=document.id)

    with pytest.raises(NotFoundError):
        service.status(bob, job_id=job.id)
    with pytest.raises(NotFoundError):
        service.cancel(bob, job_id=job.id)
    assert service.cancel(alice, job_id=job.id).status == "cancelled"
    assert _runner(sessions, objects, FakeAnalysisProvider(), settings).process_one() is False


def test_expired_lease_is_reclaimed_and_old_owner_cannot_heartbeat(
    sessions: sessionmaker[Session],
) -> None:
    settings = _settings(batch_pages=2)
    principal, _, document = _document_setup(sessions, email="lease@example.test")
    job = JobService(sessions, settings).start(
        principal, document_id=document.id
    )
    started = datetime(2026, 8, 19, 1, 0, tzinfo=UTC)
    with session_scope(sessions) as session:
        first = JobQueueRepository(session).claim(
            worker_id="worker-a",
            lease_seconds=30,
            now=started,
        )
        assert first is not None and first.id == job.id
    with session_scope(sessions) as session:
        assert (
            JobQueueRepository(session).claim(
                worker_id="worker-b",
                lease_seconds=30,
                now=started + timedelta(seconds=10),
            )
            is None
        )
    with session_scope(sessions) as session:
        reclaimed = JobQueueRepository(session).claim(
            worker_id="worker-b",
            lease_seconds=30,
            now=started + timedelta(seconds=31),
        )
        assert reclaimed is not None and reclaimed.id == job.id
    with session_scope(sessions) as session:
        assert (
            JobQueueRepository(session).heartbeat(
                tenant_id=principal.tenant_id,
                job_id=job.id,
                worker_id="worker-a",
                lease_seconds=30,
                now=started + timedelta(seconds=32),
            )
            is False
        )
