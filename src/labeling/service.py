from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import unquote

from core.settings_keys import LabelSettingKeys
from labeling.ai_service import labeling_ai_service
from storage.database import init_database
from storage.repositories import AppSettingRepository, CrawlRepository, LabelRepository


class LabelingService:
    TOPIC_PATTERNS = {
        "음식": r"(맛집|음식|식당|메뉴|카페|디저트)",
        "기술": r"(AI|인공지능|개발|코드|프로그래밍|앱|소프트웨어|툴|자동화|api|시스템)",
        "여행": r"(여행|숙소|호텔|투어|비행|관광)",
        "뷰티": r"(피부|화장품|메이크업|뷰티|향수)",
        "쇼핑": r"(구매|가격|할인|배송|리뷰|제품|렌탈|설치비용|사은품)",
        "생활서비스": r"(설치|기사|렌탈|정수기|청소|이사|수리|상담|비용|견적)",
    }

    POSITIVE = r"(추천|최고|좋다|만족|훌륭|완벽|가성비)"
    NEGATIVE = r"(별로|아쉽|불편|최악|실망|문제)"
    INFORMATIVE = r"(방법|가이드|팁|정리|비교|분석|기준)"
    EMOTIONAL = r"(느낌|감성|설렘|행복|분위기|힐링)"
    CTA_PATTERN = r"(문의|상담|신청|예약|구매|가입|클릭|링크|바로가기|연락|상담받|무료상담|설치문의|렌탈문의)"
    COMMERCIAL_PATTERN = r"(광고|협찬|제공받아|업체|이벤트|혜택|사은품|할인|특가|제휴|프로모션|상담)"
    FAQ_PATTERN = r"(faq|자주 묻는 질문|질문|답변|q&a|q\.|a\.)"
    REVIEW_PATTERN = r"(후기|리뷰|사용기|체험기|실사용)"
    COMPARISON_PATTERN = r"(비교|차이|vs|장단점|순위|top\d*)"
    GUIDE_PATTERN = r"(방법|가이드|설치|정리|체크|팁|요령|주의사항)"
    IMAGE_INSTALL_PATTERN = r"(설치|시공|교체|배관|타공|기사|방문|현장)"
    IMAGE_PRODUCT_PATTERN = r"(정수기|제품|기기|본체|모델|렌탈|사은품)"
    IMAGE_PROMO_PATTERN = r"(배너|광고|이벤트|혜택|상담|문의|카드뉴스|포스터)"
    IMAGE_SCREENSHOT_PATTERN = r"(캡처|screenshot|screen|gallery|dcinside|블로그|카페|forum|community)"
    IMAGE_DOCUMENT_PATTERN = r"(표|차트|안내문|문서|계약|신청서|폼)"
    QUESTION_TITLE_PATTERN = r"(\?|무엇|어떻게|왜|가능할까|될까|되나요|얼마나)"
    LIST_TITLE_PATTERN = r"(\d+\s*가지|\d+\s*개|top\s*\d+|순위|정리)"
    HEADING_PATTERN = r"(?m)^\s{0,3}(#{1,6}\s+.+|[0-9]+\.\s+.+|[가-힣A-Za-z0-9\s]{2,30}\n[-=]{2,})"
    LIST_PATTERN = r"(?m)^\s*([-*•]|\d+\.)\s+"
    CONTACT_PATTERN = r"(010[-\s]?\d{4}[-\s]?\d{4}|카카오톡|톡톡|오픈채팅|문의전화|연락처|상담번호)"
    PRICE_PATTERN = r"(\d{1,3}(,\d{3})+\s*원|\d+\s*만원|\d+\s*원)"
    BOILERPLATE_UI_PATTERN = r"(연관\s*갤러리|최근방문\s*갤러리|이슈박스|마이너\s*갤러리|부매니저|차단하기|닫기|개념글|로그인\s*해주세요)"
    PROMO_SENTENCE_PATTERN = r"(무료상담|즉시문의|지금\s*문의|사은품|특가|이벤트|혜택|최저가|전문업체|설치문의|렌탈문의)"
    NOISE_TOKEN_PATTERN = r"(ㅋㅋ|ㅎㅎ|ㅠㅠ|ㅜㅜ|ㄷㄷ|[!]{2,}|[?]{2,})"
    NEWS_PATTERN = r"(속보|발표|보도|공개|업데이트|출시|공식)"

    def label_unlabeled_contents(self, limit: int = 200) -> dict:
        init_database()
        rows = CrawlRepository.list_unlabeled_contents(limit)
        labeled = 0
        stage_counts = {"rule_done": 0, "free_api_done": 0, "paid_api_done": 0, "completed": 0}
        method = str(AppSettingRepository.get_value(LabelSettingKeys.METHOD, "rule") or "rule").strip().lower()
        quota = self._quota_state()
        for row in rows:
            content_label = self._label_content(row.title, row.body_text)
            confidence = max(0.0, min(1.0, float(content_label["confidence"]) / 5.0))
            stage, route_method = self._resolve_stage(method=method, confidence=confidence, quota=quota)
            if stage in {"free_api_done", "paid_api_done"}:
                enriched = labeling_ai_service.label_content(
                    title=row.title,
                    body=row.body_text,
                    prefer_paid=(stage == "paid_api_done"),
                )
                if enriched:
                    content_label = self._merge_ai_content_label(content_label, enriched)
                    confidence = max(0.0, min(1.0, float(content_label["confidence"]) / 5.0))
                else:
                    stage = "rule_done"
                    route_method = "rule"
            LabelRepository.upsert_content_label(
                content_id=row.id,
                tone=content_label["tone"],
                sentiment=content_label["sentiment"],
                topics=content_label["topics"],
                quality_score=content_label["quality_score"],
                structure_type=content_label["structure_type"],
                title_type=content_label["title_type"],
                commercial_intent=content_label["commercial_intent"],
                writing_fit_score=content_label["writing_fit_score"],
                cta_present=content_label["cta_present"],
                faq_structure=content_label["faq_structure"],
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

    def label_unlabeled_images(self, limit: int = 300, include_completed: bool = False) -> dict:
        init_database()
        rows = CrawlRepository.list_images_for_labeling(limit, include_completed=include_completed)
        labeled = 0
        stage_counts = {"rule_done": 0, "free_api_done": 0, "paid_api_done": 0, "completed": 0}
        method = str(AppSettingRepository.get_value(LabelSettingKeys.METHOD, "rule") or "rule").strip().lower()
        quota = self._quota_state()
        for row in rows:
            keyword_text = ""
            content_title = ""
            content_body = ""
            if getattr(row, "content", None):
                content_title = str(getattr(row.content, "title", "") or "")
                content_body = str(getattr(row.content, "body_text", "") or "")
                keyword_obj = getattr(row.content, "keyword", None)
                keyword_text = str(getattr(keyword_obj, "keyword", "") or "")
            image_label = self._label_image(
                image_url=row.image_url,
                source_url=getattr(row, "source_url", ""),
                content_title=content_title,
                content_body=content_body,
                keyword=keyword_text,
            )
            confidence = max(0.0, min(1.0, float(image_label["confidence"]) / 5.0))
            stage, route_method = self._resolve_stage(method=method, confidence=confidence, quota=quota)
            if stage in {"free_api_done", "paid_api_done"}:
                enriched = labeling_ai_service.label_image(
                    image_url=row.image_url,
                    prefer_paid=(stage == "paid_api_done"),
                )
                if enriched:
                    image_label = self._merge_ai_image_label(image_label, enriched)
                    confidence = max(0.0, min(1.0, float(image_label["confidence"]) / 5.0))
                else:
                    stage = "rule_done"
                    route_method = "rule"
            LabelRepository.upsert_image_label(
                image_id=row.id,
                category=image_label["category"],
                mood=image_label["mood"],
                quality_score=image_label["quality_score"],
                is_thumbnail_candidate=image_label["is_thumbnail_candidate"],
                image_type=image_label["image_type"],
                subject_tags=image_label["subject_tags"],
                commercial_intent=image_label["commercial_intent"],
                keyword_relevance_score=image_label["keyword_relevance_score"],
                text_overlay=image_label["text_overlay"],
                thumbnail_score=image_label["thumbnail_score"],
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
            message=f"이미지 라벨링 {labeled}/{len(rows)}" + (" (재라벨링 포함)" if include_completed else ""),
        )
        return {
            "labeled": labeled,
            "target": len(rows),
            "stage_counts": stage_counts,
            "free_api_used": int(quota["delta_free"]),
            "paid_api_used": int(quota["delta_paid"]),
            "include_completed": bool(include_completed),
        }

    def _label_content(self, title: str, body: str) -> dict:
        title_text = str(title or "")
        body_text = str(body or "")
        text = f"{title_text} {body_text}".lower()
        paragraphs = self._paragraphs(body_text)
        line_count = len([line for line in body_text.splitlines() if line.strip()])
        heading_count = len(re.findall(self.HEADING_PATTERN, body_text, re.IGNORECASE))
        list_count = len(re.findall(self.LIST_PATTERN, body_text, re.IGNORECASE))
        price_hits = len(re.findall(self.PRICE_PATTERN, text, re.IGNORECASE))
        contact_hits = len(re.findall(self.CONTACT_PATTERN, text, re.IGNORECASE))
        boilerplate_hits = len(re.findall(self.BOILERPLATE_UI_PATTERN, text, re.IGNORECASE))
        promo_hits = len(re.findall(self.PROMO_SENTENCE_PATTERN, text, re.IGNORECASE))
        noise_hits = len(re.findall(self.NOISE_TOKEN_PATTERN, text, re.IGNORECASE))
        repeated_ratio = self._repeated_line_ratio(body_text)
        unique_token_ratio = self._unique_token_ratio(body_text)
        summary_density = self._summary_density(body_text)

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

        length = len(body_text)
        commercial_hits = len(re.findall(self.COMMERCIAL_PATTERN, text, re.IGNORECASE))
        cta_hits = len(re.findall(self.CTA_PATTERN, text, re.IGNORECASE))
        faq_hits = len(re.findall(self.FAQ_PATTERN, text, re.IGNORECASE))
        review_hits = len(re.findall(self.REVIEW_PATTERN, text, re.IGNORECASE))
        comparison_hits = len(re.findall(self.COMPARISON_PATTERN, text, re.IGNORECASE))
        guide_hits = len(re.findall(self.GUIDE_PATTERN, text, re.IGNORECASE))
        news_hits = len(re.findall(self.NEWS_PATTERN, text, re.IGNORECASE))
        title_type = self._classify_title_type(title)
        faq_structure = faq_hits >= 2 or ("?" in body_text and "답변" in body_text)
        cta_present = (cta_hits + commercial_hits + contact_hits + promo_hits) >= 2
        structure_type = self._classify_structure_type(
            body=body_text,
            faq_structure=faq_structure,
            review_hits=review_hits,
            comparison_hits=comparison_hits,
            guide_hits=guide_hits,
            cta_present=cta_present,
            heading_count=heading_count,
            list_count=list_count,
            news_hits=news_hits,
        )
        quality = self._score_quality(
            length=length,
            topics=topics,
            structure_type=structure_type,
            cta_present=cta_present,
            heading_count=heading_count,
            list_count=list_count,
            repeated_ratio=repeated_ratio,
            unique_token_ratio=unique_token_ratio,
            boilerplate_hits=boilerplate_hits,
            paragraph_count=len(paragraphs),
        )
        commercial_intent = self._score_commercial_intent(
            commercial_hits=commercial_hits,
            cta_hits=cta_hits,
            review_hits=review_hits,
            price_hits=price_hits,
            contact_hits=contact_hits,
            promo_hits=promo_hits,
        )
        writing_fit_score = self._score_writing_fit(
            length=length,
            quality=quality,
            commercial_intent=commercial_intent,
            faq_structure=faq_structure,
            structure_type=structure_type,
            topic_count=len(topics),
            heading_count=heading_count,
            boilerplate_hits=boilerplate_hits,
            repeated_ratio=repeated_ratio,
            summary_density=summary_density,
            noise_hits=noise_hits,
        )
        confidence = self._score_confidence(
            length=length,
            title_type=title_type,
            structure_type=structure_type,
            topic_count=len(topics),
            faq_structure=faq_structure,
            cta_present=cta_present,
            heading_count=heading_count,
            list_count=list_count,
            repeated_ratio=repeated_ratio,
            unique_token_ratio=unique_token_ratio,
        )

        return {
            "tone": tone,
            "sentiment": sentiment,
            "topics": topics[:5],
            "quality_score": quality,
            "structure_type": structure_type,
            "title_type": title_type,
            "commercial_intent": commercial_intent,
            "writing_fit_score": writing_fit_score,
            "cta_present": cta_present,
            "faq_structure": faq_structure,
            "confidence": confidence,
        }

    def _label_image(self, *, image_url: str, source_url: str = "", content_title: str = "", content_body: str = "", keyword: str = "") -> dict:
        image_url_decoded = unquote(str(image_url or ""))
        source_url_decoded = unquote(str(source_url or ""))
        low = " ".join([
            image_url_decoded.lower(),
            source_url_decoded.lower(),
            str(content_title or "").lower(),
        ]).strip()
        body_low = str(content_body or "").lower()
        category = "기타"
        if any(key in low for key in ["food", "menu", "restaurant", "cafe"]):
            category = "음식"
        elif any(key in low for key in ["hotel", "room", "stay"]):
            category = "숙소"
        elif any(key in low for key in ["beach", "mountain", "view", "travel"]):
            category = "풍경"
        elif re.search(self.IMAGE_PRODUCT_PATTERN, low, re.IGNORECASE):
            category = "제품"
        elif re.search(self.IMAGE_INSTALL_PATTERN, low, re.IGNORECASE):
            category = "현장"

        mood = "중립"
        if any(key in low for key in ["night", "dark"]):
            mood = "어두움"
        elif any(key in low for key in ["sun", "bright", "light"]):
            mood = "밝음"

        image_type = self._classify_image_type(low, body_low)
        subject_tags = self._extract_image_subject_tags(keyword=keyword, title=content_title, body=content_body, image_hint=low)
        quality = 3
        if image_url.startswith("https"):
            quality = 4
        text_overlay = any(token in low for token in ["text", "thumb", "banner", "poster", "card", "summary", "썸네일", "배너"])
        if image_type in {"banner", "document"}:
            text_overlay = True
        commercial_intent = self._score_image_commercial_intent(low=low, body=body_low, image_type=image_type, text_overlay=text_overlay)
        keyword_relevance_score = self._score_image_keyword_relevance(
            keyword=keyword,
            title=content_title,
            body=content_body,
            image_hint=low,
            image_type=image_type,
        )
        thumbnail_score = 40
        if category in {"음식", "숙소", "풍경", "제품", "현장"}:
            thumbnail_score += 25
        if quality >= 4:
            thumbnail_score += 20
        if mood == "밝음":
            thumbnail_score += 10
        if image_type in {"product", "install"}:
            thumbnail_score += 10
        if keyword_relevance_score >= 70:
            thumbnail_score += 10
        if text_overlay:
            thumbnail_score -= 15
        if commercial_intent >= 4:
            thumbnail_score -= 10
        thumbnail_score = max(0, min(100, thumbnail_score))
        is_thumbnail = thumbnail_score >= 60
        confidence = 4 if category != "기타" or image_type != "other" or quality >= 4 else 3
        return {
            "category": category,
            "mood": mood,
            "image_type": image_type,
            "subject_tags": subject_tags,
            "commercial_intent": commercial_intent,
            "keyword_relevance_score": keyword_relevance_score,
            "quality_score": quality,
            "is_thumbnail_candidate": is_thumbnail,
            "text_overlay": text_overlay,
            "thumbnail_score": thumbnail_score,
            "confidence": confidence,
        }

    def _classify_image_type(self, low: str, body: str) -> str:
        if re.search(self.IMAGE_PROMO_PATTERN, low, re.IGNORECASE):
            return "banner"
        if re.search(self.IMAGE_SCREENSHOT_PATTERN, low, re.IGNORECASE):
            return "screenshot"
        if re.search(self.IMAGE_DOCUMENT_PATTERN, low, re.IGNORECASE):
            return "document"
        if re.search(self.IMAGE_INSTALL_PATTERN, f"{low} {body[:800]}", re.IGNORECASE):
            return "install"
        if re.search(self.IMAGE_PRODUCT_PATTERN, low, re.IGNORECASE):
            return "product"
        return "other"

    def _extract_image_subject_tags(self, *, keyword: str, title: str, body: str, image_hint: str) -> list[str]:
        tags: list[str] = []
        for source in (keyword, title, image_hint):
            for token in re.findall(r"[가-힣A-Za-z0-9]{2,20}", str(source or "")):
                token = token.strip().lower()
                if len(token) < 2:
                    continue
                if token in {"https", "http", "www", "com", "blog", "image", "thumb", "png", "jpg", "jpeg"}:
                    continue
                if token not in tags:
                    tags.append(token)
                if len(tags) >= 8:
                    return tags
        for pattern in (self.IMAGE_INSTALL_PATTERN, self.IMAGE_PRODUCT_PATTERN):
            for match in re.findall(pattern, str(body or ""), re.IGNORECASE):
                token = str(match).strip().lower()
                if token and token not in tags:
                    tags.append(token)
                if len(tags) >= 8:
                    break
        return tags[:8]

    def _score_image_commercial_intent(self, *, low: str, body: str, image_type: str, text_overlay: bool) -> int:
        score = 0
        score += len(re.findall(self.PROMO_SENTENCE_PATTERN, low, re.IGNORECASE))
        score += len(re.findall(self.COMMERCIAL_PATTERN, low, re.IGNORECASE))
        score += len(re.findall(self.CTA_PATTERN, low, re.IGNORECASE))
        if text_overlay:
            score += 1
        if image_type == "banner":
            score += 2
        if re.search(self.PROMO_SENTENCE_PATTERN, body[:1200], re.IGNORECASE):
            score += 1
        return max(0, min(5, score))

    def _score_image_keyword_relevance(self, *, keyword: str, title: str, body: str, image_hint: str, image_type: str) -> int:
        keyword_tokens = self._keyword_tokens(keyword)
        if not keyword_tokens:
            return 35 if image_type in {"product", "install"} else 20
        title_text = str(title or "").lower()
        hint_text = str(image_hint or "").lower()
        body_text = str(body or "").lower()[:2500]
        matched = 0
        for token in keyword_tokens:
            if token in title_text:
                matched += 2
            elif token in hint_text:
                matched += 2
            elif token in body_text:
                matched += 1
        base = int((matched / max(1, len(keyword_tokens) * 2)) * 100)
        service_context = f"{keyword} {title} {body[:800]}".lower()
        if image_type in {"product", "install"}:
            base += 10
        if image_type == "install" and re.search(self.IMAGE_INSTALL_PATTERN, service_context, re.IGNORECASE):
            base = max(base, 55)
        if image_type == "product" and re.search(self.IMAGE_PRODUCT_PATTERN, service_context, re.IGNORECASE):
            base = max(base, 50)
        return max(0, min(100, base))

    def _keyword_tokens(self, keyword: str) -> list[str]:
        parts = [token.strip().lower() for token in re.findall(r"[가-힣A-Za-z0-9]{2,20}", str(keyword or ""))]
        stop = {"정리", "가이드", "비용", "후기", "추천", "비교", "방법"}
        seen: list[str] = []
        for token in parts:
            if token in stop:
                continue
            if token not in seen:
                seen.append(token)
        return seen[:6]

    def _classify_title_type(self, title: str) -> str:
        text = str(title or "").strip().lower()
        if re.search(self.QUESTION_TITLE_PATTERN, text, re.IGNORECASE):
            return "question"
        if re.search(self.LIST_TITLE_PATTERN, text, re.IGNORECASE):
            return "list"
        if re.search(self.COMPARISON_PATTERN, text, re.IGNORECASE):
            return "comparison"
        if re.search(self.REVIEW_PATTERN, text, re.IGNORECASE):
            return "review"
        if re.search(self.GUIDE_PATTERN, text, re.IGNORECASE):
            return "guide"
        return "general"

    def _classify_structure_type(
        self,
        *,
        body: str,
        faq_structure: bool,
        review_hits: int,
        comparison_hits: int,
        guide_hits: int,
        cta_present: bool,
        heading_count: int,
        list_count: int,
        news_hits: int,
    ) -> str:
        text = str(body or "")
        if faq_structure:
            return "faq"
        if news_hits >= 2:
            return "news"
        if comparison_hits >= 2:
            return "comparison"
        if review_hits >= 2:
            return "review"
        if guide_hits >= 2:
            return "guide"
        if cta_present:
            return "promotional"
        if list_count >= 3:
            return "listicle"
        if heading_count >= 3 and len(text) >= 1000:
            return "guide"
        return "informational"

    def _score_quality(
        self,
        *,
        length: int,
        topics: list[str],
        structure_type: str,
        cta_present: bool,
        heading_count: int,
        list_count: int,
        repeated_ratio: float,
        unique_token_ratio: float,
        boilerplate_hits: int,
        paragraph_count: int,
    ) -> int:
        score = 2
        if length >= 600:
            score += 1
        if length >= 1500:
            score += 1
        if len(topics) >= 1 and topics[0] != "일반":
            score += 1
        if structure_type in {"faq", "comparison", "guide", "review"}:
            score += 1
        if heading_count >= 3:
            score += 1
        if list_count >= 2:
            score += 1
        if paragraph_count < 2:
            score -= 1
        if repeated_ratio >= 0.3:
            score -= 1
        if unique_token_ratio < 0.28:
            score -= 1
        if boilerplate_hits >= 3:
            score -= 2
        if cta_present and score > 2:
            score -= 1
        return max(1, min(5, score))

    def _score_commercial_intent(
        self,
        *,
        commercial_hits: int,
        cta_hits: int,
        review_hits: int,
        price_hits: int,
        contact_hits: int,
        promo_hits: int,
    ) -> int:
        score = 1
        score += min(2, commercial_hits)
        score += min(2, cta_hits)
        score += min(1, price_hits)
        score += min(2, contact_hits)
        score += min(2, promo_hits)
        if review_hits and commercial_hits:
            score += 1
        return max(1, min(5, score))

    def _score_writing_fit(
        self,
        *,
        length: int,
        quality: int,
        commercial_intent: int,
        faq_structure: bool,
        structure_type: str,
        topic_count: int,
        heading_count: int,
        boilerplate_hits: int,
        repeated_ratio: float,
        summary_density: float,
        noise_hits: int,
    ) -> int:
        score = quality
        if length < 500:
            score -= 1
        if commercial_intent >= 4:
            score -= 2
        elif commercial_intent == 3:
            score -= 1
        if faq_structure or structure_type in {"comparison", "guide", "review"}:
            score += 1
        if heading_count >= 3:
            score += 1
        if summary_density < 0.18:
            score -= 1
        if repeated_ratio >= 0.35:
            score -= 1
        if boilerplate_hits >= 2:
            score -= 1
        if noise_hits >= 3:
            score -= 1
        if topic_count == 0:
            score -= 1
        return max(1, min(5, score))

    def _score_confidence(
        self,
        *,
        length: int,
        title_type: str,
        structure_type: str,
        topic_count: int,
        faq_structure: bool,
        cta_present: bool,
        heading_count: int,
        list_count: int,
        repeated_ratio: float,
        unique_token_ratio: float,
    ) -> int:
        score = 2
        if length >= 800:
            score += 1
        if title_type != "general":
            score += 1
        if structure_type != "informational":
            score += 1
        if topic_count:
            score += 1
        if heading_count >= 2 or list_count >= 2:
            score += 1
        if faq_structure:
            score += 1
        if repeated_ratio >= 0.35:
            score -= 2
        elif repeated_ratio >= 0.2:
            score -= 1
        if unique_token_ratio < 0.22:
            score -= 1
        if cta_present and score > 2:
            score -= 1
        return max(1, min(5, score))

    def _paragraphs(self, body: str) -> list[str]:
        chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", str(body or "")) if chunk.strip()]
        return chunks

    def _repeated_line_ratio(self, body: str) -> float:
        lines = [re.sub(r"\s+", " ", line).strip().lower() for line in str(body or "").splitlines() if line.strip()]
        if not lines:
            return 0.0
        unique = len(set(lines))
        return max(0.0, min(1.0, 1.0 - (unique / max(1, len(lines)))))

    def _unique_token_ratio(self, body: str) -> float:
        tokens = re.findall(r"[0-9A-Za-z가-힣]{2,}", str(body or "").lower())
        if not tokens:
            return 0.0
        return len(set(tokens)) / max(1, len(tokens))

    def _summary_density(self, body: str) -> float:
        tokens = re.findall(r"[0-9A-Za-z가-힣]{2,}", str(body or ""))
        paragraphs = self._paragraphs(body)
        if not tokens or not paragraphs:
            return 0.0
        return min(1.0, len(tokens) / max(1, len(paragraphs) * 120))

    def _merge_ai_content_label(self, base: dict, enriched: dict) -> dict:
        merged = dict(base)
        topics = enriched.get("topics")
        if isinstance(topics, list):
            merged["topics"] = [str(item).strip() for item in topics if str(item).strip()][:5] or merged["topics"]
        for key in ("tone", "sentiment", "structure_type", "title_type"):
            value = str(enriched.get(key) or "").strip()
            if value:
                merged[key] = value
        for key in ("commercial_intent", "writing_fit_score", "quality_score"):
            value = _to_int(enriched.get(key), merged.get(key, 0))
            merged[key] = max(0 if key == "commercial_intent" else 1, min(5, value))
        for key in ("cta_present", "faq_structure"):
            if key in enriched:
                merged[key] = self._to_boolish(enriched.get(key))
        confidence = float(enriched.get("confidence") or 0)
        if confidence > 0:
            merged["confidence"] = max(1, min(5, int(round(confidence * 5.0))))
        return merged

    def _merge_ai_image_label(self, base: dict, enriched: dict) -> dict:
        merged = dict(base)
        for key in ("category", "mood", "image_type"):
            value = str(enriched.get(key) or "").strip()
            if value:
                merged[key] = value
        tags = enriched.get("subject_tags")
        if isinstance(tags, list):
            merged["subject_tags"] = [str(item).strip() for item in tags if str(item).strip()][:12] or merged.get("subject_tags", [])
        if "text_overlay" in enriched:
            merged["text_overlay"] = self._to_boolish(enriched.get("text_overlay"))
        if "is_thumbnail_candidate" in enriched:
            merged["is_thumbnail_candidate"] = self._to_boolish(enriched.get("is_thumbnail_candidate"))
        merged["thumbnail_score"] = max(0, min(100, _to_int(enriched.get("thumbnail_score"), merged.get("thumbnail_score", 0))))
        merged["quality_score"] = max(1, min(5, _to_int(enriched.get("quality_score"), merged.get("quality_score", 3))))
        merged["commercial_intent"] = max(0, min(5, _to_int(enriched.get("commercial_intent"), merged.get("commercial_intent", 0))))
        merged["keyword_relevance_score"] = max(0, min(100, _to_int(enriched.get("keyword_relevance_score"), merged.get("keyword_relevance_score", 0))))
        confidence = float(enriched.get("confidence") or 0)
        if confidence > 0:
            merged["confidence"] = max(1, min(5, int(round(confidence * 5.0))))
        return merged

    def _to_boolish(self, value) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "y", "on", "있음"}:
            return True
        if text in {"0", "false", "no", "n", "off", "없음"}:
            return False
        return bool(text)

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


