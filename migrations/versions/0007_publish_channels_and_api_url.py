"""publish channels table and api_url setting

Revision ID: 0007_publish_channels_and_api_url
Revises: 0006_channel_settings_and_image_source
Create Date: 2026-02-27 02:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0007_publish_channels_and_api_url"
down_revision: Union[str, None] = "0006_channel_settings_and_image_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "publish_channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    with op.batch_alter_table("publish_channel_settings") as batch_op:
        batch_op.add_column(sa.Column("api_url", sa.String(length=1000), nullable=True))

    # 기존 설정의 channel_code를 publish_channels로 이관
    op.execute(
        """
        INSERT INTO publish_channels(code, display_name, is_enabled, created_at)
        SELECT pcs.channel_code, pcs.channel_code, 1, CURRENT_TIMESTAMP
        FROM publish_channel_settings pcs
        WHERE pcs.channel_code NOT IN (SELECT code FROM publish_channels)
        """
    )

    # 기본 발행채널 보정
    op.execute(
        """
        INSERT INTO publish_channels(code, display_name, is_enabled, created_at)
        SELECT 'custom_api', '커스텀 API', 1, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (SELECT 1 FROM publish_channels WHERE code='custom_api')
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("publish_channel_settings") as batch_op:
        batch_op.drop_column("api_url")
    op.drop_table("publish_channels")

