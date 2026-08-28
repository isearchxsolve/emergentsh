"""link every job to a deduplicated managed archive

Revision ID: e563f02a13cc
Revises: d452f91e02bb
"""
from alembic import op
import sqlalchemy as sa

revision = "e563f02a13cc"
down_revision = "d452f91e02bb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pipeline_jobs", sa.Column("archive_sha256", sa.String(64), nullable=True))
    op.create_index("ix_pipeline_jobs_archive_sha256", "pipeline_jobs", ["archive_sha256"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_jobs_archive_sha256", table_name="pipeline_jobs")
    op.drop_column("pipeline_jobs", "archive_sha256")
