from __future__ import annotations

import logging

import requests

from keyword_engine.base import KeywordCandidate

logger = logging.getLogger(__name__)


class GoogleSuggestKeywordProvider:
    code = "google_suggest"
    _request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def fetch(self, keyword: str, limit: int) -> list[KeywordCandidate]:
        if not keyword.strip() or limit <= 0:
            return []
        seen: set[str] = set()
        candidates: list[KeywordCandidate] = []
        try:
            response = requests.get(
                "https://suggestqueries.google.com/complete/search",
                params={"client": "firefox", "hl": "ko", "q": keyword},
                headers=self._request_headers,
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
            items = payload[1] if isinstance(payload, list) and len(payload) > 1 and isinstance(payload[1], list) else []
            for item in items:
                cleaned = str(item or "").strip()
                if not cleaned or cleaned == keyword or cleaned in seen:
                    continue
                seen.add(cleaned)
                candidates.append(KeywordCandidate(keyword=cleaned, source_type=self.code, source_detail="suggest"))
                if len(candidates) >= limit:
                    break
        except Exception as exc:
            logger.debug("Google suggest fetch failed (%s): %s", keyword, exc)
        return candidates[:limit]
