"""add raw_contents.body_html

Revision ID: 0013_add_raw_content_body_html
Revises: 0012_drop_keyword_related_blocks
Create Date: 2026-03-07 15:05:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_add_raw_content_body_html"
down_revision: Union[str, None] = "0012_drop_keyword_related_blocks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("raw_contents") as batch_op:
        batch_op.add_column(sa.Column("body_html", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("raw_contents") as batch_op:
        batch_op.drop_column("body_html")
