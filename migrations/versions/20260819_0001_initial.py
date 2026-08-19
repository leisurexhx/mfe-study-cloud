"""Create the initial tenant-scoped schema.

Revision ID: 20260819_0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('active', 'suspended')", name=op.f("ck_tenants_tenant_status")
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "memberships",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name=op.f("ck_memberships_membership_role"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_memberships_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_memberships_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "tenant_id", name="pk_memberships"),
    )
    op.create_index("ix_memberships_tenant_user", "memberships", ["tenant_id", "user_id"])
    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("semester", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name=op.f("ck_courses_course_status")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_courses_tenant_id_tenants", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_courses"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_courses_tenant_code"),
    )
    op.create_index("ix_courses_tenant_updated", "courses", ["tenant_id", "updated_at"])
    op.create_table(
        "chapters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name="fk_chapters_course_id_courses", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_chapters_tenant_id_tenants", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chapters"),
        sa.UniqueConstraint("tenant_id", "course_id", "number", name="uq_chapter_scope_number"),
    )
    op.create_index(
        "ix_chapters_tenant_course",
        "chapters",
        ["tenant_id", "course_id", "sort_order"],
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("object_key", sa.String(length=1000), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        *timestamps(),
        sa.CheckConstraint("page_count > 0", name=op.f("ck_documents_document_pages")),
        sa.CheckConstraint("size_bytes >= 0", name=op.f("ck_documents_document_size")),
        sa.CheckConstraint(
            "status IN ('registered', 'queued', 'processing', 'partial', 'complete', 'error')",
            name=op.f("ck_documents_document_status"),
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_documents_chapter_id_chapters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name="fk_documents_course_id_courses", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_documents_tenant_id_tenants", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint("object_key", name="uq_documents_object_key"),
        sa.UniqueConstraint("tenant_id", "sha256", name="uq_documents_tenant_sha256"),
    )
    op.create_index(
        "ix_documents_tenant_course",
        "documents",
        ["tenant_id", "course_id", "chapter_id"],
    )
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("total_pages", sa.Integer(), nullable=False),
        sa.Column("completed_pages", sa.Integer(), nullable=False),
        sa.Column("failed_pages", sa.Integer(), nullable=False),
        sa.Column("next_page", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(length=100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False),
        sa.Column("error_summary", sa.String(length=2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.CheckConstraint(
            "completed_pages >= 0",
            name=op.f("ck_analysis_jobs_analysis_completed_pages"),
        ),
        sa.CheckConstraint(
            "failed_pages >= 0", name=op.f("ck_analysis_jobs_analysis_failed_pages")
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'partial', 'completed', 'failed', 'cancelled')",
            name=op.f("ck_analysis_jobs_analysis_job_status"),
        ),
        sa.CheckConstraint("total_pages > 0", name=op.f("ck_analysis_jobs_analysis_total_pages")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_analysis_jobs_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_analysis_jobs_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_analysis_jobs"),
    )
    op.create_index(
        "ix_analysis_jobs_claim",
        "analysis_jobs",
        ["status", "lease_expires_at", "created_at"],
    )
    op.create_index(
        "ix_analysis_jobs_tenant_document",
        "analysis_jobs",
        ["tenant_id", "document_id", "created_at"],
    )
    op.create_table(
        "page_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("searchable_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("response_id", sa.String(length=200), nullable=True),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        *timestamps(),
        sa.CheckConstraint("page_number > 0", name=op.f("ck_page_analyses_page_analysis_page")),
        sa.CheckConstraint("version > 0", name=op.f("ck_page_analyses_page_analysis_version")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_page_analyses_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["analysis_jobs.id"],
            name="fk_page_analyses_job_id_analysis_jobs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_page_analyses_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_page_analyses"),
        sa.UniqueConstraint(
            "tenant_id",
            "document_id",
            "page_number",
            "version",
            name="uq_page_analysis_version",
        ),
    )
    op.create_index(
        "ix_page_analyses_tenant_search",
        "page_analyses",
        ["tenant_id", "document_id", "page_number"],
    )
    op.create_index(
        "uq_page_analysis_active",
        "page_analyses",
        ["tenant_id", "document_id", "page_number"],
        unique=True,
        postgresql_where=sa.text("is_active"),
        sqlite_where=sa.text("is_active = 1"),
    )
    op.create_table(
        "notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("note_type", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number > 0", name=op.f("ck_notes_note_page")
        ),
        sa.CheckConstraint(
            "note_type IN ('note', 'question', 'insight', 'exam_focus')",
            name=op.f("ck_notes_note_type"),
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["chapters.id"],
            name="fk_notes_chapter_id_chapters",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name="fk_notes_course_id_courses", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_notes_document_id_documents",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_notes_tenant_id_tenants", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_notes_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notes"),
    )
    op.create_index(
        "ix_notes_tenant_scope",
        "notes",
        ["tenant_id", "course_id", "document_id", "page_number"],
    )
    op.create_table(
        "reading_progress",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("last_page", sa.Integer(), nullable=False),
        sa.Column("furthest_page", sa.Integer(), nullable=False),
        sa.Column("viewed_pages", sa.JSON(), nullable=False),
        sa.Column("total_seconds", sa.Integer(), nullable=False),
        sa.Column("is_completed", sa.Boolean(), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.CheckConstraint(
            "furthest_page > 0",
            name=op.f("ck_reading_progress_reading_furthest_page"),
        ),
        sa.CheckConstraint("last_page > 0", name=op.f("ck_reading_progress_reading_last_page")),
        sa.CheckConstraint(
            "total_seconds >= 0",
            name=op.f("ck_reading_progress_reading_total_seconds"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_reading_progress_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_reading_progress_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_reading_progress_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("tenant_id", "user_id", "document_id", name="pk_reading_progress"),
    )
    op.create_index(
        "ix_reading_progress_recent",
        "reading_progress",
        ["tenant_id", "user_id", "last_read_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_reading_progress_recent", table_name="reading_progress")
    op.drop_table("reading_progress")
    op.drop_index("ix_notes_tenant_scope", table_name="notes")
    op.drop_table("notes")
    op.drop_index("uq_page_analysis_active", table_name="page_analyses")
    op.drop_index("ix_page_analyses_tenant_search", table_name="page_analyses")
    op.drop_table("page_analyses")
    op.drop_index("ix_analysis_jobs_tenant_document", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_claim", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
    op.drop_index("ix_documents_tenant_course", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_chapters_tenant_course", table_name="chapters")
    op.drop_table("chapters")
    op.drop_index("ix_courses_tenant_updated", table_name="courses")
    op.drop_table("courses")
    op.drop_index("ix_memberships_tenant_user", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("tenants")
