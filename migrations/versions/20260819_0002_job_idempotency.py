"""Add a tenant-scoped analysis job idempotency key.

Revision ID: 20260819_0002
Revises: 20260819_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0002"
down_revision: str | None = "20260819_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("analysis_jobs") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=64), nullable=True))
    op.execute(
        sa.text(
            "UPDATE analysis_jobs SET idempotency_key = "
            "'legacy-' || CAST(id AS VARCHAR) WHERE idempotency_key IS NULL"
        )
    )
    with op.batch_alter_table("analysis_jobs") as batch_op:
        batch_op.alter_column("idempotency_key", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_unique_constraint(
            "uq_analysis_jobs_tenant_idempotency", ["tenant_id", "idempotency_key"]
        )


def downgrade() -> None:
    with op.batch_alter_table("analysis_jobs") as batch_op:
        batch_op.drop_constraint("uq_analysis_jobs_tenant_idempotency", type_="unique")
        batch_op.drop_column("idempotency_key")
