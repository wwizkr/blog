"""label tables

Revision ID: 0003_label_tables
Revises: 0002_collection_tables
Create Date: 2026-02-27 01:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_label_tables"
down_revision: Union[str, None] = "0002_collection_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_labels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("tone", sa.String(length=30), nullable=True),
        sa.Column("sentiment", sa.String(length=30), nullable=True),
        sa.Column("topics", sa.Text(), nullable=True),
        sa.Column("quality_score", sa.Integer(), nullable=False),
        sa.Column("label_method", sa.String(length=20), nullable=False),
        sa.Column("labeled_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["content_id"], ["raw_contents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_id"),
    )

    op.create_table(
        "image_labels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=True),
        sa.Column("mood", sa.String(length=30), nullable=True),
        sa.Column("quality_score", sa.Integer(), nullable=False),
        sa.Column("is_thumbnail_candidate", sa.Boolean(), nullable=False),
        sa.Column("label_method", sa.String(length=20), nullable=False),
        sa.Column("labeled_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["image_id"], ["raw_images.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("image_id"),
    )


def downgrade() -> None:
    op.drop_table("image_labels")
    op.drop_table("content_labels")

