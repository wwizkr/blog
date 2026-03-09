from __future__ import annotations

from collections import Counter
import json
import os
import re
import requests

from seo_profile.service import keyword_seo_profile_service
from storage.repositories import (
    AppSettingRepository,
    AIProviderRepository,
    ArticleRepository,
    ArticleTemplateRepository,
    CrawlRepository,
    KeywordSeoProfileRepository,
    PersonaRepository,
    WritingChannelRepository,
)
from core.settings_keys import WriterSettingKeys


class WriterService:
    _review_token_re = re.compile(r"[0-9A-Za-z가-힣]{2,}")
    _review_stopwords = {"그리고", "그러나", "대한", "관련", "있는", "하는", "입니다", "그런", "이런"}

    def generate_draft(
        self,
        persona_id: int,
        template_id: int,
        source_limit: int = 5,
        writing_channel_id: int | None = None,
        ai_provider_id: int | None = None,
    ) -> dict:
        persona = PersonaRepository.get_by_id(persona_id)
        if not persona or not persona.is_active:
            raise ValueError("사용 가능한 페르소나를 선택하세요.")

        template = ArticleTemplateRepository.get_by_id(template_id)
        if not template or not template.is_active:
            raise ValueError("사용 가능한 템플릿을 선택하세요.")

        source_rows = CrawlRepository.list_recent_contents_for_writer(source_limit)
        if not source_rows:
            raise ValueError("생성 가능한 원문 데이터가 없습니다. 먼저 수집을 실행하세요.")

        return self._generate_article(
            persona=persona,
            template=template,
            source_rows=source_rows,
            writing_channel_id=writing_channel_id,
            ai_provider_id=ai_provider_id,
        )

    def regenerate_article(self, article_id: int, ai_provider_id: int | None = None) -> dict:
        article = ArticleRepository.get_by_id(article_id)
        if not article:
            raise ValueError("재생성할 글을 찾을 수 없습니다.")
        if str(getattr(article, "status", "") or "").lower() == "published":
            raise ValueError("발행완료 글은 직접 재생성할 수 없습니다. 복제 후 새 초안으로 관리하세요.")

        persona_id = getattr(article, "persona_id", None)
        template_id = getattr(article, "template_id", None)
        if not persona_id or not template_id:
            raise ValueError("이 글은 재생성에 필요한 페르소나/템플릿 정보가 없습니다.")

        persona = PersonaRepository.get_by_id(int(persona_id))
        if not persona or not persona.is_active:
            raise ValueError("재생성에 사용할 페르소나가 없거나 비활성 상태입니다.")
        template = ArticleTemplateRepository.get_by_id(int(template_id))
        if not template or not template.is_active:
            raise ValueError("재생성에 사용할 템플릿이 없거나 비활성 상태입니다.")

        source_ids = self._parse_source_content_ids(getattr(article, "source_content_ids", None))
        source_rows = CrawlRepository.get_contents_by_ids(source_ids)
        if not source_rows:
            fallback_limit = max(3, min(12, len(source_ids) or 5))
            source_rows = CrawlRepository.list_recent_contents_for_writer(fallback_limit)
        if not source_rows:
            raise ValueError("재생성에 사용할 원문 데이터가 없습니다.")

        writing_channel_id = getattr(article, "writing_channel_id", None)
        provider_id = ai_provider_id or getattr(article, "ai_provider_id", None)
        result = self._generate_article(
            persona=persona,
            template=template,
            source_rows=source_rows,
            writing_channel_id=int(writing_channel_id) if writing_channel_id else None,
            ai_provider_id=int(provider_id) if provider_id else None,
            persist=False,
        )

        ArticleRepository.replace_generated(
            article_id=article.id,
            title=result["title"],
            content=result["content"],
            persona_id=persona.id,
            persona_name=persona.name,
            template_id=template.id,
            template_name=template.name,
            template_version=template.version,
            writing_channel_id=int(writing_channel_id) if writing_channel_id else None,
            ai_provider_id=int(result.get("ai_provider_id") or 0) or None,
            source_content_ids=[row.id for row in source_rows],
            generation_meta=result.get("generation_meta") or {},
            status="draft",
        )
        result["id"] = int(article.id)
        result["regenerated"] = True
        return result

    def _generate_article(
        self,
        persona,
        template,
        source_rows: list,
        writing_channel_id: int | None = None,
        ai_provider_id: int | None = None,
        persist: bool = True,
    ) -> dict:

        channel = WritingChannelRepository.get_by_id(writing_channel_id) if writing_channel_id else None
        if not ai_provider_id:
            ai_provider_id = self._resolve_default_provider_id()
        provider = AIProviderRepository.get_by_id(ai_provider_id) if ai_provider_id else None
        keyword = source_rows[0].keyword or "콘텐츠"
        seo_profile, seo_keyword, seo_auto_analyzed = self._ensure_keyword_seo_profile(source_rows)
        target_channel = channel.display_name if channel else template.template_type
        format_type = self._resolve_format_type(template.template_type, channel.channel_type if channel else None)
        seo_notes = self._build_seo_notes(seo_profile, seo_keyword or keyword)
        context = {
            "persona_name": persona.name,
            "persona_age_group": persona.age_group or "미정",
            "persona_gender": persona.gender or "미정",
            "persona_personality": persona.personality or "보통",
            "persona_interests": persona.interests or "",
            "persona_speech_style": persona.speech_style or "설명형",
            "persona_tone": persona.tone or "정보형",
            "persona_style": persona.style_guide or "",
            "persona_banned_words": persona.banned_words or "",
            "keyword": keyword,
            "source_summary": self._build_source_summary(source_rows),
            "source_outline": self._build_source_outline(source_rows),
            "image_plan": self._build_image_plan(source_rows, seo_profile),
            "image_slots": self._build_image_slots(source_rows, seo_profile),
            "seo_brief": seo_notes["brief"],
            "seo_strategy": seo_notes["strategy"],
            "seo_metrics": seo_notes["metrics"],
            "seo_format": seo_profile.dominant_format if seo_profile else "",
            "seo_length_range": self._format_length_range(seo_profile),
            "seo_common_sections": ", ".join(seo_profile.common_sections[:8]) if seo_profile else "",
            "seo_common_terms": ", ".join(seo_profile.common_terms[:10]) if seo_profile else "",
            "target_channel": target_channel,
            "channel_code": channel.code if channel else "",
            "channel_type": channel.channel_type if channel else template.template_type,
            "ai_provider": provider.provider if provider else "",
            "ai_model": provider.model_name if provider else "",
        }
        generation_meta = self._build_generation_meta(
            keyword=seo_keyword or keyword,
            channel=channel,
            provider=provider,
            source_rows=source_rows,
            seo_notes=seo_notes,
        )

        title = self._build_title(format_type, persona.name, keyword, template.name)
        rendered_prompt = self._render_template(template.user_prompt, context)
        content = self._generate_content(
            provider=provider,
            template=template,
            context=context,
            rendered_prompt=rendered_prompt,
            fallback_title=title,
        )
        content = self._ensure_image_slots_in_content(
            content=content,
            image_slots=context.get("image_slots", ""),
            channel_type=(channel.channel_type if channel else template.template_type),
        )
        article_id = None
        if persist:
            article_id = ArticleRepository.add(
                title=title,
                content=content,
                format_type=format_type,
                persona_id=persona.id,
                persona_name=persona.name,
                template_id=template.id,
                template_name=template.name,
                template_version=template.version,
                writing_channel_id=channel.id if channel else None,
                ai_provider_id=provider.id if provider else None,
                source_content_ids=[row.id for row in source_rows],
                generation_meta=generation_meta,
            )
        return {
            "id": article_id,
            "title": title,
            "content": content,
            "format_type": format_type,
            "seo_profile_used": bool(seo_profile),
            "seo_profile_auto_analyzed": bool(seo_auto_analyzed),
            "seo_keyword": seo_keyword or keyword,
            "writing_channel_id": channel.id if channel else None,
            "ai_provider_id": provider.id if provider else None,
            "generation_meta": generation_meta,
        }

    def review_article(self, article) -> dict:
        if not article:
            return self._empty_review()
        source_rows = self._source_rows_for_article(article)
        seo_profile, seo_keyword, _ = self._ensure_keyword_seo_profile(source_rows)
        if not seo_profile:
            review = self._empty_review()
            review["keyword"] = seo_keyword or ""
            review["flags"] = ["SEO 패턴 없음"]
            review["recommendations"] = ["먼저 이 키워드의 상위 글을 더 수집하고 SEO 패턴 분석을 실행하세요."]
            return review
        body = self._strip_control_guides(str(getattr(article, "content", "") or ""))
        length_score = self._score_length(body, seo_profile)
        heading_score = self._score_headings(body, seo_profile)
        section_score, section_flags = self._score_sections(body, seo_profile)
        term_score, term_flags = self._score_terms(body, seo_profile)
        strategy_score, strategy_flags = self._score_strategy(body, seo_profile)
        total = max(0, min(100, length_score + heading_score + section_score + term_score + strategy_score))
        flags = section_flags + term_flags + strategy_flags
        if length_score < 18:
            flags.append("권장 글자수 범위 재조정 필요")
        if heading_score < 12:
            flags.append("소제목 구조 보강 필요")
        if not flags:
            flags.append("주요 SEO 패턴 반영 양호")
        recommendations = self._build_review_recommendations(
            length_score=length_score,
            heading_score=heading_score,
            section_score=section_score,
            term_score=term_score,
            strategy_score=strategy_score,
            profile=seo_profile,
        )
        return {
            "score": int(total),
            "status": "양호" if total >= 80 else ("보통" if total >= 60 else "보완필요"),
            "flags": flags[:6],
            "recommendations": recommendations[:5],
            "keyword": seo_keyword or "",
            "length_score": int(length_score),
            "heading_score": int(heading_score),
            "section_score": int(section_score),
            "term_score": int(term_score),
            "strategy_score": int(strategy_score),
        }

    def _resolve_format_type(self, template_type: str, channel_type: str | None) -> str:
        ctype = (channel_type or "").strip().lower()
        if ctype in {"blog", "cms"}:
            return "blog"
        if ctype in {"sns", "longform"}:
            return "sns"
        if ctype in {"community", "board"}:
            return "board"
        return template_type

    def _build_title(self, format_type: str, persona_name: str, keyword: str, template_name: str) -> str:
        if format_type == "sns":
            return f"{keyword} 핵심 요약 | {persona_name} | {template_name}"
        if format_type == "board":
            return f"[정보공유] {keyword} 정리 ({persona_name}) - {template_name}"
        return f"{keyword} 가이드 및 인사이트 ({persona_name}) - {template_name}"

    def _build_source_summary(self, rows: list) -> str:
        lines: list[str] = []
        for idx, row in enumerate(rows, 1):
            lines.append(f"{idx}. {row.title}")
            lines.append(f"   - 출처: {row.source_url}")
        return "\n".join(lines)

    def _build_source_outline(self, rows: list) -> str:
        chunks: list[str] = []
        for idx, row in enumerate(rows, 1):
            body = re.sub(r"\s+", " ", str(getattr(row, "body_text", "") or "")).strip()
            if len(body) > 280:
                body = f"{body[:280].rstrip()}..."
            author = str(getattr(row, "author", "") or "").strip()
            prefix = f"{idx}. {row.title}"
            if author:
                prefix += f" | 작성자: {author}"
            chunks.append(prefix)
            if body:
                chunks.append(f"   - 요약: {body}")
        return "\n".join(chunks)

    def _select_candidate_images(self, rows: list, max_count: int = 8) -> list:
        preferred: list = []
        candidates: list = []
        seen_sources: set[str] = set()
        for row in rows:
            images = list(getattr(row, "images", None) or [])
            images.sort(
                key=lambda item: (
                    1 if getattr(item, "local_path", None) else 0,
                    int(getattr(item, "keyword_relevance_score", 0) or 0),
                    1 if getattr(item, "is_thumbnail_candidate", False) else 0,
                    int(getattr(item, "thumbnail_score", 0) or 0),
                    -int(getattr(item, "commercial_intent", 0) or 0),
                    0 if getattr(item, "text_overlay", False) else 1,
                ),
                reverse=True,
            )
            for image in images:
                if not getattr(image, "local_path", None):
                    continue
                bundle = (row, image)
                relevance = int(getattr(image, "keyword_relevance_score", 0) or 0)
                commercial = int(getattr(image, "commercial_intent", 0) or 0)
                image_type = str(getattr(image, "image_type", "") or "")
                if relevance >= 40 and commercial <= 3 and image_type not in {"banner", "document", "screenshot"}:
                    preferred.append(bundle)
        for row, image in preferred:
            source_key = str(getattr(image, "source_url", "") or "").strip()
            if source_key and source_key in seen_sources:
                continue
            if source_key:
                seen_sources.add(source_key)
            candidates.append((row, image))
            if len(candidates) >= max_count:
                return candidates
        return candidates

    def _build_image_plan(self, rows: list, profile) -> str:
        recommended = int(getattr(profile, "recommended_image_count", None) or 0) if profile else 0
        candidates = self._select_candidate_images(rows, max_count=max(3, min(8, recommended or 5)))
        if not candidates:
            return "키워드 적합도 기준을 통과한 로컬 이미지가 없습니다. 이미지 없이도 자연스럽게 읽히는 본문 구조를 우선 작성하세요."
        lines = [f"사용 가능한 로컬 이미지 후보 {len(candidates)}장"]
        if recommended > 0:
            lines.append(f"권장 이미지 수는 약 {recommended}장입니다.")
        for idx, (row, image) in enumerate(candidates, 1):
            thumb = int(getattr(image, "thumbnail_score", 0) or 0)
            relevance = int(getattr(image, "keyword_relevance_score", 0) or 0)
            image_type = str(getattr(image, "image_type", "") or "")
            commercial = int(getattr(image, "commercial_intent", 0) or 0)
            overlay = "텍스트포함" if getattr(image, "text_overlay", False) else "텍스트없음"
            lines.append(f"{idx}. image_id={image.id} | source={row.title} | type={image_type or '-'} | relevance={relevance} | thumb={thumb} | commercial={commercial} | {overlay}")
        return "\n".join(lines)

    def _build_image_slots(self, rows: list, profile) -> str:
        recommended = int(getattr(profile, "recommended_image_count", None) or 0) if profile else 0
        candidates = self._select_candidate_images(rows, max_count=max(3, min(8, recommended or 5)))
        if not candidates:
            return ""
        lines: list[str] = []
        for idx, (row, image) in enumerate(candidates, 1):
            placement = "대표 이미지" if idx == 1 else f"본문 이미지 {idx - 1}"
            lines.append(f"[[IMAGE:{image.id}]] - {placement} - {row.title}")
        return "\n".join(lines)

    def _build_generation_meta(self, *, keyword: str, channel, provider, source_rows: list, seo_notes: dict[str, str]) -> dict:
        image_ids: list[int] = []
        for row in source_rows:
            for image in list(getattr(row, "images", None) or []):
                image_id = int(getattr(image, "id", 0) or 0)
                if image_id > 0:
                    image_ids.append(image_id)
        selected_image_ids: list[int] = []
        for _row, image in self._select_candidate_images(source_rows, max_count=8):
            image_id = int(getattr(image, "id", 0) or 0)
            if image_id > 0:
                selected_image_ids.append(image_id)
        return {
            "keyword": keyword,
            "channel_name": getattr(channel, "display_name", "") if channel else "",
            "channel_type": getattr(channel, "channel_type", "") if channel else "",
            "ai_provider": getattr(provider, "provider", "") if provider else "",
            "ai_model": getattr(provider, "model_name", "") if provider else "",
            "seo_strategy": str(seo_notes.get("strategy") or ""),
            "seo_metrics": str(seo_notes.get("metrics") or ""),
            "seo_brief": str(seo_notes.get("brief") or ""),
            "source_ids": [int(getattr(row, "id", 0) or 0) for row in source_rows if getattr(row, "id", None)],
            "image_ids": image_ids,
            "selected_image_ids": selected_image_ids,
        }

    def _parse_source_content_ids(self, raw_value) -> list[int]:
        if raw_value is None:
            return []
        try:
            values = json.loads(str(raw_value))
        except Exception:
            values = []
        result: list[int] = []
        for value in values if isinstance(values, list) else []:
            try:
                result.append(int(value))
            except (TypeError, ValueError):
                continue
        return result

    def _ensure_keyword_seo_profile(self, source_rows: list) -> tuple[object | None, str | None, bool]:
        keyword_counter: Counter[int] = Counter()
        keyword_names: dict[int, str] = {}
        for row in source_rows:
            keyword_id = getattr(row, "keyword_id", None)
            if not keyword_id:
                continue
            keyword_counter[int(keyword_id)] += 1
            if getattr(row, "keyword", None):
                keyword_names[int(keyword_id)] = str(row.keyword)
        if not keyword_counter:
            return None, None, False
        keyword_id = keyword_counter.most_common(1)[0][0]
        profile = KeywordSeoProfileRepository.get_by_keyword_id(keyword_id)
        auto_analyzed = False
        if not profile:
            try:
                keyword_seo_profile_service.analyze_keyword(keyword_id=keyword_id, sample_limit=12)
                profile = KeywordSeoProfileRepository.get_by_keyword_id(keyword_id)
                auto_analyzed = profile is not None
            except Exception:
                profile = None
        return profile, keyword_names.get(keyword_id), auto_analyzed

    def _format_length_range(self, profile) -> str:
        if not profile:
            return ""
        low = getattr(profile, "recommended_length_min", None)
        high = getattr(profile, "recommended_length_max", None)
        if low and high:
            return f"{low}~{high}자"
        return ""

    def _build_seo_notes(self, profile, keyword: str) -> dict[str, str]:
        if not profile:
            return {"brief": "", "strategy": "", "metrics": ""}
        metric_parts: list[str] = [f"키워드 '{keyword}' 상위 글 패턴 기준"]
        length_range = self._format_length_range(profile)
        if length_range:
            metric_parts.append(f"권장 글자수 {length_range}")
        if getattr(profile, "recommended_heading_count", None) is not None:
            metric_parts.append(f"권장 소제목 {profile.recommended_heading_count}개")
        if getattr(profile, "recommended_image_count", None) is not None:
            metric_parts.append(f"권장 이미지 {profile.recommended_image_count}개")
        if getattr(profile, "dominant_format", None):
            metric_parts.append(f"대표 형식 {profile.dominant_format}")
        sections = ", ".join((getattr(profile, "common_sections", None) or [])[:6])
        if sections:
            metric_parts.append(f"자주 보이는 섹션: {sections}")
        terms = ", ".join((getattr(profile, "common_terms", None) or [])[:8])
        if terms:
            metric_parts.append(f"핵심 표현: {terms}")
        strategy, summary = self._split_seo_summary(str(getattr(profile, "summary_text", "") or "").strip())
        brief_parts = []
        if strategy:
            brief_parts.append(strategy)
        metrics = " / ".join(metric_parts)
        if metrics:
            brief_parts.append(metrics)
        if summary and summary != strategy:
            brief_parts.append(summary)
        return {
            "brief": " / ".join([part for part in brief_parts if part]),
            "strategy": strategy,
            "metrics": metrics,
        }

    def _split_seo_summary(self, summary_text: str) -> tuple[str, str]:
        text = str(summary_text or "").strip()
        if not text:
            return "", ""
        marker = "AI 해석:"
        if marker not in text:
            return "", text
        base, ai = text.split(marker, 1)
        return ai.strip(), base.strip()

    def _resolve_default_provider_id(self) -> int | None:
        raw = AppSettingRepository.get_value(WriterSettingKeys.DEFAULT_AI_PROVIDER_ID, "")
        try:
            value = int(str(raw or "").strip())
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def _source_rows_for_article(self, article) -> list:
        raw = getattr(article, "source_content_ids", None)
        try:
            ids = json.loads(str(raw or "[]"))
        except Exception:
            ids = []
        if not isinstance(ids, list):
            ids = []
        return CrawlRepository.get_contents_by_ids(ids[:30])

    def _empty_review(self) -> dict:
        return {
            "score": 0,
            "status": "기준없음",
            "flags": ["검수 불가"],
            "recommendations": [],
            "keyword": "",
            "length_score": 0,
            "heading_score": 0,
            "section_score": 0,
            "term_score": 0,
            "strategy_score": 0,
        }

    def _build_review_recommendations(
        self,
        *,
        length_score: int,
        heading_score: int,
        section_score: int,
        term_score: int,
        strategy_score: int,
        profile,
    ) -> list[str]:
        recommendations: list[str] = []
        length_range = self._format_length_range(profile)
        if length_score < 18:
            recommendations.append(f"본문 분량을 {length_range or '권장 범위'}에 맞게 늘리거나 줄이세요.")
        recommended_headings = int(getattr(profile, "recommended_heading_count", None) or 0)
        if heading_score < 12 and recommended_headings > 0:
            recommendations.append(f"소제목을 약 {recommended_headings}개 기준으로 다시 구성하세요.")
        sections = ", ".join((getattr(profile, "common_sections", None) or [])[:3])
        if section_score < 12 and sections:
            recommendations.append(f"본문에 `{sections}` 같은 핵심 섹션을 명시적으로 넣으세요.")
        terms = ", ".join((getattr(profile, "common_terms", None) or [])[:5])
        if term_score < 7 and terms:
            recommendations.append(f"핵심 표현 `{terms}`를 자연스럽게 본문에 포함하세요.")
        strategy, _ = self._split_seo_summary(str(getattr(profile, "summary_text", "") or ""))
        if strategy_score < 6 and strategy:
            recommendations.append(f"AI 전략 해석 기준으로 다음 방향을 더 반영하세요: {strategy[:120]}")
        if not recommendations:
            recommendations.append("현재 글은 주요 SEO 패턴을 잘 반영하고 있습니다.")
        return recommendations

    def _strip_control_guides(self, content: str) -> str:
        text = str(content or "")
        text = re.sub(r"^\[SEO 패턴 가이드\].*?(?:\n\n|\Z)", "", text, flags=re.S)
        text = re.sub(r"^\[작성 채널:.*?(?:\n\n|\Z)", "", text, flags=re.S)
        return text.strip()

    def _score_length(self, body: str, profile) -> int:
        length = len(re.sub(r"\s+", "", str(body or "")))
        low = getattr(profile, "recommended_length_min", None) or 0
        high = getattr(profile, "recommended_length_max", None) or 0
        if low and high and low <= length <= high:
            return 30
        if low and length < low:
            return max(0, 30 - int(((low - length) / max(1, low)) * 30))
        if high and length > high:
            return max(0, 30 - int(((length - high) / max(1, high)) * 20))
        return 15 if length > 0 else 0

    def _score_headings(self, body: str, profile) -> int:
        recommended = int(getattr(profile, "recommended_heading_count", None) or 0)
        count = len(re.findall(r"(?m)^\s*#{1,6}\s+", str(body or "")))
        if recommended <= 0:
            return 10 if count > 0 else 0
        return max(0, 20 - abs(count - recommended) * 4)

    def _score_sections(self, body: str, profile) -> tuple[int, list[str]]:
        sections = [str(v).strip() for v in (getattr(profile, "common_sections", None) or [])[:4] if str(v).strip()]
        if not sections:
            return 10, []
        hay = str(body or "").lower()
        matched = sum(1 for section in sections if section.lower() in hay)
        return int(round((matched / len(sections)) * 25)), ([] if matched >= max(1, len(sections) // 2) else ["자주 보이는 섹션 반영 부족"])

    def _score_terms(self, body: str, profile) -> tuple[int, list[str]]:
        terms = [str(v).strip() for v in (getattr(profile, "common_terms", None) or [])[:6] if str(v).strip()]
        if not terms:
            return 8, []
        hay = str(body or "").lower()
        matched = sum(1 for term in terms if term.lower() in hay)
        return int(round((matched / len(terms)) * 15)), ([] if matched >= max(2, len(terms) // 3) else ["핵심 표현 활용 부족"])

    def _score_strategy(self, body: str, profile) -> tuple[int, list[str]]:
        strategy, _ = self._split_seo_summary(str(getattr(profile, "summary_text", "") or ""))
        tokens = self._strategy_tokens(strategy)
        if not tokens:
            return 5, []
        hay = str(body or "").lower()
        matched = sum(1 for token in tokens if token in hay)
        needed = max(1, min(4, len(tokens)))
        return int(round((min(matched, needed) / needed) * 10)), ([] if matched >= needed else ["AI 전략 해석 반영 약함"])

    def _strategy_tokens(self, text: str) -> list[str]:
        seen: set[str] = set()
        tokens: list[str] = []
        for raw in self._review_token_re.findall(str(text or "").lower()):
            token = raw.strip()
            if token in self._review_stopwords or len(token) < 2 or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
            if len(tokens) >= 8:
                break
        return tokens

    def _render_template(self, template_text: str, context: dict[str, str]) -> str:
        rendered = template_text
        for key, value in context.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)
        return rendered

    def _generate_content(self, *, provider, template, context: dict[str, str], rendered_prompt: str, fallback_title: str) -> str:
        image_slots = str(context.get("image_slots", "") or "").strip()
        if image_slots:
            rendered_prompt = (
                f"{rendered_prompt}\n\n"
                "[이미지 슬롯 사용 규칙]\n"
                "- 아래 슬롯은 이미 다운로드된 로컬 이미지를 가리킵니다.\n"
                "- 관련성이 높은 경우에만 본문에 그대로 삽입하세요.\n"
                "- 슬롯 문자열은 수정하거나 새로 만들지 마세요.\n"
                f"{image_slots}"
            )
        if provider:
            generated = self._generate_with_provider(provider=provider, template=template, rendered_prompt=rendered_prompt)
            if generated:
                return generated
        return self._build_fallback_article(
            title=fallback_title,
            prompt=rendered_prompt,
            source_summary=context.get("source_summary", ""),
            source_outline=context.get("source_outline", ""),
            seo_strategy=context.get("seo_strategy", ""),
            seo_metrics=context.get("seo_metrics", ""),
            image_plan=context.get("image_plan", ""),
            image_slots=context.get("image_slots", ""),
        )

    def _generate_with_provider(self, *, provider, template, rendered_prompt: str) -> str:
        provider_name = str(getattr(provider, "provider", "") or "").strip().lower()
        alias = str(getattr(provider, "api_key_alias", "") or "").strip()
        api_key = os.getenv(alias) if alias else ""
        if not api_key:
            return ""
        system_prompt = str(getattr(template, "system_prompt", "") or "").strip() or (
            "당신은 한국어 콘텐츠 작성자입니다. 자연스럽고 완성된 본문만 출력하세요. "
            "메타 설명이나 프롬프트 해설 없이 최종 글만 작성하세요."
        )
        if provider_name == "openai":
            return self._generate_with_openai(
                api_key=api_key,
                model_name=str(getattr(provider, "model_name", "") or ""),
                system_prompt=system_prompt,
                rendered_prompt=rendered_prompt,
            )
        if provider_name in {"google", "gemini"}:
            return self._generate_with_gemini(
                api_key=api_key,
                model_name=str(getattr(provider, "model_name", "") or ""),
                system_prompt=system_prompt,
                rendered_prompt=rendered_prompt,
            )
        return ""

    def _generate_with_openai(self, *, api_key: str, model_name: str, system_prompt: str, rendered_prompt: str) -> str:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model_name,
                "temperature": 0.7,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": rendered_prompt},
                ],
            },
            timeout=90,
        )
        response.raise_for_status()
        result = response.json()
        content = str((((result.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()
        return self._clean_generated_content(content)

    def _generate_with_gemini(self, *, api_key: str, model_name: str, system_prompt: str, rendered_prompt: str) -> str:
        prompt = f"{system_prompt}\n\n{rendered_prompt}"
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=90,
        )
        response.raise_for_status()
        result = response.json()
        candidates = result.get("candidates") or []
        parts = (((candidates[0] if candidates else {}).get("content") or {}).get("parts") or [])
        content = "".join(str(part.get("text") or "") for part in parts).strip()
        return self._clean_generated_content(content)

    def _clean_generated_content(self, content: str) -> str:
        text = str(content or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    def _extract_slot_tokens(self, image_slots: str) -> list[str]:
        lines: list[str] = []
        for raw in str(image_slots or "").splitlines():
            text = str(raw).strip()
            if text.startswith("[[IMAGE:"):
                lines.append(text)
        return lines

    def _ensure_image_slots_in_content(self, *, content: str, image_slots: str, channel_type: str | None) -> str:
        ctype = str(channel_type or "").strip().lower()
        if ctype not in {"blog", "cms", "board"}:
            return content
        text = str(content or "").strip()
        slots = self._extract_slot_tokens(image_slots)
        if not text or not slots or "[[IMAGE:" in text:
            return text
        blocks = text.split("\n\n")
        if len(blocks) < 3:
            return f"{text}\n\n{slots[0]}"
        first_insert_at = 2 if len(blocks) > 2 else len(blocks)
        blocks.insert(first_insert_at, slots[0])
        if len(slots) > 1 and len(blocks) > 5:
            second_insert_at = min(len(blocks) - 1, max(4, len(blocks) // 2))
            blocks.insert(second_insert_at, slots[1])
        return "\n\n".join(blocks).strip()

    def _build_fallback_article(
        self,
        *,
        title: str,
        prompt: str,
        source_summary: str,
        source_outline: str,
        seo_strategy: str,
        seo_metrics: str,
        image_plan: str,
        image_slots: str,
    ) -> str:
        parts = [
            f"# {title}",
            "",
            "## 작성 방향",
            seo_strategy or "핵심 정보를 먼저 정리하고 독자의 의문을 순서대로 해소합니다.",
            "",
            "## SEO 기준",
            seo_metrics or "상위 글 패턴 기준으로 소제목 구조와 핵심 표현을 유지합니다.",
            "",
            "## 원문 개요",
            source_outline or source_summary,
            "",
            "## 참고 자료",
            source_summary or prompt,
            "",
            "## 이미지 계획",
            image_plan or "이미지 없이도 읽히는 구조로 우선 작성합니다.",
            "",
            "## 예시 이미지 슬롯",
            image_slots or "(사용 가능한 이미지 슬롯 없음)",
            "",
            "## 초안 메모",
            "현재 AI 응답을 받지 못해 참고 자료 기반 초안으로 저장되었습니다. 본문을 보강하세요.",
        ]
        return "\n".join(parts).strip()


writer_service = WriterService()

