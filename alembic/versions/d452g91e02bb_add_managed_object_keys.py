"""move generated app delivery payloads to managed local object store

Revision ID: d452f91e02bb
Revises: c341f80d91aa
"""
from alembic import op
import sqlalchemy as sa

revision = "d452f91e02bb"
down_revision = "c341f80d91aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("managed_artifacts", sa.Column("object_key", sa.String(600), nullable=True))
    op.create_index("ix_managed_artifacts_object_key", "managed_artifacts", ["object_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_managed_artifacts_object_key", table_name="managed_artifacts")
    op.drop_column("managed_artifacts", "object_key")
