from __future__ import annotations

from collector.manager import collector_manager
from core.related_keyword_service import related_keyword_service
from storage.repositories import CrawlRepository, KeywordRepository, SourceChannelRepository


class CrawlService:
    def run_for_keyword(
        self,
        keyword_id: int,
        max_results: int = 3,
        sync_related: bool = True,
        allowed_channels: list[str] | None = None,
    ) -> list[str]:
        messages: list[str] = []
        all_keywords = {item.id: item for item in KeywordRepository.list_all()}
        target = all_keywords.get(keyword_id)
        if not target:
            return ["키워드를 찾을 수 없습니다."]

        enabled_channels = SourceChannelRepository.list_enabled_codes()
        if allowed_channels:
            allow = {str(code).strip() for code in allowed_channels if str(code).strip()}
            enabled_channels = [code for code in enabled_channels if code in allow]
        if not enabled_channels:
            return ["활성화된 채널이 없습니다."]

        for channel in enabled_channels:
            job_id = CrawlRepository.create_job(keyword_id=keyword_id, channel_code=channel)
            CrawlRepository.mark_started(job_id)
            try:
                rows = collector_manager.collect(channel_code=channel, keyword=target.keyword, limit=max_results)
                inserted = CrawlRepository.save_raw_contents(
                    keyword_id=keyword_id,
                    category_id=target.category_id,
                    channel_code=channel,
                    rows=rows,
                )
                CrawlRepository.mark_finished(job_id, inserted)
                messages.append(f"{channel}: 신규 {inserted}건 저장")
            except Exception as exc:
                CrawlRepository.mark_failed(job_id, str(exc))
                messages.append(f"{channel}: 실패 - {exc}")

        if sync_related:
            try:
                related_count = related_keyword_service.sync_from_naver(
                    source_keyword_id=keyword_id,
                    source_keyword=target.keyword,
                    category_id=target.category_id,
                )
                if related_count > 0:
                    messages.append(f"연관키워드(네이버) 반영: {related_count}건")
            except Exception as exc:
                messages.append(f"연관키워드 반영 실패: {exc}")

        return messages


crawl_service = CrawlService()



