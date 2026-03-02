"""add related keyword tables

Revision ID: 0010_related_keywords
Revises: 0009_persona_details_and_ai_providers
Create Date: 2026-02-28 16:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010_related_keywords"
down_revision: Union[str, None] = "0009_persona_details_and_ai_providers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("keywords") as batch_op:
        batch_op.add_column(sa.Column("is_auto_generated", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    op.create_table(
        "keyword_related_relations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_keyword_id", sa.Integer(), nullable=False),
        sa.Column("related_keyword_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("collect_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_keyword_id"], ["keywords.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["related_keyword_id"], ["keywords.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_keyword_id", "related_keyword_id", name="uq_keyword_related_pair"),
    )

    op.create_table(
        "keyword_related_blocks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_keyword_id", sa.Integer(), nullable=False),
        sa.Column("related_keyword", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_keyword_id"], ["keywords.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_keyword_id", "related_keyword", name="uq_keyword_related_block"),
    )


def downgrade() -> None:
    op.drop_table("keyword_related_blocks")
    op.drop_table("keyword_related_relations")
    with op.batch_alter_table("keywords") as batch_op:
        batch_op.drop_column("is_auto_generated")
