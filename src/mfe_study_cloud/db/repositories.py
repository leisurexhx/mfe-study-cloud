"""Tenant-scoped database access.

Business records are never loaded by identifier alone. Callers must provide the
authenticated tenant for every query, which keeps the ownership check at the data
access boundary instead of relying on route handlers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from mfe_study_cloud.db.models import (
    Chapter,
    Course,
    Document,
    Membership,
    Note,
    PageAnalysis,
    ReadingProgress,
    Tenant,
    User,
)


@dataclass(frozen=True, slots=True)
class TenantPrincipal:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


@dataclass(frozen=True, slots=True)
class SearchHit:
    source: str
    record_id: uuid.UUID
    document_id: uuid.UUID | None
    page_number: int | None
    text: str


@dataclass(frozen=True, slots=True)
class RecentReading:
    document_id: uuid.UUID
    document_title: str
    course_name: str
    last_page: int
    page_count: int


class AuthRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def user_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email))

    def principal(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> TenantPrincipal | None:
        row = self._session.execute(
            select(Membership.user_id, Membership.tenant_id, Membership.role)
            .join(User, User.id == Membership.user_id)
            .join(Tenant, Tenant.id == Membership.tenant_id)
            .where(
                Membership.user_id == user_id,
                Membership.tenant_id == tenant_id,
                User.is_active.is_(True),
                Tenant.status == "active",
            )
        ).one_or_none()
        if row is None:
            return None
        return TenantPrincipal(user_id=row.user_id, tenant_id=row.tenant_id, role=row.role)

    def first_principal(self, user_id: uuid.UUID) -> TenantPrincipal | None:
        row = self._session.execute(
            select(Membership.user_id, Membership.tenant_id, Membership.role)
            .join(User, User.id == Membership.user_id)
            .join(Tenant, Tenant.id == Membership.tenant_id)
            .where(Membership.user_id == user_id)
            .where(User.is_active.is_(True), Tenant.status == "active")
            .order_by(Membership.created_at, Membership.tenant_id)
            .limit(1)
        ).one_or_none()
        if row is None:
            return None
        return TenantPrincipal(user_id=row.user_id, tenant_id=row.tenant_id, role=row.role)

    def add_personal_account(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        email: str,
        display_name: str,
        password_hash: str,
        tenant_slug: str,
    ) -> TenantPrincipal:
        self._session.add(
            User(
                id=user_id,
                email=email,
                display_name=display_name,
                password_hash=password_hash,
            )
        )
        self._session.add(
            Tenant(id=tenant_id, slug=tenant_slug, name=f"{display_name}'s workspace")
        )
        self._session.add(Membership(user_id=user_id, tenant_id=tenant_id, role="owner"))
        self._session.flush()
        return TenantPrincipal(user_id=user_id, tenant_id=tenant_id, role="owner")


class StudyRepository:
    def __init__(self, session: Session, tenant_id: uuid.UUID) -> None:
        self._session = session
        self.tenant_id = tenant_id

    def _courses(self) -> Select[tuple[Course]]:
        return select(Course).where(Course.tenant_id == self.tenant_id)

    def course(self, course_id: uuid.UUID) -> Course | None:
        return self._session.scalar(self._courses().where(Course.id == course_id))

    def courses(self) -> list[Course]:
        return list(
            self._session.scalars(self._courses().order_by(Course.updated_at.desc(), Course.id))
        )

    def add_course(
        self,
        *,
        course_id: uuid.UUID,
        code: str,
        name: str,
        semester: str | None,
        description: str | None,
    ) -> Course:
        course = Course(
            id=course_id,
            tenant_id=self.tenant_id,
            code=code,
            name=name,
            semester=semester,
            description=description,
        )
        self._session.add(course)
        self._session.flush()
        return course

    def chapter(
        self, chapter_id: uuid.UUID, *, course_id: uuid.UUID | None = None
    ) -> Chapter | None:
        query = select(Chapter).where(
            Chapter.tenant_id == self.tenant_id,
            Chapter.id == chapter_id,
        )
        if course_id is not None:
            query = query.where(Chapter.course_id == course_id)
        return self._session.scalar(query)

    def chapters(self, course_id: uuid.UUID) -> list[Chapter]:
        return list(
            self._session.scalars(
                select(Chapter)
                .where(
                    Chapter.tenant_id == self.tenant_id,
                    Chapter.course_id == course_id,
                )
                .order_by(Chapter.sort_order, Chapter.number, Chapter.id)
            )
        )

    def add_chapter(
        self,
        *,
        chapter_id: uuid.UUID,
        course_id: uuid.UUID,
        number: str,
        title: str,
        description: str | None,
        sort_order: int,
    ) -> Chapter:
        chapter = Chapter(
            id=chapter_id,
            tenant_id=self.tenant_id,
            course_id=course_id,
            number=number,
            title=title,
            description=description,
            sort_order=sort_order,
        )
        self._session.add(chapter)
        self._session.flush()
        return chapter

    def document(self, document_id: uuid.UUID) -> Document | None:
        return self._session.scalar(
            select(Document).where(
                Document.tenant_id == self.tenant_id,
                Document.id == document_id,
            )
        )

    def document_by_hash(self, sha256: str) -> Document | None:
        return self._session.scalar(
            select(Document).where(
                Document.tenant_id == self.tenant_id,
                Document.sha256 == sha256,
            )
        )

    def documents(self, course_id: uuid.UUID) -> list[Document]:
        return list(
            self._session.scalars(
                select(Document)
                .where(
                    Document.tenant_id == self.tenant_id,
                    Document.course_id == course_id,
                )
                .order_by(Document.updated_at.desc(), Document.id)
            )
        )

    def analyses(self, document_id: uuid.UUID) -> list[PageAnalysis]:
        return list(
            self._session.scalars(
                select(PageAnalysis)
                .where(
                    PageAnalysis.tenant_id == self.tenant_id,
                    PageAnalysis.document_id == document_id,
                    PageAnalysis.is_active.is_(True),
                )
                .order_by(PageAnalysis.page_number)
            )
        )

    def add_document(
        self,
        *,
        document_id: uuid.UUID,
        course_id: uuid.UUID,
        chapter_id: uuid.UUID,
        title: str,
        original_filename: str,
        object_key: str,
        sha256: str,
        size_bytes: int,
        page_count: int,
    ) -> Document:
        document = Document(
            id=document_id,
            tenant_id=self.tenant_id,
            course_id=course_id,
            chapter_id=chapter_id,
            title=title,
            original_filename=original_filename,
            object_key=object_key,
            sha256=sha256,
            size_bytes=size_bytes,
            page_count=page_count,
        )
        self._session.add(document)
        self._session.flush()
        return document

    def add_note(
        self,
        *,
        note_id: uuid.UUID,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        chapter_id: uuid.UUID | None,
        document_id: uuid.UUID | None,
        page_number: int | None,
        note_type: str,
        content: str,
    ) -> Note:
        note = Note(
            id=note_id,
            tenant_id=self.tenant_id,
            user_id=user_id,
            course_id=course_id,
            chapter_id=chapter_id,
            document_id=document_id,
            page_number=page_number,
            note_type=note_type,
            content=content,
        )
        self._session.add(note)
        self._session.flush()
        return note

    def notes(self, *, course_id: uuid.UUID, user_id: uuid.UUID) -> list[Note]:
        return list(
            self._session.scalars(
                select(Note)
                .where(
                    Note.tenant_id == self.tenant_id,
                    Note.course_id == course_id,
                    Note.user_id == user_id,
                )
                .order_by(Note.updated_at.desc(), Note.id)
            )
        )

    def document_notes(self, *, document_id: uuid.UUID, user_id: uuid.UUID) -> list[Note]:
        return list(
            self._session.scalars(
                select(Note)
                .where(
                    Note.tenant_id == self.tenant_id,
                    Note.document_id == document_id,
                    Note.user_id == user_id,
                )
                .order_by(Note.page_number, Note.updated_at.desc(), Note.id)
            )
        )

    def progress(self, *, user_id: uuid.UUID, document_id: uuid.UUID) -> ReadingProgress | None:
        return self._session.scalar(
            select(ReadingProgress).where(
                ReadingProgress.tenant_id == self.tenant_id,
                ReadingProgress.user_id == user_id,
                ReadingProgress.document_id == document_id,
            )
        )

    def recent_reading(self, *, user_id: uuid.UUID, limit: int = 6) -> list[RecentReading]:
        rows = self._session.execute(
            select(
                ReadingProgress.document_id,
                Document.title,
                Course.name,
                ReadingProgress.last_page,
                Document.page_count,
            )
            .join(
                Document,
                (Document.id == ReadingProgress.document_id)
                & (Document.tenant_id == ReadingProgress.tenant_id),
            )
            .join(
                Course,
                (Course.id == Document.course_id)
                & (Course.tenant_id == Document.tenant_id),
            )
            .where(
                ReadingProgress.tenant_id == self.tenant_id,
                ReadingProgress.user_id == user_id,
            )
            .order_by(
                ReadingProgress.last_read_at.desc(),
                ReadingProgress.document_id,
            )
            .limit(max(1, min(limit, 20)))
        )
        return [
            RecentReading(
                document_id=row.document_id,
                document_title=row.title,
                course_name=row.name,
                last_page=row.last_page,
                page_count=row.page_count,
            )
            for row in rows
        ]

    def search(self, query: str, *, limit: int = 50) -> list[SearchHit]:
        pattern = f"%{query}%"
        analyses = self._session.scalars(
            select(PageAnalysis)
            .where(
                PageAnalysis.tenant_id == self.tenant_id,
                PageAnalysis.is_active.is_(True),
                PageAnalysis.searchable_text.ilike(pattern),
            )
            .order_by(PageAnalysis.updated_at.desc())
            .limit(limit)
        )
        hits = [
            SearchHit(
                source="analysis",
                record_id=item.id,
                document_id=item.document_id,
                page_number=item.page_number,
                text=item.searchable_text[:500],
            )
            for item in analyses
        ]
        if len(hits) >= limit:
            return hits
        notes = self._session.scalars(
            select(Note)
            .where(
                Note.tenant_id == self.tenant_id,
                Note.content.ilike(pattern),
            )
            .order_by(Note.updated_at.desc())
            .limit(limit - len(hits))
        )
        hits.extend(
            SearchHit(
                source="note",
                record_id=item.id,
                document_id=item.document_id,
                page_number=item.page_number,
                text=item.content[:500],
            )
            for item in notes
        )
        return hits

    def count_documents(self) -> int:
        return int(
            self._session.scalar(
                select(func.count(Document.id)).where(Document.tenant_id == self.tenant_id)
            )
            or 0
        )

    def find_text(self, query: str, *, limit: int = 50) -> list[PageAnalysis]:
        """PostgreSQL-ready search hook with a bounded CJK-friendly fallback."""
        words = [word for word in query.strip().split() if word]
        if not words:
            return []
        conditions = [PageAnalysis.searchable_text.ilike(f"%{word}%") for word in words]
        return list(
            self._session.scalars(
                select(PageAnalysis)
                .where(
                    PageAnalysis.tenant_id == self.tenant_id,
                    PageAnalysis.is_active.is_(True),
                    or_(*conditions),
                )
                .order_by(PageAnalysis.updated_at.desc())
                .limit(max(1, min(limit, 100)))
            )
        )
