"""Authoritative multi-tenant PostgreSQL data model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mfe_study_cloud.db.base import Base, TimestampMixin


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    memberships: Mapped[list[Membership]] = relationship(back_populates="tenant")

    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended')", name="tenant_status"),
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    memberships: Mapped[list[Membership]] = relationship(back_populates="user")


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), default="owner", nullable=False)

    user: Mapped[User] = relationship(back_populates="memberships")
    tenant: Mapped[Tenant] = relationship(back_populates="memberships")

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'member')", name="membership_role"),
        Index("ix_memberships_tenant_user", "tenant_id", "user_id"),
    )


class Course(TimestampMixin, Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    semester: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    chapters: Mapped[list[Chapter]] = relationship(back_populates="course")
    documents: Mapped[list[Document]] = relationship(back_populates="course")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_courses_tenant_code"),
        CheckConstraint("status IN ('active', 'archived')", name="course_status"),
        Index("ix_courses_tenant_updated", "tenant_id", "updated_at"),
    )


class Chapter(TimestampMixin, Base):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    course: Mapped[Course] = relationship(back_populates="chapters")
    documents: Mapped[list[Document]] = relationship(back_populates="chapter")

    __table_args__ = (
        UniqueConstraint("tenant_id", "course_id", "number", name="uq_chapter_scope_number"),
        Index("ix_chapters_tenant_course", "tenant_id", "course_id", "sort_order"),
    )


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), default="application/pdf")
    status: Mapped[str] = mapped_column(String(30), default="registered", nullable=False)

    course: Mapped[Course] = relationship(back_populates="documents")
    chapter: Mapped[Chapter] = relationship(back_populates="documents")
    analyses: Mapped[list[PageAnalysis]] = relationship(back_populates="document")
    jobs: Mapped[list[AnalysisJob]] = relationship(back_populates="document")

    __table_args__ = (
        UniqueConstraint("tenant_id", "sha256", name="uq_documents_tenant_sha256"),
        CheckConstraint("size_bytes >= 0", name="document_size"),
        CheckConstraint("page_count > 0", name="document_pages"),
        CheckConstraint(
            "status IN ('registered', 'queued', 'processing', 'partial', 'complete', 'error')",
            name="document_status",
        ),
        Index("ix_documents_tenant_course", "tenant_id", "course_id", "chapter_id"),
    )


class AnalysisJob(TimestampMixin, Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    total_pages: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_pages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_pages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_page: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(String(2000))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document: Mapped[Document] = relationship(back_populates="jobs")

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_analysis_jobs_tenant_idempotency"
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'partial', 'completed', 'failed', 'cancelled')",
            name="analysis_job_status",
        ),
        CheckConstraint("total_pages > 0", name="analysis_total_pages"),
        CheckConstraint("completed_pages >= 0", name="analysis_completed_pages"),
        CheckConstraint("failed_pages >= 0", name="analysis_failed_pages"),
        Index("ix_analysis_jobs_claim", "status", "lease_expires_at", "created_at"),
        Index("ix_analysis_jobs_tenant_document", "tenant_id", "document_id", "created_at"),
    )


class PageAnalysis(TimestampMixin, Base):
    __tablename__ = "page_analyses"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="SET NULL")
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    searchable_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    response_id: Mapped[str | None] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    document: Mapped[Document] = relationship(back_populates="analyses")

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "document_id", "page_number", "version", name="uq_page_analysis_version"
        ),
        CheckConstraint("page_number > 0", name="page_analysis_page"),
        CheckConstraint("version > 0", name="page_analysis_version"),
        Index(
            "uq_page_analysis_active",
            "tenant_id",
            "document_id",
            "page_number",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
        Index("ix_page_analyses_tenant_search", "tenant_id", "document_id", "page_number"),
    )


class Note(TimestampMixin, Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL")
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    page_number: Mapped[int | None] = mapped_column(Integer)
    note_type: Mapped[str] = mapped_column(String(20), default="note", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "note_type IN ('note', 'question', 'insight', 'exam_focus')",
            name="note_type",
        ),
        CheckConstraint("page_number IS NULL OR page_number > 0", name="note_page"),
        Index("ix_notes_tenant_scope", "tenant_id", "course_id", "document_id", "page_number"),
    )


class ReadingProgress(TimestampMixin, Base):
    __tablename__ = "reading_progress"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    last_page: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    furthest_page: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    viewed_pages: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    total_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("last_page > 0", name="reading_last_page"),
        CheckConstraint("furthest_page > 0", name="reading_furthest_page"),
        CheckConstraint("total_seconds >= 0", name="reading_total_seconds"),
        Index("ix_reading_progress_recent", "tenant_id", "user_id", "last_read_at"),
    )
