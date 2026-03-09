"""expand labeling fields

Revision ID: 0015_expand_label_fields
Revises: 0014_add_keyword_seo_profiles
Create Date: 2026-03-07 18:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0015_expand_label_fields"
down_revision: Union[str, None] = "0014_add_keyword_seo_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("content_labels", schema=None) as batch_op:
        batch_op.add_column(sa.Column("structure_type", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("title_type", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("commercial_intent", sa.Integer(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("writing_fit_score", sa.Integer(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("cta_present", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("faq_structure", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    with op.batch_alter_table("image_labels", schema=None) as batch_op:
        batch_op.add_column(sa.Column("text_overlay", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("thumbnail_score", sa.Integer(), nullable=False, server_default=sa.text("0")))


def downgrade() -> None:
    with op.batch_alter_table("image_labels", schema=None) as batch_op:
        batch_op.drop_column("thumbnail_score")
        batch_op.drop_column("text_overlay")

    with op.batch_alter_table("content_labels", schema=None) as batch_op:
        batch_op.drop_column("faq_structure")
        batch_op.drop_column("cta_present")
        batch_op.drop_column("writing_fit_score")
        batch_op.drop_column("commercial_intent")
        batch_op.drop_column("title_type")
        batch_op.drop_column("structure_type")
