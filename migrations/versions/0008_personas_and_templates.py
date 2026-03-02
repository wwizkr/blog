"""add personas and article templates

Revision ID: 0008_personas_and_templates
Revises: 0007_publish_channels_and_api_url
Create Date: 2026-02-28 10:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008_personas_and_templates"
down_revision: Union[str, None] = "0007_publish_channels_and_api_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "personas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("tone", sa.String(length=100), nullable=True),
        sa.Column("style_guide", sa.Text(), nullable=True),
        sa.Column("banned_words", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "article_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("template_type", sa.String(length=20), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("output_schema", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("generated_articles") as batch_op:
        batch_op.add_column(sa.Column("persona_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("template_name", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("template_version", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_generated_articles_persona_id", "personas", ["persona_id"], ["id"], ondelete="SET NULL")
        batch_op.create_foreign_key("fk_generated_articles_template_id", "article_templates", ["template_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("generated_articles") as batch_op:
        batch_op.drop_constraint("fk_generated_articles_template_id", type_="foreignkey")
        batch_op.drop_constraint("fk_generated_articles_persona_id", type_="foreignkey")
        batch_op.drop_column("template_version")
        batch_op.drop_column("template_name")
        batch_op.drop_column("template_id")
        batch_op.drop_column("persona_id")

    op.drop_table("article_templates")
    op.drop_table("personas")
