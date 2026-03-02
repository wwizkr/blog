from __future__ import annotations

import logging
import re
from typing import List

import requests
from bs4 import BeautifulSoup

from storage.repositories import AppSettingRepository, KeywordRepository

logger = logging.getLogger(__name__)


class RelatedKeywordService:
    _request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.naver.com/",
    }
    _cleanup_pattern = re.compile(r"^(연관검색어|관련검색어)\s*")
    _default_max_related_per_keyword = 10

    def sync_from_naver(
        self,
        source_keyword_id: int,
        source_keyword: str,
        category_id: int | None,
    ) -> int:
        max_related = AppSettingRepository.get_related_keyword_limit(self._default_max_related_per_keyword)
        candidates = self._fetch_related_keywords(source_keyword, max_related=max_related)

        upserted_relations = 0
        for candidate in candidates[:max_related]:
            if KeywordRepository.is_blocked_related(source_keyword_id, candidate):
                continue
            related_id = KeywordRepository.add_or_get(
                keyword=candidate,
                category_id=category_id,
                is_auto_generated=True,
            )
            if related_id is None:
                continue
            KeywordRepository.upsert_related_relation(
                source_keyword_id=source_keyword_id,
                related_keyword_id=related_id,
                source_type="naver",
            )
            upserted_relations += 1
        return upserted_relations

    def _fetch_related_keywords(self, keyword: str, max_related: int) -> List[str]:
        if not keyword.strip():
            return []

        related: list[str] = []

        # 1) SERP 연관검색어 추출
        try:
            response = requests.get(
                "https://search.naver.com/search.naver",
                params={"query": keyword},
                headers=self._request_headers,
                timeout=10,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            selectors = [
                "div.related_srch a.keyword",
                "ul.lst_related_srch a",
                "div._related_keywords a",
                "a.tit",
            ]
            for selector in selectors:
                nodes = soup.select(selector)
                if not nodes:
                    continue
                for node in nodes:
                    cleaned = self._clean_keyword(node.get_text(strip=True), source_keyword=keyword)
                    if cleaned and cleaned not in related:
                        related.append(cleaned)
                    if len(related) >= max_related:
                        return related[:max_related]
                if related:
                    break
        except Exception as exc:
            logger.debug("Naver SERP related fetch failed (%s): %s", keyword, exc)

        # 2) 자동완성 보강
        try:
            response = requests.get(
                "https://ac.search.naver.com/nx/ac",
                params={
                    "q": keyword,
                    "con": "1",
                    "frm": "nv",
                    "ans": "2",
                    "r_format": "json",
                    "r_enc": "UTF-8",
                    "r_unicode": "0",
                    "t_koreng": "1",
                },
                headers=self._request_headers,
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
            for group in payload.get("items", []):
                if not isinstance(group, list):
                    continue
                for item in group:
                    if not isinstance(item, list) or not item:
                        continue
                    cleaned = self._clean_keyword(str(item[0]), source_keyword=keyword)
                    if cleaned and cleaned not in related:
                        related.append(cleaned)
                    if len(related) >= max_related:
                        return related[:max_related]
        except Exception as exc:
            logger.debug("Naver autocomplete related fetch failed (%s): %s", keyword, exc)

        return related[:max_related]

    def _clean_keyword(self, value: str, source_keyword: str) -> str:
        cleaned = self._cleanup_pattern.sub("", (value or "").strip())
        if not cleaned:
            return ""
        if cleaned == source_keyword:
            return ""
        return cleaned


related_keyword_service = RelatedKeywordService()

