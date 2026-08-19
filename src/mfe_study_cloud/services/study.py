"""Tenant-scoped course, document, note, search, and progress use cases."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from io import BytesIO

import pypdfium2 as pdfium
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from mfe_study_cloud.analysis.pdf_batches import validate_pdf
from mfe_study_cloud.db.models import (
    Chapter,
    Course,
    Document,
    Note,
    PageAnalysis,
    ReadingProgress,
)
from mfe_study_cloud.db.repositories import (
    RecentReading,
    SearchHit,
    StudyRepository,
    TenantPrincipal,
)
from mfe_study_cloud.db.session import session_scope
from mfe_study_cloud.services.errors import ConflictError, NotFoundError, ValidationError
from mfe_study_cloud.storage import (
    ObjectStore,
    document_object_key,
    rendered_page_object_key,
)

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_NOTE_TYPES = {"note", "question", "insight", "exam_focus"}


def safe_filename(value: str) -> str:
    basename = value.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = _CONTROL_CHARACTERS.sub("", basename).strip().strip(".")
    if not cleaned:
        cleaned = "document.pdf"
    return cleaned[:500]


def _bounded_text(value: str, *, field: str, maximum: int) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum:
        raise ValidationError(f"{field} must be 1 to {maximum} characters.")
    return cleaned


class StudyService:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        object_store: ObjectStore,
        *,
        max_upload_bytes: int,
        max_document_pages: int,
    ) -> None:
        self._sessions = sessions
        self._objects = object_store
        self._max_upload_bytes = max_upload_bytes
        self._max_document_pages = max_document_pages

    def create_course(
        self,
        principal: TenantPrincipal,
        *,
        code: str,
        name: str,
        semester: str | None = None,
        description: str | None = None,
    ) -> Course:
        clean_code = _bounded_text(code, field="Course code", maximum=32)
        clean_name = _bounded_text(name, field="Course name", maximum=300)
        clean_semester = semester.strip()[:100] if semester and semester.strip() else None
        clean_description = description.strip() if description and description.strip() else None
        try:
            with session_scope(self._sessions) as session:
                return StudyRepository(session, principal.tenant_id).add_course(
                    course_id=uuid.uuid4(),
                    code=clean_code,
                    name=clean_name,
                    semester=clean_semester,
                    description=clean_description,
                )
        except IntegrityError as exc:
            raise ConflictError("A course with this code already exists.") from exc

    def list_courses(self, principal: TenantPrincipal) -> list[Course]:
        with self._sessions() as session:
            return StudyRepository(session, principal.tenant_id).courses()

    def recent_reading(self, principal: TenantPrincipal) -> list[RecentReading]:
        with self._sessions() as session:
            return StudyRepository(session, principal.tenant_id).recent_reading(
                user_id=principal.user_id
            )

    def course(self, principal: TenantPrincipal, course_id: uuid.UUID) -> Course:
        with self._sessions() as session:
            course = StudyRepository(session, principal.tenant_id).course(course_id)
            if course is None:
                raise NotFoundError("Course was not found.")
            return course

    def chapters(self, principal: TenantPrincipal, course_id: uuid.UUID) -> list[Chapter]:
        with self._sessions() as session:
            repository = StudyRepository(session, principal.tenant_id)
            if repository.course(course_id) is None:
                raise NotFoundError("Course was not found.")
            return repository.chapters(course_id)

    def documents(self, principal: TenantPrincipal, course_id: uuid.UUID) -> list[Document]:
        with self._sessions() as session:
            repository = StudyRepository(session, principal.tenant_id)
            if repository.course(course_id) is None:
                raise NotFoundError("Course was not found.")
            return repository.documents(course_id)

    def create_chapter(
        self,
        principal: TenantPrincipal,
        *,
        course_id: uuid.UUID,
        number: str,
        title: str,
        description: str | None = None,
        sort_order: int = 0,
    ) -> Chapter:
        clean_number = _bounded_text(number, field="Chapter number", maximum=32)
        clean_title = _bounded_text(title, field="Chapter title", maximum=300)
        clean_description = description.strip() if description and description.strip() else None
        try:
            with session_scope(self._sessions) as session:
                repository = StudyRepository(session, principal.tenant_id)
                if repository.course(course_id) is None:
                    raise NotFoundError("Course was not found.")
                return repository.add_chapter(
                    chapter_id=uuid.uuid4(),
                    course_id=course_id,
                    number=clean_number,
                    title=clean_title,
                    description=clean_description,
                    sort_order=max(0, sort_order),
                )
        except IntegrityError as exc:
            raise ConflictError("A chapter with this number already exists.") from exc

    def upload_document(
        self,
        principal: TenantPrincipal,
        *,
        course_id: uuid.UUID,
        chapter_id: uuid.UUID,
        filename: str,
        data: bytes,
        title: str | None = None,
    ) -> Document:
        try:
            page_count = validate_pdf(
                data,
                max_bytes=self._max_upload_bytes,
                max_pages=self._max_document_pages,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        digest = hashlib.sha256(data).hexdigest()
        document_id = uuid.uuid4()
        object_key = document_object_key(principal.tenant_id, document_id)
        display_filename = safe_filename(filename)
        display_title = title.strip()[:500] if title and title.strip() else display_filename
        stored = False
        try:
            with session_scope(self._sessions) as session:
                repository = StudyRepository(session, principal.tenant_id)
                if repository.course(course_id) is None:
                    raise NotFoundError("Course was not found.")
                if repository.chapter(chapter_id, course_id=course_id) is None:
                    raise NotFoundError("Chapter was not found in this course.")
                if repository.document_by_hash(digest) is not None:
                    raise ConflictError("This PDF is already registered in the workspace.")
                self._objects.put(object_key, data, content_type="application/pdf")
                stored = True
                return repository.add_document(
                    document_id=document_id,
                    course_id=course_id,
                    chapter_id=chapter_id,
                    title=display_title,
                    original_filename=display_filename,
                    object_key=object_key,
                    sha256=digest,
                    size_bytes=len(data),
                    page_count=page_count,
                )
        except IntegrityError as exc:
            if stored:
                self._objects.delete(object_key)
            raise ConflictError("This PDF is already registered in the workspace.") from exc
        except Exception:
            if stored:
                self._objects.delete(object_key)
            raise

    def document_bytes(self, principal: TenantPrincipal, document_id: uuid.UUID) -> bytes:
        with self._sessions() as session:
            document = StudyRepository(session, principal.tenant_id).document(document_id)
            if document is None:
                raise NotFoundError("Document was not found.")
            object_key = document.object_key
        return self._objects.get(object_key)

    def document(self, principal: TenantPrincipal, document_id: uuid.UUID) -> Document:
        with self._sessions() as session:
            document = StudyRepository(session, principal.tenant_id).document(document_id)
            if document is None:
                raise NotFoundError("Document was not found.")
            return document

    def analyses(self, principal: TenantPrincipal, document_id: uuid.UUID) -> list[PageAnalysis]:
        with self._sessions() as session:
            repository = StudyRepository(session, principal.tenant_id)
            if repository.document(document_id) is None:
                raise NotFoundError("Document was not found.")
            return repository.analyses(document_id)

    def notes_for_document(
        self, principal: TenantPrincipal, document_id: uuid.UUID
    ) -> list[Note]:
        with self._sessions() as session:
            repository = StudyRepository(session, principal.tenant_id)
            if repository.document(document_id) is None:
                raise NotFoundError("Document was not found.")
            return repository.document_notes(
                document_id=document_id,
                user_id=principal.user_id,
            )

    def rendered_page(
        self,
        principal: TenantPrincipal,
        *,
        document_id: uuid.UUID,
        page_number: int,
        width: int,
    ) -> bytes:
        document = self.document(principal, document_id)
        if not 1 <= page_number <= document.page_count:
            raise NotFoundError("Document page was not found.")
        bounded_width = max(640, min(width, 2000))
        cache_key = rendered_page_object_key(
            principal.tenant_id,
            document_id,
            page_number,
            bounded_width,
        )
        try:
            return self._objects.get(cache_key)
        except FileNotFoundError:
            pass
        source = self._objects.get(document.object_key)
        pdf = pdfium.PdfDocument(source)
        page = pdf.get_page(page_number - 1)
        bitmap = None
        try:
            page_width, _ = page.get_size()
            scale = bounded_width / page_width
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil()
            output = BytesIO()
            image.save(output, format="PNG", optimize=True)
            rendered = output.getvalue()
        finally:
            if bitmap is not None:
                bitmap.close()
            page.close()
            pdf.close()
        self._objects.put(cache_key, rendered, content_type="image/png")
        return rendered

    def add_note(
        self,
        principal: TenantPrincipal,
        *,
        course_id: uuid.UUID,
        content: str,
        note_type: str = "note",
        chapter_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
        page_number: int | None = None,
    ) -> Note:
        clean_content = _bounded_text(content, field="Note", maximum=20_000)
        if note_type not in _NOTE_TYPES:
            raise ValidationError("Unknown note type.")
        if page_number is not None and page_number < 1:
            raise ValidationError("Page number must be positive.")
        with session_scope(self._sessions) as session:
            repository = StudyRepository(session, principal.tenant_id)
            if repository.course(course_id) is None:
                raise NotFoundError("Course was not found.")
            if (
                chapter_id is not None
                and repository.chapter(chapter_id, course_id=course_id) is None
            ):
                raise NotFoundError("Chapter was not found in this course.")
            if document_id is not None:
                document = repository.document(document_id)
                if document is None or document.course_id != course_id:
                    raise NotFoundError("Document was not found in this course.")
                if page_number is not None and page_number > document.page_count:
                    raise ValidationError("Page number exceeds the document length.")
            return repository.add_note(
                note_id=uuid.uuid4(),
                user_id=principal.user_id,
                course_id=course_id,
                chapter_id=chapter_id,
                document_id=document_id,
                page_number=page_number,
                note_type=note_type,
                content=clean_content,
            )

    def search(self, principal: TenantPrincipal, query: str, *, limit: int = 50) -> list[SearchHit]:
        cleaned = query.strip()
        if not cleaned:
            return []
        with self._sessions() as session:
            return StudyRepository(session, principal.tenant_id).search(
                cleaned, limit=max(1, min(limit, 100))
            )

    def update_progress(
        self,
        principal: TenantPrincipal,
        *,
        document_id: uuid.UUID,
        page_number: int,
        seconds_delta: int = 0,
    ) -> ReadingProgress:
        with session_scope(self._sessions) as session:
            repository = StudyRepository(session, principal.tenant_id)
            document = repository.document(document_id)
            if document is None:
                raise NotFoundError("Document was not found.")
            if not 1 <= page_number <= document.page_count:
                raise ValidationError("Page number is outside the document.")
            progress = repository.progress(
                user_id=principal.user_id,
                document_id=document_id,
            )
            if progress is None:
                progress = ReadingProgress(
                    tenant_id=principal.tenant_id,
                    user_id=principal.user_id,
                    document_id=document_id,
                    last_page=1,
                    furthest_page=1,
                    viewed_pages=[],
                    total_seconds=0,
                    is_completed=False,
                )
                session.add(progress)
            progress.last_page = page_number
            progress.furthest_page = max(progress.furthest_page, page_number)
            progress.viewed_pages = sorted({*progress.viewed_pages, page_number})
            progress.total_seconds += max(0, min(seconds_delta, 3600))
            progress.is_completed = progress.furthest_page >= document.page_count
            progress.last_read_at = datetime.now(UTC)
            session.flush()
            return progress
