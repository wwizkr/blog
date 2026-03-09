from __future__ import annotations

import json
import logging
import re

import requests
from bs4 import BeautifulSoup

from keyword_engine.base import KeywordCandidate

logger = logging.getLogger(__name__)


class NaverKeywordProvider:
    code = "naver"
    _request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.naver.com/",
    }
    _cleanup_pattern = re.compile(r"^(연관검색어|관련검색어)\s*")

    def fetch(self, keyword: str, limit: int) -> list[KeywordCandidate]:
        if not keyword.strip() or limit <= 0:
            return []

        # NOTE:
        # Naver UI/response shape is unstable and may omit related keywords entirely.
        # For now we keep the provider in place even if it returns 0 results.
        #
        # Planned direction:
        # 1. Replace UI/HTML-dependent parsing with a dedicated Naver-related API flow.
        # 2. Keep `source_type="naver"` unchanged so stored relations remain compatible.
        # 3. Prefer an API response contract that returns explicit keyword arrays plus scores.
        # 4. Preserve current fallback order so the switch can happen inside this provider only.
        #
        # In short: do not remove this provider; swap internals to API-based collection later.
        rows = self._fetch_qr_candidates(keyword, limit)
        if rows:
            return rows[:limit]

        rows = self._fetch_autocomplete_candidates(keyword, limit)
        if rows:
            return rows[:limit]

        return []

    def _fetch_qr_candidates(self, keyword: str, limit: int) -> list[KeywordCandidate]:
        seen: set[str] = set()
        related: list[KeywordCandidate] = []
        try:
            # NOTE:
            # This path depends on search result HTML/embedded payloads.
            # It is intentionally left as-is for now even though Naver may return 0 candidates.
            # Future work should replace this block with a direct API call rather than selector/text parsing.
            response = requests.get(
                "https://search.naver.com/search.naver",
                params={"query": keyword},
                headers=self._request_headers,
                timeout=10,
            )
            response.raise_for_status()
            html = response.text
            match = re.search(r'qr\\\\\":\\\\\"(\\[.*?\\])\\\\\"', html)
            if not match:
                return []
            raw = match.group(1)
            normalized = re.sub(r'\\+"', '"', raw)
            payload = json.loads(normalized)
            if not isinstance(payload, list):
                return []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                cleaned = self._clean_keyword(str(item.get("query") or ""), source_keyword=keyword)
                if not cleaned or cleaned in seen:
                    continue
                seen.add(cleaned)
                score = item.get("score")
                try:
                    normalized_score = float(score) if score is not None else None
                except (TypeError, ValueError):
                    normalized_score = None
                related.append(
                    KeywordCandidate(
                        keyword=cleaned,
                        source_type=self.code,
                        source_detail="serp_qr",
                        score=normalized_score,
                    )
                )
                if len(related) >= limit:
                    break
        except Exception as exc:
            logger.debug("Naver QR fetch failed (%s): %s", keyword, exc)
        return related[:limit]

    def _fetch_autocomplete_candidates(self, keyword: str, limit: int) -> list[KeywordCandidate]:
        seen: set[str] = set()
        related: list[KeywordCandidate] = []
        try:
            # NOTE:
            # The current autocomplete endpoint can return empty `items` even for valid keywords.
            # Keep this fallback for now; later replace or supplement it with an official/stable API path.
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
                    if not cleaned or cleaned in seen:
                        continue
                    seen.add(cleaned)
                    related.append(KeywordCandidate(keyword=cleaned, source_type=self.code, source_detail="autocomplete"))
                    if len(related) >= limit:
                        break
                if len(related) >= limit:
                    break
        except Exception as exc:
            logger.debug("Naver autocomplete fetch failed (%s): %s", keyword, exc)
        return related[:limit]

    def _clean_keyword(self, value: str, source_keyword: str) -> str:
        cleaned = self._cleanup_pattern.sub("", (value or "").strip())
        if not cleaned:
            return ""
        if cleaned == source_keyword:
            return ""
        return cleaned
