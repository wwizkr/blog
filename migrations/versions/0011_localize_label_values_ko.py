"""localize label values to korean

Revision ID: 0011_localize_label_values_ko
Revises: 0010_related_keywords
Create Date: 2026-03-02 15:30:00
"""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0011_localize_label_values_ko"
down_revision: Union[str, None] = "0010_related_keywords"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TONE_MAP = {
    "informative": "정보형",
    "emotional": "감성형",
    "review": "후기형",
}
SENTIMENT_MAP = {
    "positive": "긍정",
    "negative": "부정",
    "neutral": "중립",
}
TOPIC_MAP = {
    "food": "음식",
    "tech": "기술",
    "travel": "여행",
    "beauty": "뷰티",
    "shopping": "쇼핑",
    "general": "일반",
}
CATEGORY_MAP = {
    "food": "음식",
    "room": "숙소",
    "scenery": "풍경",
    "other": "기타",
}
MOOD_MAP = {
    "neutral": "중립",
    "dark": "어두움",
    "bright": "밝음",
}


def _normalize_topics(raw: str | None) -> str | None:
    if not raw:
        return raw
    text = str(raw).strip()
    if not text:
        return text
    try:
        decoded = json.loads(text)
    except Exception:
        return text
    if not isinstance(decoded, list):
        return text
    normalized: list[str] = []
    seen: set[str] = set()
    for item in decoded:
        key = str(item or "").strip()
        if not key:
            continue
        mapped = TOPIC_MAP.get(key, key)
        if mapped in seen:
            continue
        seen.add(mapped)
        normalized.append(mapped)
    return json.dumps(normalized, ensure_ascii=False)


def upgrade() -> None:
    conn = op.get_bind()

    for old, new in TONE_MAP.items():
        conn.execute(sa.text("UPDATE content_labels SET tone=:new WHERE tone=:old"), {"old": old, "new": new})
    for old, new in SENTIMENT_MAP.items():
        conn.execute(sa.text("UPDATE content_labels SET sentiment=:new WHERE sentiment=:old"), {"old": old, "new": new})

    rows = conn.execute(sa.text("SELECT id, topics FROM content_labels")).fetchall()
    for row_id, topics in rows:
        normalized = _normalize_topics(topics)
        if normalized != topics:
            conn.execute(
                sa.text("UPDATE content_labels SET topics=:topics WHERE id=:id"),
                {"id": row_id, "topics": normalized},
            )

    for old, new in CATEGORY_MAP.items():
        conn.execute(sa.text("UPDATE image_labels SET category=:new WHERE category=:old"), {"old": old, "new": new})
    for old, new in MOOD_MAP.items():
        conn.execute(sa.text("UPDATE image_labels SET mood=:new WHERE mood=:old"), {"old": old, "new": new})


def downgrade() -> None:
    conn = op.get_bind()

    inv_tone = {v: k for k, v in TONE_MAP.items()}
    inv_sentiment = {v: k for k, v in SENTIMENT_MAP.items()}
    inv_topic = {v: k for k, v in TOPIC_MAP.items()}
    inv_category = {v: k for k, v in CATEGORY_MAP.items()}
    inv_mood = {v: k for k, v in MOOD_MAP.items()}

    for old, new in inv_tone.items():
        conn.execute(sa.text("UPDATE content_labels SET tone=:new WHERE tone=:old"), {"old": old, "new": new})
    for old, new in inv_sentiment.items():
        conn.execute(sa.text("UPDATE content_labels SET sentiment=:new WHERE sentiment=:old"), {"old": old, "new": new})

    rows = conn.execute(sa.text("SELECT id, topics FROM content_labels")).fetchall()
    for row_id, topics in rows:
        if not topics:
            continue
        text = str(topics).strip()
        if not text:
            continue
        try:
            decoded = json.loads(text)
        except Exception:
            continue
        if not isinstance(decoded, list):
            continue
        reverted = [inv_topic.get(str(item or "").strip(), str(item or "").strip()) for item in decoded]
        payload = json.dumps(reverted, ensure_ascii=False)
        if payload != topics:
            conn.execute(sa.text("UPDATE content_labels SET topics=:topics WHERE id=:id"), {"id": row_id, "topics": payload})

    for old, new in inv_category.items():
        conn.execute(sa.text("UPDATE image_labels SET category=:new WHERE category=:old"), {"old": old, "new": new})
    for old, new in inv_mood.items():
        conn.execute(sa.text("UPDATE image_labels SET mood=:new WHERE mood=:old"), {"old": old, "new": new})
