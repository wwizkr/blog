from __future__ import annotations

from keyword_engine.service import keyword_engine_service


class RelatedKeywordService:
    def sync(
        self,
        source_keyword_id: int,
        source_keyword: str,
        category_id: int | None,
        enabled_sources: list[str] | None = None,
    ) -> int:
        result = keyword_engine_service.sync_related_keywords(
            source_keyword_id=source_keyword_id,
            source_keyword=source_keyword,
            category_id=category_id,
            enabled_sources=enabled_sources,
        )
        return result.total_applied

    def sync_from_naver(
        self,
        source_keyword_id: int,
        source_keyword: str,
        category_id: int | None,
    ) -> int:
        return self.sync(
            source_keyword_id=source_keyword_id,
            source_keyword=source_keyword,
            category_id=category_id,
            enabled_sources=["naver"],
        )


related_keyword_service = RelatedKeywordService()
