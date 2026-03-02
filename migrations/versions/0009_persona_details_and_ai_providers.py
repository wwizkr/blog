"""add persona details and ai providers

Revision ID: 0009_persona_details_and_ai_providers
Revises: 0008_personas_and_templates
Create Date: 2026-02-28 12:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0009_persona_details_and_ai_providers"
down_revision: Union[str, None] = "0008_personas_and_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("personas") as batch_op:
        batch_op.add_column(sa.Column("age_group", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("gender", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("personality", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("interests", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("speech_style", sa.String(length=120), nullable=True))

    op.create_table(
        "ai_providers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("api_key_alias", sa.String(length=120), nullable=True),
        sa.Column("is_paid", sa.Boolean(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("rate_limit_per_min", sa.Integer(), nullable=True),
        sa.Column("daily_budget_limit", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ai_providers")

    with op.batch_alter_table("personas") as batch_op:
        batch_op.drop_column("speech_style")
        batch_op.drop_column("interests")
        batch_op.drop_column("personality")
        batch_op.drop_column("gender")
        batch_op.drop_column("age_group")
