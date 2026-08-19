"""One-batch-at-a-time analysis worker with bounded retries and leases."""

from __future__ import annotations

import logging
import threading
import uuid
from contextlib import AbstractContextManager
from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from mfe_study_cloud.analysis.errors import AnalysisError
from mfe_study_cloud.analysis.pdf_batches import PdfBatch, split_pdf
from mfe_study_cloud.analysis.provider import AnalysisProvider, AnalysisRequest
from mfe_study_cloud.config import Settings
from mfe_study_cloud.db.session import session_scope
from mfe_study_cloud.jobs.errors import LeaseLostError
from mfe_study_cloud.jobs.repository import JobQueueRepository
from mfe_study_cloud.storage import ObjectStore

logger = logging.getLogger(__name__)


class WorkerRunner:
    def __init__(
        self,
        *,
        sessions: sessionmaker[Session],
        object_store: ObjectStore,
        provider: AnalysisProvider,
        settings: Settings,
        worker_id: str | None = None,
    ) -> None:
        self._sessions = sessions
        self._objects = object_store
        self._provider = provider
        self._settings = settings
        self.worker_id = worker_id or f"worker-{uuid.uuid4()}"

    def process_one(self) -> bool:
        with session_scope(self._sessions) as session:
            claimed = JobQueueRepository(session).claim(
                worker_id=self.worker_id,
                lease_seconds=self._settings.analysis_job_lease_seconds,
            )
            if claimed is None:
                return False
            tenant_id = claimed.tenant_id
            job_id = claimed.id

        try:
            with self._sessions() as session:
                job, document = JobQueueRepository(session).claimed_document(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    worker_id=self.worker_id,
                )
                if job.cancel_requested:
                    with session_scope(self._sessions) as cancel_session:
                        JobQueueRepository(cancel_session).finish_cancelled(
                            tenant_id=tenant_id,
                            job_id=job_id,
                            worker_id=self.worker_id,
                        )
                    return True
                document_id = document.id
                document_title = document.title
                document_sha256 = document.sha256
                object_key = document.object_key
                next_page = job.next_page

            raw = self._objects.get(object_key)
            batch = self._batch_for(raw, next_page)
            request = AnalysisRequest(
                document_id=str(document_id),
                document_title=document_title,
                pdf_bytes=batch.pdf_bytes,
                first_page=batch.first_page,
                last_page=batch.last_page,
            )
            with _LeaseHeartbeat(self, tenant_id=tenant_id, job_id=job_id):
                result = self._provider.analyze(request)
            with session_scope(self._sessions) as session:
                JobQueueRepository(session).complete_batch(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    worker_id=self.worker_id,
                    document_sha256=document_sha256,
                    result=result,
                )
        except LeaseLostError:
            logger.warning("analysis_lease_lost", extra={"job_id": str(job_id)})
        except AnalysisError as exc:
            self._record_failure(
                tenant_id=tenant_id,
                job_id=job_id,
                retryable=exc.retryable,
                summary=_safe_failure_summary(exc),
            )
        except (FileNotFoundError, ValueError):
            self._record_failure(
                tenant_id=tenant_id,
                job_id=job_id,
                retryable=False,
                summary="The stored PDF could not be processed safely.",
            )
        except Exception:
            logger.exception("analysis_internal_failure", extra={"job_id": str(job_id)})
            self._record_failure(
                tenant_id=tenant_id,
                job_id=job_id,
                retryable=True,
                summary="An internal processing error occurred.",
            )
        return True

    def run_until_idle(self, *, maximum_jobs: int = 10_000) -> int:
        processed = 0
        while processed < maximum_jobs and self.process_one():
            processed += 1
        return processed

    def run_forever(self, stop: threading.Event) -> None:
        while not stop.is_set():
            if not self.process_one():
                stop.wait(self._settings.worker_poll_seconds)

    def heartbeat(self, *, tenant_id: uuid.UUID, job_id: uuid.UUID) -> bool:
        with session_scope(self._sessions) as session:
            return JobQueueRepository(session).heartbeat(
                tenant_id=tenant_id,
                job_id=job_id,
                worker_id=self.worker_id,
                lease_seconds=self._settings.analysis_job_lease_seconds,
            )

    def _batch_for(self, raw: bytes, next_page: int) -> PdfBatch:
        batches = split_pdf(
            raw,
            batch_pages=self._settings.analysis_batch_pages,
            max_bytes=self._settings.analysis_max_input_bytes,
            max_pages=self._settings.analysis_max_document_pages,
        )
        for batch in batches:
            if batch.first_page == next_page:
                return batch
        raise ValueError("Job progress is not aligned to a PDF batch boundary.")

    def _record_failure(
        self,
        *,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
        retryable: bool,
        summary: str,
    ) -> None:
        try:
            with session_scope(self._sessions) as session:
                JobQueueRepository(session).record_failure(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    worker_id=self.worker_id,
                    retryable=retryable,
                    summary=summary,
                )
        except LeaseLostError:
            logger.warning("analysis_failure_after_lease_loss", extra={"job_id": str(job_id)})


class _LeaseHeartbeat(AbstractContextManager[None]):
    def __init__(self, runner: WorkerRunner, *, tenant_id: uuid.UUID, job_id: uuid.UUID) -> None:
        self._runner = runner
        self._tenant_id = tenant_id
        self._job_id = job_id
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> None:
        interval = max(5.0, self._runner._settings.analysis_job_lease_seconds / 3)
        self._thread = threading.Thread(
            target=self._run,
            args=(interval,),
            daemon=True,
            name=f"heartbeat-{self._job_id}",
        )
        self._thread.start()
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        return None

    def _run(self, interval: float) -> None:
        while not self._stop.wait(interval):
            try:
                if not self._runner.heartbeat(
                    tenant_id=self._tenant_id,
                    job_id=self._job_id,
                ):
                    return
            except Exception:
                logger.exception(
                    "analysis_heartbeat_failure",
                    extra={"job_id": str(self._job_id)},
                )


def _safe_failure_summary(error: AnalysisError) -> str:
    if error.retryable:
        return "The analysis provider is temporarily unavailable."
    return "The analysis provider could not accept this PDF batch."
