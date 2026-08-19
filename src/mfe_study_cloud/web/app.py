"""Application factory for the server-rendered web UI and cookie-authenticated API."""

from __future__ import annotations

import secrets
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from mfe_study_cloud.branding import PRODUCT_NAME
from mfe_study_cloud.config import Settings, get_settings
from mfe_study_cloud.db.repositories import TenantPrincipal
from mfe_study_cloud.db.session import create_session_factory
from mfe_study_cloud.security import new_csrf_token
from mfe_study_cloud.services.auth import AuthService
from mfe_study_cloud.services.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from mfe_study_cloud.services.jobs import JobService
from mfe_study_cloud.services.study import StudyService
from mfe_study_cloud.storage import ObjectStore, S3ObjectStore
from mfe_study_cloud.web.middleware import CsrfOriginMiddleware, SecurityHeadersMiddleware

WEB_ROOT = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))


class ProgressInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1)
    seconds_delta: int = Field(default=0, ge=0, le=3600)


def create_app(
    *,
    settings: Settings | None = None,
    sessions: sessionmaker[Session] | None = None,
    object_store: ObjectStore | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    session_factory = sessions or create_session_factory(app_settings.database_url)
    objects = object_store or S3ObjectStore(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        del app
        objects.ensure_ready()
        yield

    app = FastAPI(
        title=PRODUCT_NAME,
        version="1.0.0-rc.1",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.sessions = session_factory
    app.state.objects = objects
    app.state.auth = AuthService(session_factory)
    app.state.study = StudyService(
        session_factory,
        objects,
        max_upload_bytes=app_settings.max_upload_bytes,
        max_document_pages=app_settings.analysis_max_document_pages,
    )
    app.state.jobs = JobService(session_factory, app_settings)

    app.mount("/static", StaticFiles(directory=str(WEB_ROOT / "static")), name="static")
    _add_routes(app)
    _add_exception_handlers(app)

    app.add_middleware(
        CsrfOriginMiddleware,
        expected_origin=app_settings.public_origin,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=app_settings.session_secret.get_secret_value(),
        session_cookie="mfe_session",
        max_age=7 * 24 * 60 * 60,
        same_site="lax",
        https_only=app_settings.secure_cookies,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=app_settings.allowed_host_list)
    app.add_middleware(
        SecurityHeadersMiddleware,
        production=app_settings.environment == "production",
    )
    return app


def _add_routes(app: FastAPI) -> None:
    @app.get("/health/live", name="health_live")
    async def health_live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready", name="health_ready")
    async def health_ready(request: Request) -> JSONResponse:
        try:
            with request.app.state.sessions() as session:
                session.execute(select(1)).scalar_one()
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        settings: Settings = request.app.state.settings
        return JSONResponse(
            {
                "status": "ready",
                "provider": settings.analysis_provider,
                "provider_ready": settings.provider_ready,
            }
        )

    @app.get("/manifest.webmanifest", name="manifest")
    async def manifest() -> JSONResponse:
        return JSONResponse(
            {
                "name": PRODUCT_NAME,
                "short_name": "MFE Study",
                "description": "A private, self-hosted PDF study workspace.",
                "start_url": "/",
                "scope": "/",
                "display": "standalone",
                "background_color": "#f4f0e8",
                "theme_color": "#16352d",
                "icons": [
                    {
                        "src": "/static/icon-192.png",
                        "sizes": "192x192",
                        "type": "image/png",
                    },
                    {
                        "src": "/static/icon-512.png",
                        "sizes": "512x512",
                        "type": "image/png",
                        "purpose": "any maskable",
                    },
                ],
            },
            media_type="application/manifest+json",
        )

    @app.get("/service-worker.js", name="service_worker")
    async def service_worker() -> FileResponse:
        return FileResponse(
            WEB_ROOT / "static" / "service-worker.js",
            media_type="application/javascript",
            headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
        )

    @app.get("/", name="home")
    async def home(request: Request) -> RedirectResponse:
        principal = _optional_principal(request)
        return RedirectResponse("/dashboard" if principal else "/login", status_code=303)

    @app.get("/register", response_class=HTMLResponse, name="register_form")
    async def register_form(request: Request) -> Response:
        return _render(request, "auth.html", mode="register")

    @app.post("/register", response_class=HTMLResponse, name="register")
    async def register(
        request: Request,
        email: Annotated[str, Form()],
        display_name: Annotated[str, Form()],
        password: Annotated[str, Form()],
    ) -> Response:
        try:
            principal = request.app.state.auth.register(
                email=email,
                display_name=display_name,
                password=password,
            )
        except (ValueError, ConflictError) as exc:
            return _render(
                request,
                "auth.html",
                status_code=400,
                mode="register",
                error=str(exc),
                email=email,
                display_name=display_name,
            )
        _start_session(request, principal)
        response = RedirectResponse("/dashboard", status_code=303)
        _set_csrf_cookie(request, response)
        return response

    @app.get("/login", response_class=HTMLResponse, name="login_form")
    async def login_form(request: Request) -> Response:
        return _render(request, "auth.html", mode="login")

    @app.post("/login", response_class=HTMLResponse, name="login")
    async def login(
        request: Request,
        email: Annotated[str, Form()],
        password: Annotated[str, Form()],
    ) -> Response:
        try:
            principal = request.app.state.auth.authenticate(email=email, password=password)
        except AuthenticationError as exc:
            return _render(
                request,
                "auth.html",
                status_code=400,
                mode="login",
                error=str(exc),
                email=email,
            )
        _start_session(request, principal)
        response = RedirectResponse("/dashboard", status_code=303)
        _set_csrf_cookie(request, response)
        return response

    @app.post("/logout", name="logout")
    async def logout(request: Request) -> RedirectResponse:
        request.session.clear()
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie("mfe_csrf", path="/")
        return response

    @app.get("/dashboard", response_class=HTMLResponse, name="dashboard")
    async def dashboard(
        request: Request,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
    ) -> Response:
        courses = request.app.state.study.list_courses(principal)
        return _render(request, "dashboard.html", courses=courses)

    @app.post("/courses", name="create_course")
    async def create_course(
        request: Request,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
        code: Annotated[str, Form()],
        name: Annotated[str, Form()],
        semester: Annotated[str | None, Form()] = None,
    ) -> RedirectResponse:
        course = request.app.state.study.create_course(
            principal,
            code=code,
            name=name,
            semester=semester,
        )
        return RedirectResponse(f"/courses/{course.id}", status_code=303)

    @app.get("/courses/{course_id}", response_class=HTMLResponse, name="course")
    async def course(
        request: Request,
        course_id: uuid.UUID,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
    ) -> Response:
        study = request.app.state.study
        return _render(
            request,
            "course.html",
            course=study.course(principal, course_id),
            chapters=study.chapters(principal, course_id),
            documents=study.documents(principal, course_id),
        )

    @app.post("/courses/{course_id}/chapters", name="create_chapter")
    async def create_chapter(
        request: Request,
        course_id: uuid.UUID,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
        number: Annotated[str, Form()],
        title: Annotated[str, Form()],
    ) -> RedirectResponse:
        request.app.state.study.create_chapter(
            principal,
            course_id=course_id,
            number=number,
            title=title,
        )
        return RedirectResponse(f"/courses/{course_id}", status_code=303)

    @app.post(
        "/courses/{course_id}/chapters/{chapter_id}/documents",
        name="upload_document",
    )
    async def upload_document(
        request: Request,
        course_id: uuid.UUID,
        chapter_id: uuid.UUID,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
        document: Annotated[UploadFile, File()],
        title: Annotated[str | None, Form()] = None,
    ) -> RedirectResponse:
        settings: Settings = request.app.state.settings
        raw = await document.read(settings.max_upload_bytes + 1)
        await document.close()
        stored = request.app.state.study.upload_document(
            principal,
            course_id=course_id,
            chapter_id=chapter_id,
            filename=document.filename or "document.pdf",
            data=raw,
            title=title,
        )
        return RedirectResponse(f"/documents/{stored.id}", status_code=303)

    @app.get("/documents/{document_id}", response_class=HTMLResponse, name="reader")
    async def reader(
        request: Request,
        document_id: uuid.UUID,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
        page: Annotated[int, Query(ge=1)] = 1,
    ) -> Response:
        study = request.app.state.study
        document = study.document(principal, document_id)
        selected_page = min(page, document.page_count)
        analyses = study.analyses(principal, document_id)
        analysis = next(
            (item for item in analyses if item.page_number == selected_page),
            None,
        )
        return _render(
            request,
            "reader.html",
            document=document,
            page=selected_page,
            analysis=analysis,
            analyses=analyses,
            notes=study.notes_for_document(principal, document_id),
            job=request.app.state.jobs.latest_for_document(
                principal, document_id=document_id
            ),
        )

    @app.get("/documents/{document_id}/source.pdf", name="document_source")
    async def document_source(
        request: Request,
        document_id: uuid.UUID,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
    ) -> Response:
        study = request.app.state.study
        document = study.document(principal, document_id)
        data = study.document_bytes(principal, document_id)
        encoded = quote(document.original_filename, safe="")
        return Response(
            data,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded}"},
        )

    @app.get("/documents/{document_id}/pages/{page_number}.png", name="document_page")
    async def document_page(
        request: Request,
        document_id: uuid.UUID,
        page_number: int,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
        width: Annotated[int, Query(ge=320, le=4000)] = 1200,
    ) -> Response:
        data = request.app.state.study.rendered_page(
            principal,
            document_id=document_id,
            page_number=page_number,
            width=width,
        )
        return Response(data, media_type="image/png")

    @app.post("/documents/{document_id}/analysis", name="start_analysis")
    async def start_analysis(
        request: Request,
        document_id: uuid.UUID,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
    ) -> RedirectResponse:
        request.app.state.jobs.start(principal, document_id=document_id)
        return RedirectResponse(f"/documents/{document_id}", status_code=303)

    @app.post("/jobs/{job_id}/cancel", name="cancel_job")
    async def cancel_job(
        request: Request,
        job_id: uuid.UUID,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
    ) -> RedirectResponse:
        job = request.app.state.jobs.cancel(principal, job_id=job_id)
        return RedirectResponse(f"/documents/{job.document_id}", status_code=303)

    @app.post("/jobs/{job_id}/retry", name="retry_job")
    async def retry_job(
        request: Request,
        job_id: uuid.UUID,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
    ) -> RedirectResponse:
        job = request.app.state.jobs.retry(principal, job_id=job_id)
        return RedirectResponse(f"/documents/{job.document_id}", status_code=303)

    @app.post("/documents/{document_id}/notes", name="add_note")
    async def add_note(
        request: Request,
        document_id: uuid.UUID,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
        content: Annotated[str, Form()],
        page_number: Annotated[int, Form()],
        note_type: Annotated[str, Form()] = "note",
    ) -> RedirectResponse:
        document = request.app.state.study.document(principal, document_id)
        request.app.state.study.add_note(
            principal,
            course_id=document.course_id,
            chapter_id=document.chapter_id,
            document_id=document_id,
            page_number=page_number,
            note_type=note_type,
            content=content,
        )
        return RedirectResponse(
            f"/documents/{document_id}?page={page_number}", status_code=303
        )

    @app.get("/search", response_class=HTMLResponse, name="search")
    async def search(
        request: Request,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
        q: str = "",
    ) -> Response:
        return _render(
            request,
            "search.html",
            query=q,
            hits=request.app.state.study.search(principal, q),
        )

    @app.get("/api/v1/jobs/{job_id}", name="api_job")
    async def api_job(
        request: Request,
        job_id: uuid.UUID,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
    ) -> dict[str, Any]:
        return _job_payload(request.app.state.jobs.status(principal, job_id=job_id))

    @app.get("/api/v1/search", name="api_search")
    async def api_search(
        request: Request,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
        q: Annotated[str, Query(min_length=1, max_length=500)],
    ) -> dict[str, Any]:
        hits = request.app.state.study.search(principal, q)
        return {
            "results": [
                {
                    "source": hit.source,
                    "record_id": str(hit.record_id),
                    "document_id": str(hit.document_id) if hit.document_id else None,
                    "page_number": hit.page_number,
                    "text": hit.text,
                }
                for hit in hits
            ]
        }

    @app.post("/api/v1/documents/{document_id}/progress", name="api_progress")
    async def api_progress(
        request: Request,
        document_id: uuid.UUID,
        payload: ProgressInput,
        principal: Annotated[TenantPrincipal, Depends(_principal)],
    ) -> dict[str, Any]:
        progress = request.app.state.study.update_progress(
            principal,
            document_id=document_id,
            page_number=payload.page_number,
            seconds_delta=payload.seconds_delta,
        )
        return {
            "document_id": str(progress.document_id),
            "last_page": progress.last_page,
            "furthest_page": progress.furthest_page,
            "is_completed": progress.is_completed,
        }


def _add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError) -> Response:
        if isinstance(exc, NotFoundError):
            status_code = 404
        elif isinstance(exc, ConflictError):
            status_code = 409
        elif isinstance(exc, (ValidationError, AuthenticationError)):
            status_code = 400
        else:
            status_code = 400
        if request.url.path.startswith("/api/"):
            return JSONResponse({"error": str(exc)}, status_code=status_code)
        return _render(
            request,
            "error.html",
            status_code=status_code,
            error=str(exc),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> Response:
        del exc
        if request.url.path.startswith("/api/"):
            return JSONResponse({"error": "Request validation failed."}, status_code=422)
        return _render(
            request,
            "error.html",
            status_code=422,
            error="Request validation failed.",
        )


def _principal(request: Request) -> TenantPrincipal:
    principal = _optional_principal(request)
    if principal is None:
        status_code = 401 if request.url.path.startswith("/api/") else 303
        headers = None if status_code == 401 else {"Location": "/login"}
        raise HTTPException(
            status_code=status_code,
            detail="Authentication required.",
            headers=headers,
        )
    return principal


def _optional_principal(request: Request) -> TenantPrincipal | None:
    try:
        user_id = uuid.UUID(str(request.session.get("user_id", "")))
        tenant_id = uuid.UUID(str(request.session.get("tenant_id", "")))
    except ValueError:
        return None
    auth: AuthService = request.app.state.auth
    principal = auth.resolve_principal(user_id=user_id, tenant_id=tenant_id)
    if principal is None:
        request.session.clear()
    return principal


def _start_session(request: Request, principal: TenantPrincipal) -> None:
    request.session.clear()
    request.session.update(
        {
            "user_id": str(principal.user_id),
            "tenant_id": str(principal.tenant_id),
            "csrf": new_csrf_token(),
        }
    )


def _render(
    request: Request,
    template_name: str,
    *,
    status_code: int = 200,
    **context: Any,
) -> Response:
    if not request.session.get("csrf"):
        request.session["csrf"] = new_csrf_token()
    response = templates.TemplateResponse(
        request=request,
        name=template_name,
        context={
            "product_name": PRODUCT_NAME,
            "principal": _optional_principal(request),
            **context,
        },
        status_code=status_code,
    )
    _set_csrf_cookie(request, response)
    return response


def _set_csrf_cookie(request: Request, response: Response) -> None:
    settings: Settings = request.app.state.settings
    token = str(request.session.get("csrf") or secrets.token_urlsafe(32))
    request.session["csrf"] = token
    response.set_cookie(
        "mfe_csrf",
        token,
        max_age=7 * 24 * 60 * 60,
        secure=settings.secure_cookies,
        httponly=False,
        samesite="strict",
        path="/",
    )


def _job_payload(job: Any) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "document_id": str(job.document_id),
        "status": job.status,
        "provider": job.provider,
        "model": job.model,
        "total_pages": job.total_pages,
        "completed_pages": job.completed_pages,
        "failed_pages": job.failed_pages,
        "attempt_count": job.attempt_count,
        "cancel_requested": job.cancel_requested,
        "error_summary": job.error_summary,
    }
