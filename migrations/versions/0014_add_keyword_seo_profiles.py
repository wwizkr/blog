"""add keyword seo profile tables

Revision ID: 0014_add_keyword_seo_profiles
Revises: 0013_add_raw_content_body_html
Create Date: 2026-03-07 16:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0014_add_keyword_seo_profiles"
down_revision: Union[str, None] = "0013_add_raw_content_body_html"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "keyword_seo_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("keyword_id", sa.Integer(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_title_length", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_body_length", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_heading_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_image_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_list_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("dominant_format", sa.String(length=30), nullable=True),
        sa.Column("common_sections_json", sa.Text(), nullable=True),
        sa.Column("common_terms_json", sa.Text(), nullable=True),
        sa.Column("recommended_length_min", sa.Integer(), nullable=True),
        sa.Column("recommended_length_max", sa.Integer(), nullable=True),
        sa.Column("recommended_heading_count", sa.Integer(), nullable=True),
        sa.Column("recommended_image_count", sa.Integer(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("analysis_basis_json", sa.Text(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["keyword_id"], ["keywords.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("keyword_id"),
    )
    op.create_table(
        "keyword_seo_profile_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("keyword_id", sa.Integer(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("source_content_ids_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["keyword_id"], ["keywords.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("keyword_seo_profile_runs")
    op.drop_table("keyword_seo_profiles")
