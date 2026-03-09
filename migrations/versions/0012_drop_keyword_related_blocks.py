"""drop obsolete keyword related block table

Revision ID: 0012_drop_keyword_related_blocks
Revises: 0011_localize_label_values_ko
Create Date: 2026-03-07 12:10:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0012_drop_keyword_related_blocks"
down_revision: Union[str, None] = "0011_localize_label_values_ko"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS keyword_related_blocks")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS keyword_related_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_keyword_id INTEGER NOT NULL,
            related_keyword VARCHAR(200) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(source_keyword_id) REFERENCES keywords(id) ON DELETE CASCADE,
            UNIQUE(source_keyword_id, related_keyword)
        )
        """
    )
