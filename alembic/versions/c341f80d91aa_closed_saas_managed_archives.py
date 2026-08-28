"""closed SaaS auth sessions and managed generated-app archives

Revision ID: c341f80d91aa
Revises: b724e18a09f1
"""
from alembic import op
import sqlalchemy as sa

revision = "c341f80d91aa"
down_revision = "b724e18a09f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("pipeline_jobs", sa.Column("reserved_bytes", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "managed_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pipeline_job_id", sa.String(32), sa.ForeignKey("pipeline_jobs.job_id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_managed_artifacts_user_id", "managed_artifacts", ["user_id"])
    op.create_index("ix_managed_artifacts_pipeline_job_id", "managed_artifacts", ["pipeline_job_id"])
    op.create_index("ix_managed_artifacts_sha256", "managed_artifacts", ["sha256"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_managed_artifacts_sha256", table_name="managed_artifacts")
    op.drop_index("ix_managed_artifacts_pipeline_job_id", table_name="managed_artifacts")
    op.drop_index("ix_managed_artifacts_user_id", table_name="managed_artifacts")
    op.drop_table("managed_artifacts")
    op.drop_column("pipeline_jobs", "reserved_bytes")
    op.drop_column("users", "auth_version")
