from __future__ import annotations

from dataclasses import dataclass
import re

from core.settings_keys import CollectSettingKeys
from keyword_engine.base import KeywordSourceProvider
from keyword_engine.providers import GoogleSuggestKeywordProvider, NaverKeywordProvider
from storage.repositories import AppSettingRepository, KeywordRepository


@dataclass(frozen=True)
class KeywordSyncResult:
    total_applied: int
    by_source: dict[str, int]


@dataclass(frozen=True)
class KeywordSourceInfo:
    code: str
    label: str
    enabled_by_default: bool = False


class KeywordEngineService:
    _default_max_related_per_keyword = 10
    _min_keyword_length = 2
    _space_re = re.compile(r"\s+")
    _edge_noise_re = re.compile(r"^[\s\-_,./|:;]+|[\s\-_,./|:;]+$")
    _canonical_noise_re = re.compile(r"[^0-9A-Za-z가-힣]+")

    def __init__(self, providers: list[KeywordSourceProvider] | None = None) -> None:
        provider_list = providers or [NaverKeywordProvider(), GoogleSuggestKeywordProvider()]
        self._providers = {provider.code: provider for provider in provider_list}
        self._source_info = {
            "naver": KeywordSourceInfo(code="naver", label="네이버 연관/자동완성", enabled_by_default=True),
            "google_suggest": KeywordSourceInfo(code="google_suggest", label="Google Suggest", enabled_by_default=True),
        }

    def list_provider_codes(self) -> list[str]:
        return list(self._providers.keys())

    def list_sources(self) -> list[KeywordSourceInfo]:
        rows: list[KeywordSourceInfo] = []
        for code in self.list_provider_codes():
            rows.append(self._source_info.get(code, KeywordSourceInfo(code=code, label=code, enabled_by_default=False)))
        return rows

    def get_enabled_source_codes(self) -> list[str]:
        try:
            raw = AppSettingRepository.get_value(CollectSettingKeys.KEYWORD_SOURCE_CODES, "")
        except Exception:
            raw = ""
        if raw:
            values = [str(item).strip() for item in raw.split(",")]
            return [code for code in values if code in self._providers]
        return [row.code for row in self.list_sources() if row.enabled_by_default and row.code in self._providers]

    def _normalize_keyword_text(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        text = self._space_re.sub(" ", text)
        text = self._edge_noise_re.sub("", text)
        return text.strip()

    def _canonical_keyword_key(self, value: str) -> str:
        normalized = self._normalize_keyword_text(value).casefold()
        normalized = self._canonical_noise_re.sub("", normalized)
        return normalized.strip()

    def _is_valid_related_keyword(self, candidate: str, source_keyword: str) -> bool:
        normalized = self._normalize_keyword_text(candidate)
        canonical = self._canonical_keyword_key(normalized)
        source_canonical = self._canonical_keyword_key(source_keyword)
        if not normalized or not canonical:
            return False
        if len(canonical) < self._min_keyword_length:
            return False
        if canonical == source_canonical:
            return False
        return True

    def sync_related_keywords(
        self,
        source_keyword_id: int,
        source_keyword: str,
        category_id: int | None,
        enabled_sources: list[str] | None = None,
    ) -> KeywordSyncResult:
        max_related = AppSettingRepository.get_related_keyword_limit(self._default_max_related_per_keyword)
        if max_related <= 0:
            return KeywordSyncResult(total_applied=0, by_source={})

        allowed = {str(code).strip() for code in (enabled_sources or self.get_enabled_source_codes()) if str(code).strip()}
        source_keyword_normalized = self._normalize_keyword_text(source_keyword)
        seen_keywords: set[str] = set()
        total_applied = 0
        by_source: dict[str, int] = {}

        for code, provider in self._providers.items():
            if allowed and code not in allowed:
                continue
            remaining = max_related - total_applied
            if remaining <= 0:
                break
            candidates = provider.fetch(keyword=source_keyword, limit=remaining)
            applied_in_source = 0
            for candidate in candidates:
                cleaned = self._normalize_keyword_text(candidate.keyword)
                canonical = self._canonical_keyword_key(cleaned)
                if not self._is_valid_related_keyword(cleaned, source_keyword_normalized):
                    continue
                if canonical in seen_keywords:
                    continue
                seen_keywords.add(canonical)
                related_id = KeywordRepository.add_or_get(
                    keyword=cleaned,
                    category_id=category_id,
                    is_auto_generated=True,
                )
                if related_id is None:
                    continue
                KeywordRepository.upsert_related_relation(
                    source_keyword_id=source_keyword_id,
                    related_keyword_id=related_id,
                    source_type=code,
                )
                applied_in_source += 1
                total_applied += 1
                if total_applied >= max_related:
                    break
            if applied_in_source > 0:
                by_source[code] = applied_in_source

        return KeywordSyncResult(total_applied=total_applied, by_source=by_source)


keyword_engine_service = KeywordEngineService()
