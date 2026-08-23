"""add durable pipeline worker leases

Revision ID: b724e18a09f1
Revises: 9936aa792817
"""
from alembic import op
import sqlalchemy as sa

revision = "b724e18a09f1"
down_revision = "9936aa792817"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pipeline_jobs", sa.Column("use_mock", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("pipeline_jobs", sa.Column("target", sa.String(length=50), nullable=False, server_default="web"))
    op.add_column("pipeline_jobs", sa.Column("worker_id", sa.String(length=100), nullable=True))
    op.add_column("pipeline_jobs", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
    op.add_column("pipeline_jobs", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_pipeline_jobs_worker_id", "pipeline_jobs", ["worker_id"])
    op.create_index("ix_pipeline_jobs_lease_expires_at", "pipeline_jobs", ["lease_expires_at"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_jobs_lease_expires_at", table_name="pipeline_jobs")
    op.drop_index("ix_pipeline_jobs_worker_id", table_name="pipeline_jobs")
    op.drop_column("pipeline_jobs", "attempts")
    op.drop_column("pipeline_jobs", "lease_expires_at")
    op.drop_column("pipeline_jobs", "worker_id")
    op.drop_column("pipeline_jobs", "use_mock")
    op.drop_column("pipeline_jobs", "target")
