"""channel settings and image source url

Revision ID: 0006_channel_settings_and_image_source
Revises: 0005_publish_jobs
Create Date: 2026-02-27 02:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006_channel_settings_and_image_source"
down_revision: Union[str, None] = "0005_publish_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("raw_images") as batch_op:
        batch_op.add_column(sa.Column("source_url", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("page_url", sa.String(length=1000), nullable=True))

    op.execute("UPDATE raw_images SET source_url = image_url WHERE source_url IS NULL")

    with op.batch_alter_table("raw_images") as batch_op:
        batch_op.alter_column("source_url", existing_type=sa.String(length=1000), nullable=False)
        batch_op.create_unique_constraint("uq_raw_images_source_url", ["source_url"])

    op.create_table(
        "publish_channel_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_code", sa.String(length=50), nullable=False),
        sa.Column("publish_cycle_minutes", sa.Integer(), nullable=False),
        sa.Column("publish_mode", sa.String(length=20), nullable=False),
        sa.Column("publish_format", sa.String(length=20), nullable=False),
        sa.Column("writing_style", sa.String(length=20), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_code"),
    )


def downgrade() -> None:
    op.drop_table("publish_channel_settings")
    with op.batch_alter_table("raw_images") as batch_op:
        batch_op.drop_constraint("uq_raw_images_source_url", type_="unique")
        batch_op.drop_column("page_url")
        batch_op.drop_column("source_url")

