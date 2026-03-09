"""expand image label fields

Revision ID: 0016_expand_image_label_fields
Revises: 0015_expand_label_fields
Create Date: 2026-03-07 20:10:00
"""

from __future__ import annotations

from alembic import op


revision = "0016_expand_image_label_fields"
down_revision = "0015_expand_label_fields"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    rows = bind.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]) == column_name for row in rows)


def upgrade() -> None:
    for column_name, column_type in (
        ("image_type", "VARCHAR(30)"),
        ("subject_tags", "TEXT"),
        ("commercial_intent", "INTEGER DEFAULT 0"),
        ("keyword_relevance_score", "INTEGER DEFAULT 0"),
    ):
        if not _has_column("image_labels", column_name):
            op.execute(f"ALTER TABLE image_labels ADD COLUMN {column_name} {column_type}")


def downgrade() -> None:
    # SQLite runtime upgrade path keeps additive columns.
    return None
