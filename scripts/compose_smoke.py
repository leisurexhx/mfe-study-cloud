"""Exercise the public Fake Provider journey against a running Compose stack."""

from __future__ import annotations

import io
import os
import re
import time
import uuid
from urllib.parse import urlsplit

import httpx
from pypdf import PdfWriter

BASE_URL = os.environ.get("MFE_SMOKE_BASE_URL", "http://localhost:8080")
ORIGIN = os.environ.get("MFE_SMOKE_ORIGIN", "http://localhost:8080")
FINAL_JOB_STATUSES = {"completed", "failed", "partial", "cancelled"}


def require(response: httpx.Response, status_code: int, label: str) -> httpx.Response:
    if response.status_code != status_code:
        raise RuntimeError(f"{label}: expected HTTP {status_code}, got {response.status_code}")
    return response


def anonymous_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def run() -> None:
    host = urlsplit(ORIGIN).netloc
    with httpx.Client(
        base_url=BASE_URL,
        headers={"Host": host, "Origin": ORIGIN},
        follow_redirects=False,
        timeout=30,
    ) as client:
        require(client.get("/health/ready"), 200, "readiness")
        require(client.get("/register"), 200, "registration page")
        email = f"compose-smoke-{uuid.uuid4().hex[:12]}@example.test"
        registered = require(
            client.post(
                "/register",
                data={
                    "email": email,
                    "display_name": "Compose Smoke",
                    "password": "a sufficiently long smoke password",
                },
            ),
            303,
            "registration",
        )
        if registered.headers.get("location") != "/dashboard":
            raise RuntimeError("registration: unexpected redirect")

        course = require(
            client.post(
                "/courses",
                data={"code": f"SMOKE-{uuid.uuid4().hex[:6]}", "name": "Compose Smoke"},
            ),
            303,
            "course creation",
        )
        course_path = course.headers["location"]
        require(
            client.post(
                f"{course_path}/chapters",
                data={"number": "1", "title": "Anonymous Fixture"},
            ),
            303,
            "chapter creation",
        )
        course_page = require(client.get(course_path), 200, "course page")
        upload_match = re.search(
            r'action="(?P<path>/courses/[^\"]+/chapters/[^\"]+/documents)"',
            course_page.text,
        )
        if upload_match is None:
            raise RuntimeError("course page: upload action not found")

        uploaded = require(
            client.post(
                upload_match.group("path"),
                data={"title": "Anonymous Compose Fixture"},
                files={
                    "document": (
                        "anonymous-compose-smoke.pdf",
                        anonymous_pdf(),
                        "application/pdf",
                    )
                },
            ),
            303,
            "PDF upload",
        )
        document_path = uploaded.headers["location"]
        document_id = document_path.rsplit("/", 1)[-1]
        source = require(client.get(f"{document_path}/source.pdf"), 200, "PDF source")
        if not source.content.startswith(b"%PDF-"):
            raise RuntimeError("PDF source: invalid signature")
        rendered = require(
            client.get(f"{document_path}/pages/1.png?width=700"),
            200,
            "rendered page",
        )
        if not rendered.content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("rendered page: invalid PNG signature")

        require(client.post(f"{document_path}/analysis"), 303, "analysis start")
        reader = require(client.get(document_path), 200, "analysis reader")
        job_match = re.search(r'data-job-url="(?P<path>/api/v1/jobs/[^\"]+)"', reader.text)
        if job_match is None:
            raise RuntimeError("analysis reader: job URL not found")
        job_path = job_match.group("path")

        deadline = time.monotonic() + 90
        status = ""
        while time.monotonic() < deadline:
            payload = require(client.get(job_path), 200, "job status").json()
            status = str(payload["status"])
            if status in FINAL_JOB_STATUSES:
                break
            time.sleep(1)
        if status != "completed":
            raise RuntimeError(f"analysis job did not complete successfully: {status!r}")

        page_one = require(client.get(f"{document_path}?page=1"), 200, "page 1 reader")
        if "第 1 页匿名演示内容" not in page_one.text:
            raise RuntimeError("page 1 reader: Fake Provider output missing")
        page_two = require(client.get(f"{document_path}?page=2"), 200, "page 2 reader")
        if "Present value demo" not in page_two.text or "公式解析" not in page_two.text:
            raise RuntimeError("page 2 reader: formula output missing")

        require(
            client.post(
                f"{document_path}/notes",
                data={
                    "page_number": "1",
                    "note_type": "insight",
                    "content": "compose-smoke-duration-note",
                },
            ),
            303,
            "note creation",
        )
        search = require(
            client.get("/api/v1/search", params={"q": "duration-note"}),
            200,
            "note search",
        ).json()
        if not search["results"] or search["results"][0]["source"] != "note":
            raise RuntimeError("note search: result missing")

        csrf_token = client.cookies.get("mfe_csrf")
        progress = require(
            client.post(
                f"/api/v1/documents/{document_id}/progress",
                json={"page_number": 2, "seconds_delta": 30},
                headers={"X-CSRF-Token": csrf_token or ""},
            ),
            200,
            "reading progress",
        ).json()
        if progress["is_completed"] is not True:
            raise RuntimeError("reading progress: document was not completed")

        dashboard = require(client.get("/dashboard"), 200, "dashboard")
        for expected in ("继续阅读", "分析进度", "Anonymous Compose Fixture"):
            if expected not in dashboard.text:
                raise RuntimeError(f"dashboard: missing {expected!r}")
        manifest = require(client.get("/manifest.webmanifest"), 200, "PWA manifest").json()
        if {icon["sizes"] for icon in manifest["icons"]} != {"192x192", "512x512"}:
            raise RuntimeError("PWA manifest: icon sizes are incomplete")

        with httpx.Client(
            base_url=BASE_URL,
            headers={"Host": host, "Origin": ORIGIN},
            follow_redirects=False,
            timeout=30,
        ) as other_tenant:
            require(other_tenant.get("/register"), 200, "second tenant registration page")
            require(
                other_tenant.post(
                    "/register",
                    data={
                        "email": f"compose-isolation-{uuid.uuid4().hex[:12]}@example.test",
                        "display_name": "Isolation Smoke",
                        "password": "a different sufficiently long password",
                    },
                ),
                303,
                "second tenant registration",
            )
            require(
                other_tenant.get(f"{document_path}/source.pdf"),
                404,
                "cross-tenant PDF download",
            )
            require(other_tenant.get(job_path), 404, "cross-tenant job lookup")
            require(
                other_tenant.post(
                    f"{document_path}/notes",
                    data={
                        "page_number": "1",
                        "note_type": "insight",
                        "content": "must-not-be-created",
                    },
                ),
                404,
                "cross-tenant note creation",
            )
            other_csrf = other_tenant.cookies.get("mfe_csrf")
            require(
                other_tenant.post(
                    f"/api/v1/documents/{document_id}/progress",
                    json={"page_number": 1, "seconds_delta": 1},
                    headers={"X-CSRF-Token": other_csrf or ""},
                ),
                404,
                "cross-tenant progress update",
            )
            hidden_search = require(
                other_tenant.get("/api/v1/search", params={"q": "duration-note"}),
                200,
                "cross-tenant search",
            ).json()
            if hidden_search["results"]:
                raise RuntimeError("cross-tenant search exposed another tenant's note")

        print(
            "COMPOSE_SMOKE_OK "
            f"document={document_id} job={job_path.rsplit('/', 1)[-1]} "
            f"status={status} pages=2 isolation=verified"
        )


if __name__ == "__main__":
    run()
