from __future__ import annotations

import re

from storage.repositories import CrawlRepository, LabelRepository


class LabelingService:
    TOPIC_PATTERNS = {
        "음식": r"(맛집|음식|식당|메뉴|카페|디저트)",
        "기술": r"(AI|인공지능|개발|코드|프로그래밍|앱|소프트웨어|툴)",
        "여행": r"(여행|숙소|호텔|투어|비행|관광)",
        "뷰티": r"(피부|화장품|메이크업|뷰티|향수)",
        "쇼핑": r"(구매|가격|할인|배송|리뷰|제품)",
    }

    POSITIVE = r"(추천|최고|좋다|만족|훌륭|완벽|가성비)"
    NEGATIVE = r"(별로|아쉽|불편|최악|실망|문제)"
    INFORMATIVE = r"(방법|가이드|팁|정리|비교|분석|기준)"
    EMOTIONAL = r"(느낌|감성|설렘|행복|분위기|힐링)"

    def label_unlabeled_contents(self, limit: int = 200) -> dict:
        rows = CrawlRepository.list_unlabeled_contents(limit)
        labeled = 0
        for row in rows:
            tone, sentiment, topics, quality = self._label_content(row.title, row.body_text)
            LabelRepository.upsert_content_label(
                content_id=row.id,
                tone=tone,
                sentiment=sentiment,
                topics=topics,
                quality_score=quality,
            )
            labeled += 1
        return {"labeled": labeled, "target": len(rows)}

    def label_unlabeled_images(self, limit: int = 300) -> dict:
        rows = CrawlRepository.list_unlabeled_images(limit)
        labeled = 0
        for row in rows:
            category, mood, quality, is_thumbnail = self._label_image(row.image_url)
            LabelRepository.upsert_image_label(
                image_id=row.id,
                category=category,
                mood=mood,
                quality_score=quality,
                is_thumbnail_candidate=is_thumbnail,
            )
            labeled += 1
        return {"labeled": labeled, "target": len(rows)}

    def _label_content(self, title: str, body: str) -> tuple[str, str, list[str], int]:
        text = f"{title} {body}".lower()

        topics: list[str] = []
        for topic, pattern in self.TOPIC_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                topics.append(topic)
        if not topics:
            topics.append("일반")

        if re.search(self.INFORMATIVE, text, re.IGNORECASE):
            tone = "정보형"
        elif re.search(self.EMOTIONAL, text, re.IGNORECASE):
            tone = "감성형"
        else:
            tone = "후기형"

        pos = len(re.findall(self.POSITIVE, text, re.IGNORECASE))
        neg = len(re.findall(self.NEGATIVE, text, re.IGNORECASE))
        if pos > neg:
            sentiment = "긍정"
        elif neg > pos:
            sentiment = "부정"
        else:
            sentiment = "중립"

        length = len(body or "")
        quality = 2
        if length > 300:
            quality = 3
        if length > 1000:
            quality = 4
        if length > 2000:
            quality = 5

        return tone, sentiment, topics[:5], quality

    def _label_image(self, image_url: str) -> tuple[str, str, int, bool]:
        low = (image_url or "").lower()
        category = "기타"
        if any(key in low for key in ["food", "menu", "restaurant", "cafe"]):
            category = "음식"
        elif any(key in low for key in ["hotel", "room", "stay"]):
            category = "숙소"
        elif any(key in low for key in ["beach", "mountain", "view", "travel"]):
            category = "풍경"

        mood = "중립"
        if any(key in low for key in ["night", "dark"]):
            mood = "어두움"
        elif any(key in low for key in ["sun", "bright", "light"]):
            mood = "밝음"

        quality = 3
        if image_url.startswith("https"):
            quality = 4

        is_thumbnail = category in {"음식", "숙소", "풍경"} and quality >= 4
        return category, mood, quality, is_thumbnail


labeling_service = LabelingService()


