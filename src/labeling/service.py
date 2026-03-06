from __future__ import annotations

import re
from datetime import datetime

from core.settings_keys import LabelSettingKeys
from storage.repositories import AppSettingRepository, CrawlRepository, LabelRepository


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
        stage_counts = {"rule_done": 0, "free_api_done": 0, "paid_api_done": 0, "completed": 0}
        method = str(AppSettingRepository.get_value(LabelSettingKeys.METHOD, "rule") or "rule").strip().lower()
        quota = self._quota_state()
        for row in rows:
            tone, sentiment, topics, quality = self._label_content(row.title, row.body_text)
            confidence = max(0.0, min(1.0, float(quality) / 5.0))
            stage, route_method = self._resolve_stage(method=method, confidence=confidence, quota=quota)
            LabelRepository.upsert_content_label(
                content_id=row.id,
                tone=tone,
                sentiment=sentiment,
                topics=topics,
                quality_score=quality,
                label_method=route_method,
            )
            LabelRepository.mark_content_labeled(content_id=row.id, confidence=confidence, stage_status=stage, completed=False)
            stage_counts[stage] = int(stage_counts.get(stage, 0)) + 1
            stage_counts["completed"] = int(stage_counts.get("completed", 0)) + 1
            labeled += 1
        self._save_quota_state(quota)
        LabelRepository.record_run_log(
            run_kind="content",
            method=method,
            stage_summary=stage_counts,
            labeled_count=labeled,
            target_count=len(rows),
            free_api_used=int(quota["delta_free"]),
            paid_api_used=int(quota["delta_paid"]),
            message=f"텍스트 라벨링 {labeled}/{len(rows)}",
        )
        return {
            "labeled": labeled,
            "target": len(rows),
            "stage_counts": stage_counts,
            "free_api_used": int(quota["delta_free"]),
            "paid_api_used": int(quota["delta_paid"]),
        }

    def label_unlabeled_images(self, limit: int = 300) -> dict:
        rows = CrawlRepository.list_unlabeled_images(limit)
        labeled = 0
        stage_counts = {"rule_done": 0, "free_api_done": 0, "paid_api_done": 0, "completed": 0}
        method = str(AppSettingRepository.get_value(LabelSettingKeys.METHOD, "rule") or "rule").strip().lower()
        quota = self._quota_state()
        for row in rows:
            category, mood, quality, is_thumbnail = self._label_image(row.image_url)
            confidence = max(0.0, min(1.0, float(quality) / 5.0))
            stage, route_method = self._resolve_stage(method=method, confidence=confidence, quota=quota)
            LabelRepository.upsert_image_label(
                image_id=row.id,
                category=category,
                mood=mood,
                quality_score=quality,
                is_thumbnail_candidate=is_thumbnail,
                label_method=route_method,
            )
            LabelRepository.mark_image_labeled(image_id=row.id, confidence=confidence, stage_status=stage, completed=False)
            stage_counts[stage] = int(stage_counts.get(stage, 0)) + 1
            stage_counts["completed"] = int(stage_counts.get("completed", 0)) + 1
            labeled += 1
        self._save_quota_state(quota)
        LabelRepository.record_run_log(
            run_kind="image",
            method=method,
            stage_summary=stage_counts,
            labeled_count=labeled,
            target_count=len(rows),
            free_api_used=int(quota["delta_free"]),
            paid_api_used=int(quota["delta_paid"]),
            message=f"이미지 라벨링 {labeled}/{len(rows)}",
        )
        return {
            "labeled": labeled,
            "target": len(rows),
            "stage_counts": stage_counts,
            "free_api_used": int(quota["delta_free"]),
            "paid_api_used": int(quota["delta_paid"]),
        }

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

    @staticmethod
    def _quota_state() -> dict:
        today = datetime.utcnow().strftime("%Y%m%d")
        quota_date = str(AppSettingRepository.get_value(LabelSettingKeys.QUOTA_DATE, today) or today)
        free_limit = max(0, _to_int(AppSettingRepository.get_value(LabelSettingKeys.FREE_API_DAILY_LIMIT, "200"), 200))
        paid_limit = max(0, _to_int(AppSettingRepository.get_value(LabelSettingKeys.PAID_API_DAILY_LIMIT, "20"), 20))
        free_used = max(0, _to_int(AppSettingRepository.get_value(LabelSettingKeys.FREE_API_USED, "0"), 0))
        paid_used = max(0, _to_int(AppSettingRepository.get_value(LabelSettingKeys.PAID_API_USED, "0"), 0))
        if quota_date != today:
            quota_date = today
            free_used = 0
            paid_used = 0
        return {
            "date": quota_date,
            "free_limit": free_limit,
            "paid_limit": paid_limit,
            "free_used": free_used,
            "paid_used": paid_used,
            "delta_free": 0,
            "delta_paid": 0,
        }

    @staticmethod
    def _save_quota_state(quota: dict) -> None:
        AppSettingRepository.set_value(LabelSettingKeys.QUOTA_DATE, str(quota.get("date") or ""))
        AppSettingRepository.set_value(LabelSettingKeys.FREE_API_USED, str(max(0, int(quota.get("free_used") or 0))))
        AppSettingRepository.set_value(LabelSettingKeys.PAID_API_USED, str(max(0, int(quota.get("paid_used") or 0))))

    @staticmethod
    def _resolve_stage(method: str, confidence: float, quota: dict) -> tuple[str, str]:
        if method != "ai":
            return "rule_done", "rule"

        threshold_mid = max(1, min(5, _to_int(AppSettingRepository.get_value(LabelSettingKeys.THRESHOLD_MID, "3"), 3))) / 5.0
        threshold_high = max(threshold_mid, max(1, min(5, _to_int(AppSettingRepository.get_value(LabelSettingKeys.THRESHOLD_HIGH, "4"), 4))) / 5.0)

        if confidence >= threshold_high:
            return "rule_done", "rule"

        free_remaining = max(0, int(quota["free_limit"]) - int(quota["free_used"]))
        paid_remaining = max(0, int(quota["paid_limit"]) - int(quota["paid_used"]))

        if confidence >= threshold_mid:
            if free_remaining > 0:
                quota["free_used"] = int(quota["free_used"]) + 1
                quota["delta_free"] = int(quota["delta_free"]) + 1
                return "free_api_done", "free_api"
            return "rule_done", "rule"

        if paid_remaining > 0:
            quota["paid_used"] = int(quota["paid_used"]) + 1
            quota["delta_paid"] = int(quota["delta_paid"]) + 1
            return "paid_api_done", "paid_api"
        if free_remaining > 0:
            quota["free_used"] = int(quota["free_used"]) + 1
            quota["delta_free"] = int(quota["delta_free"]) + 1
            return "free_api_done", "free_api"
        return "rule_done", "rule"


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


labeling_service = LabelingService()


