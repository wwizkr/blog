from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass

from bs4 import BeautifulSoup
import requests
from sqlalchemy import select

from core.settings_keys import WriterSettingKeys
from storage.database import init_database, session_scope
from storage.models import Keyword, RawContent, RawImage
from storage.repositories import AIProviderRepository, AppSettingRepository, KeywordSeoProfileRepository


@dataclass(frozen=True)
class KeywordSeoProfileResult:
    keyword_id: int
    sample_count: int


class KeywordSeoProfileService:
    _token_re = re.compile(r"[0-9A-Za-z가-힣]{2,}")
    _stopwords = {
        "정말", "이번", "관련", "대한", "에서", "으로", "입니다", "있는", "하는", "그리고", "그러나",
        "the", "and", "for", "with", "this", "that", "have", "from",
    }

    def analyze_keyword(self, keyword_id: int, sample_limit: int = 12) -> KeywordSeoProfileResult:
        init_database()
        with session_scope() as session:
            keyword = session.get(Keyword, keyword_id)
            if not keyword:
                raise ValueError("keyword not found")

            contents = session.execute(
                select(RawContent)
                .where(RawContent.keyword_id == keyword_id)
                .order_by(RawContent.created_at.desc())
                .limit(max(3, min(30, int(sample_limit or 12))))
            ).scalars().all()
            if not contents:
                raise ValueError("글 수집 후 분석이 가능합니다.")

            image_counts = {}
            if contents:
                content_ids = [int(row.id) for row in contents]
                image_rows = session.execute(
                    select(RawImage.content_id).where(RawImage.content_id.in_(content_ids))
                ).all()
                for (content_id,) in image_rows:
                    image_counts[int(content_id)] = image_counts.get(int(content_id), 0) + 1

        title_lengths: list[int] = []
        body_lengths: list[int] = []
        heading_counts: list[int] = []
        image_count_values: list[int] = []
        list_count_values: list[int] = []
        section_counter: Counter[str] = Counter()
        term_counter: Counter[str] = Counter()
        format_counter: Counter[str] = Counter()
        source_content_ids: list[int] = []

        for row in contents:
            title = str(row.title or "").strip()
            body_html = str(row.body_html or "").strip()
            raw_body_text = str(row.body_text or "").strip()
            body_text = self._to_plain_text(body_html or raw_body_text)
            title_lengths.append(len(title))
            body_lengths.append(len(body_text))
            image_count_values.append(int(image_counts.get(int(row.id), 0)))
            source_content_ids.append(int(row.id))

            heading_count = 0
            list_count = 0
            heading_texts: list[str] = []
            html_source = body_html or (raw_body_text if self._looks_like_html(raw_body_text) else "")
            if html_source:
                soup = BeautifulSoup(html_source, "html.parser")
                headings = soup.select("h1, h2, h3, h4")
                heading_count = len(headings)
                heading_texts = [self._clean_heading_text(node.get_text(" ", strip=True)) for node in headings]
                heading_texts = [text for text in heading_texts if text]
                list_count = len(soup.select("ul, ol")) + len(soup.select("li")) // 3
            else:
                heading_count = 0
                list_count = body_text.count("\n- ") + body_text.count("\n1.")
            heading_counts.append(heading_count)
            list_count_values.append(list_count)
            for section in heading_texts[:12]:
                section_counter[section] += 1
            for token in self._tokenize(f"{title} {body_text[:2500]}"):
                term_counter[token] += 1
            format_counter[self._classify_format(title=title, body_text=body_text, heading_texts=heading_texts)] += 1

        sample_count = len(contents)
        avg_title_length = self._avg_int(title_lengths)
        avg_body_length = self._avg_int(body_lengths)
        avg_heading_count = self._avg_int(heading_counts)
        avg_image_count = self._avg_int(image_count_values)
        avg_list_count = self._avg_int(list_count_values)
        common_sections = [name for name, _ in section_counter.most_common(8)]
        common_terms = [name for name, _ in term_counter.most_common(12)]
        dominant_format = format_counter.most_common(1)[0][0] if format_counter else "informational"
        recommended_length_min = self._percentile(body_lengths, 0.25)
        recommended_length_max = self._percentile(body_lengths, 0.75)
        recommended_heading_count = max(1, self._avg_int(heading_counts))
        recommended_image_count = max(0, self._avg_int(image_count_values))
        summary_text = (
            f"샘플 {sample_count}건 기준, 평균 본문 {avg_body_length}자 / 제목 {avg_title_length}자 / "
            f"소제목 {avg_heading_count}개 / 이미지 {avg_image_count}개 / 리스트 {avg_list_count}개. "
            f"주요 형식은 {dominant_format}."
        )
        ai_interpretation, ai_meta = self._build_ai_interpretation(
            keyword=str(getattr(keyword, "keyword", "") or ""),
            sample_count=sample_count,
            avg_title_length=avg_title_length,
            avg_body_length=avg_body_length,
            avg_heading_count=avg_heading_count,
            avg_image_count=avg_image_count,
            avg_list_count=avg_list_count,
            dominant_format=dominant_format,
            common_sections=common_sections,
            common_terms=common_terms,
            titles=[str(getattr(row, "title", "") or "").strip() for row in contents[:8]],
        )
        if ai_interpretation:
            summary_text = f"{summary_text}\n\nAI 해석: {ai_interpretation}"

        KeywordSeoProfileRepository.upsert(
            keyword_id=keyword_id,
            sample_count=sample_count,
            avg_title_length=avg_title_length,
            avg_body_length=avg_body_length,
            avg_heading_count=avg_heading_count,
            avg_image_count=avg_image_count,
            avg_list_count=avg_list_count,
            dominant_format=dominant_format,
            common_sections=common_sections,
            common_terms=common_terms,
            recommended_length_min=recommended_length_min,
            recommended_length_max=recommended_length_max,
            recommended_heading_count=recommended_heading_count,
            recommended_image_count=recommended_image_count,
            summary_text=summary_text,
            analysis_basis={
                "sample_limit": sample_limit,
                "channels": sorted({str(row.channel_code or "") for row in contents}),
                "ai_interpretation_enabled": bool(ai_interpretation),
                "ai_provider": ai_meta.get("provider") or "",
                "ai_model": ai_meta.get("model_name") or "",
            },
            source_content_ids=source_content_ids,
        )
        return KeywordSeoProfileResult(keyword_id=keyword_id, sample_count=sample_count)

    def _build_ai_interpretation(
        self,
        *,
        keyword: str,
        sample_count: int,
        avg_title_length: int,
        avg_body_length: int,
        avg_heading_count: int,
        avg_image_count: int,
        avg_list_count: int,
        dominant_format: str,
        common_sections: list[str],
        common_terms: list[str],
        titles: list[str],
    ) -> tuple[str, dict]:
        provider = self._pick_provider()
        if not provider:
            return "", {}
        try:
            prompt = self._build_ai_prompt(
                keyword=keyword,
                sample_count=sample_count,
                avg_title_length=avg_title_length,
                avg_body_length=avg_body_length,
                avg_heading_count=avg_heading_count,
                avg_image_count=avg_image_count,
                avg_list_count=avg_list_count,
                dominant_format=dominant_format,
                common_sections=common_sections,
                common_terms=common_terms,
                titles=titles,
            )
            provider_name = str(getattr(provider, "provider", "") or "").strip().lower()
            if provider_name == "openai":
                text = self._request_openai_summary(provider, prompt)
            else:
                text = self._request_gemini_summary(provider, prompt)
            return text.strip(), {
                "provider": str(getattr(provider, "provider", "") or ""),
                "model_name": str(getattr(provider, "model_name", "") or ""),
            }
        except Exception:
            return "", {}

    def _pick_provider(self):
        default_id = self._default_provider_id()
        if default_id:
            row = AIProviderRepository.get_by_id(default_id)
            if self._is_ready_provider(row):
                return row
        for row in AIProviderRepository.list_all(enabled_only=True):
            if self._is_ready_provider(row):
                return row
        return None

    def _default_provider_id(self) -> int | None:
        raw = AppSettingRepository.get_value(WriterSettingKeys.DEFAULT_AI_PROVIDER_ID, "")
        try:
            value = int(str(raw or "").strip())
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def _is_ready_provider(self, row) -> bool:
        if not row or not bool(getattr(row, "is_enabled", False)):
            return False
        provider_name = str(getattr(row, "provider", "") or "").strip().lower()
        if provider_name not in {"openai", "google", "gemini"}:
            return False
        alias = str(getattr(row, "api_key_alias", "") or "").strip()
        return bool(alias and os.getenv(alias))

    def _build_ai_prompt(
        self,
        *,
        keyword: str,
        sample_count: int,
        avg_title_length: int,
        avg_body_length: int,
        avg_heading_count: int,
        avg_image_count: int,
        avg_list_count: int,
        dominant_format: str,
        common_sections: list[str],
        common_terms: list[str],
        titles: list[str],
    ) -> str:
        section_text = ", ".join(common_sections[:8]) or "-"
        term_text = ", ".join(common_terms[:10]) or "-"
        title_text = " | ".join([title for title in titles if title][:6]) or "-"
        return (
            "한국어로만 답하세요. SEO 상위글 패턴을 해석해 작성 전략 요약 2~4문장만 작성하세요. "
            "숫자 반복 나열보다 무엇을 강조해야 하는지, 어떤 독자 의도를 충족하는지, 어떤 섹션 구성이 유리한지 중심으로 요약하세요.\n\n"
            f"키워드: {keyword}\n"
            f"샘플 수: {sample_count}\n"
            f"평균 제목 길이: {avg_title_length}\n"
            f"평균 본문 길이: {avg_body_length}\n"
            f"평균 소제목 수: {avg_heading_count}\n"
            f"평균 이미지 수: {avg_image_count}\n"
            f"평균 리스트 수: {avg_list_count}\n"
            f"대표 형식: {dominant_format}\n"
            f"자주 보이는 섹션: {section_text}\n"
            f"자주 보이는 표현: {term_text}\n"
            f"대표 제목 예시: {title_text}\n"
        )

    def _request_openai_summary(self, provider, prompt: str) -> str:
        api_key = os.getenv(str(provider.api_key_alias or "").strip())
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": provider.model_name,
                "temperature": 0.3,
                "messages": [
                    {"role": "system", "content": "Return only concise Korean prose."},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=45,
        )
        response.raise_for_status()
        result = response.json()
        return str((((result.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()

    def _request_gemini_summary(self, provider, prompt: str) -> str:
        api_key = os.getenv(str(provider.api_key_alias or "").strip())
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{provider.model_name}:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=45,
        )
        response.raise_for_status()
        result = response.json()
        candidates = result.get("candidates") or []
        parts = (((candidates[0] if candidates else {}).get("content") or {}).get("parts") or [])
        return "".join(str(part.get("text") or "") for part in parts).strip()

    def _tokenize(self, text: str) -> list[str]:
        tokens: list[str] = []
        for raw in self._token_re.findall(str(text or "").lower()):
            token = raw.strip()
            if len(token) < 2 or token in self._stopwords:
                continue
            tokens.append(token)
        return tokens

    def _clean_heading_text(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
        cleaned = re.sub(r"^[0-9.\-\)\]]+\s*", "", cleaned)
        return cleaned[:80]

    def _looks_like_html(self, text: str) -> bool:
        blob = str(text or "")
        return "<" in blob and ">" in blob and bool(re.search(r"<[a-zA-Z][^>]*>", blob))

    def _to_plain_text(self, text: str) -> str:
        blob = str(text or "").strip()
        if not blob:
            return ""
        if self._looks_like_html(blob):
            blob = BeautifulSoup(blob, "html.parser").get_text(" ", strip=True)
        blob = re.sub(r"\s+", " ", blob).strip()
        return blob

    def _classify_format(self, *, title: str, body_text: str, heading_texts: list[str]) -> str:
        blob = f"{title} {' '.join(heading_texts)} {body_text[:1200]}".lower()
        if any(token in blob for token in ["후기", "리뷰", "사용기"]):
            return "review"
        if any(token in blob for token in ["비교", "차이", "vs"]):
            return "comparison"
        if any(token in blob for token in ["faq", "질문", "답변", "자주"]):
            return "faq"
        if any(token in blob for token in ["방법", "가이드", "설치", "정리", "체크"]):
            return "guide"
        return "informational"

    def _avg_int(self, values: list[int]) -> int:
        if not values:
            return 0
        return int(round(sum(values) / len(values)))

    def _percentile(self, values: list[int], ratio: float) -> int:
        if not values:
            return 0
        ordered = sorted(values)
        idx = min(len(ordered) - 1, max(0, int(math.floor((len(ordered) - 1) * ratio))))
        return int(ordered[idx])


keyword_seo_profile_service = KeywordSeoProfileService()
