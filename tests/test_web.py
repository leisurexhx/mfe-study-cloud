from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from mfe_study_cloud.analysis.provider import FakeAnalysisProvider
from mfe_study_cloud.config import Settings
from mfe_study_cloud.db.models import AnalysisJob, Chapter
from mfe_study_cloud.jobs.runner import WorkerRunner
from mfe_study_cloud.storage import InMemoryObjectStore
from mfe_study_cloud.web.app import create_app

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "anonymous-demo.pdf"
ORIGIN = "http://testserver"


@dataclass(slots=True)
class WebContext:
    client: TestClient
    settings: Settings
    sessions: sessionmaker[Session]
    objects: InMemoryObjectStore


@pytest.fixture
def web(sessions: sessionmaker[Session]) -> Iterator[WebContext]:
    settings = Settings(
        MFE_ENV="test",
        MFE_PUBLIC_BASE_URL=ORIGIN,
        MFE_ANALYSIS_PROVIDER="fake",
        MFE_ANALYSIS_BATCH_PAGES=1,
        MFE_ANALYSIS_JOB_LEASE_SECONDS=30,
        MFE_ALLOWED_HOSTS="testserver",
    )
    objects = InMemoryObjectStore()
    app = create_app(settings=settings, sessions=sessions, object_store=objects)
    with TestClient(app, base_url=ORIGIN) as client:
        yield WebContext(client=client, settings=settings, sessions=sessions, objects=objects)


def _csrf_headers(client: TestClient, *, json_request: bool = False) -> dict[str, str]:
    headers = {"Origin": ORIGIN}
    if json_request:
        headers["X-CSRF-Token"] = client.cookies.get("mfe_csrf") or ""
    return headers


def _register(client: TestClient, *, email: str) -> None:
    assert client.get("/register").status_code == 200
    response = client.post(
        "/register",
        data={
            "email": email,
            "display_name": email.split("@", 1)[0],
            "password": "a sufficiently long password",
        },
        headers=_csrf_headers(client),
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def _create_uploaded_document(client: TestClient, sessions: sessionmaker[Session]) -> uuid.UUID:
    response = client.post(
        "/courses",
        data={"code": f"WEB-{uuid.uuid4().hex[:6]}", "name": "Web Integration"},
        headers=_csrf_headers(client),
        follow_redirects=False,
    )
    assert response.status_code == 303
    course_location = response.headers["location"]
    course_id = uuid.UUID(course_location.rsplit("/", 1)[-1])
    response = client.post(
        f"/courses/{course_id}/chapters",
        data={"number": "1", "title": "Upload"},
        headers=_csrf_headers(client),
        follow_redirects=False,
    )
    assert response.status_code == 303
    with sessions() as session:
        chapter_id = session.scalar(
            select(Chapter.id).where(Chapter.course_id == course_id)
        )
    assert chapter_id is not None
    response = client.post(
        f"/courses/{course_id}/chapters/{chapter_id}/documents",
        data={"title": "Anonymous Web Fixture"},
        files={"document": ("anonymous.pdf", FIXTURE.read_bytes(), "application/pdf")},
        headers=_csrf_headers(client),
        follow_redirects=False,
    )
    assert response.status_code == 303
    return uuid.UUID(response.headers["location"].rsplit("/", 1)[-1])


def test_security_headers_sessions_and_csrf_are_enforced(web: WebContext) -> None:
    response = web.client.get("/login")
    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["cache-control"] == "no-store"
    cookies = response.headers.get_list("set-cookie")
    assert any("mfe_session=" in value and "httponly" in value.casefold() for value in cookies)
    assert any("mfe_csrf=" in value and "samesite=strict" in value.casefold() for value in cookies)

    missing_origin = web.client.post(
        "/login",
        data={"email": "x@example.test", "password": "not a real password"},
    )
    assert missing_origin.status_code == 403
    wrong_origin = web.client.post(
        "/login",
        data={"email": "x@example.test", "password": "not a real password"},
        headers={"Origin": "https://attacker.example"},
    )
    assert wrong_origin.status_code == 403


def test_complete_browser_and_json_api_flow_with_fake_worker(web: WebContext) -> None:
    _register(web.client, email="web-flow@example.test")
    document_id = _create_uploaded_document(web.client, web.sessions)

    reader = web.client.get(f"/documents/{document_id}")
    assert reader.status_code == 200
    assert "Anonymous Web Fixture" in reader.text
    source = web.client.get(f"/documents/{document_id}/source.pdf")
    assert source.status_code == 200
    assert source.content.startswith(b"%PDF-")
    assert "anonymous.pdf" in source.headers["content-disposition"]
    rendered = web.client.get(f"/documents/{document_id}/pages/1.png?width=700")
    assert rendered.status_code == 200
    assert rendered.content.startswith(b"\x89PNG\r\n\x1a\n")

    start = web.client.post(
        f"/documents/{document_id}/analysis",
        headers=_csrf_headers(web.client),
        follow_redirects=False,
    )
    assert start.status_code == 303
    with web.sessions() as session:
        job = session.scalar(
            select(AnalysisJob).where(AnalysisJob.document_id == document_id)
        )
    assert job is not None
    runner = WorkerRunner(
        sessions=web.sessions,
        object_store=web.objects,
        provider=FakeAnalysisProvider(),
        settings=web.settings,
        worker_id="web-test-worker",
    )
    assert runner.run_until_idle() == 2

    job_response = web.client.get(f"/api/v1/jobs/{job.id}")
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "completed"
    analyzed_reader = web.client.get(f"/documents/{document_id}?page=1")
    assert "第 1 页匿名演示内容" in analyzed_reader.text

    note = web.client.post(
        f"/documents/{document_id}/notes",
        data={
            "page_number": "1",
            "note_type": "insight",
            "content": "web-only-duration-note",
        },
        headers=_csrf_headers(web.client),
        follow_redirects=False,
    )
    assert note.status_code == 303
    search = web.client.get("/api/v1/search", params={"q": "duration-note"})
    assert search.status_code == 200
    assert search.json()["results"][0]["source"] == "note"
    progress = web.client.post(
        f"/api/v1/documents/{document_id}/progress",
        json={"page_number": 2, "seconds_delta": 30},
        headers=_csrf_headers(web.client, json_request=True),
    )
    assert progress.status_code == 200
    assert progress.json()["is_completed"] is True


def test_http_document_boundary_hides_another_tenants_pdf(
    sessions: sessionmaker[Session],
) -> None:
    settings = Settings(
        MFE_ENV="test",
        MFE_PUBLIC_BASE_URL=ORIGIN,
        MFE_ALLOWED_HOSTS="testserver",
    )
    objects = InMemoryObjectStore()
    app = create_app(settings=settings, sessions=sessions, object_store=objects)
    with (
        TestClient(app, base_url=ORIGIN) as alice,
        TestClient(app, base_url=ORIGIN) as bob,
    ):
        _register(alice, email="http-alice@example.test")
        document_id = _create_uploaded_document(alice, sessions)
        _register(bob, email="http-bob@example.test")

        response = bob.get(f"/documents/{document_id}/source.pdf")
        assert response.status_code == 404
        assert not response.content.startswith(b"%PDF-")
        api_response = bob.get(f"/api/v1/jobs/{uuid.uuid4()}")
        assert api_response.status_code == 404


def test_pwa_manifest_and_worker_cache_only_public_assets(web: WebContext) -> None:
    manifest = web.client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    assert {icon["sizes"] for icon in manifest.json()["icons"]} == {"192x192", "512x512"}
    worker = web.client.get("/service-worker.js")
    assert worker.status_code == 200
    assert worker.headers["service-worker-allowed"] == "/"
    assert "/api/" not in worker.text
    assert "/documents/" not in worker.text
    assert "cache.put" not in worker.text
    assert re.search(r"request\.mode === \"navigate\"", worker.text)


def test_api_requires_authentication(web: WebContext) -> None:
    response = web.client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required."
