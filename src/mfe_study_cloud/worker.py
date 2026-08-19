"""Production entry point for concurrent database-leased workers."""

from __future__ import annotations

import logging
import signal
import threading
import uuid
from collections.abc import Callable

from mfe_study_cloud.analysis.provider import build_provider
from mfe_study_cloud.config import Settings, get_settings
from mfe_study_cloud.db.session import create_session_factory
from mfe_study_cloud.jobs.runner import WorkerRunner
from mfe_study_cloud.storage import S3ObjectStore

logger = logging.getLogger(__name__)


def _install_signal_handlers(stop: threading.Event) -> None:
    def request_stop(signum: int, frame: object) -> None:
        del signum, frame
        stop.set()

    for signal_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signal_name):
            signal.signal(getattr(signal, signal_name), request_stop)


def run_worker_pool(
    settings: Settings,
    *,
    stop: threading.Event | None = None,
    runner_factory: Callable[[int], WorkerRunner] | None = None,
) -> None:
    stop_event = stop or threading.Event()
    sessions = create_session_factory(settings.database_url)
    if runner_factory is None:
        readiness_store = S3ObjectStore(settings)
        readiness_store.ensure_ready()
        instance_id = uuid.uuid4().hex[:12]

        def runner_factory(index: int) -> WorkerRunner:
            return WorkerRunner(
                sessions=sessions,
                object_store=S3ObjectStore(settings),
                provider=build_provider(settings),
                settings=settings,
                worker_id=f"worker-{instance_id}-{index}",
            )

    threads = [
        threading.Thread(
            target=runner_factory(index).run_forever,
            args=(stop_event,),
            daemon=False,
            name=f"analysis-worker-{index}",
        )
        for index in range(1, settings.analysis_max_concurrent_jobs + 1)
    ]
    for thread in threads:
        thread.start()
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        stop_event.set()
        for thread in threads:
            thread.join(timeout=settings.worker_poll_seconds + 2)


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    stop = threading.Event()
    _install_signal_handlers(stop)
    logger.info(
        "analysis_worker_starting",
        extra={
            "provider": settings.analysis_provider,
            "concurrency": settings.analysis_max_concurrent_jobs,
        },
    )
    run_worker_pool(settings, stop=stop)


if __name__ == "__main__":
    main()
