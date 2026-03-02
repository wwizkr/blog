from __future__ import annotations

from storage.repositories import ArticleRepository, PublishChannelSettingRepository, PublishRepository


class PublisherService:
    def enqueue_publish(self, article_id: int, target_channel: str, mode: str = "semi_auto") -> int:
        ArticleRepository.update_status(article_id, "ready")
        return PublishRepository.enqueue(article_id=article_id, target_channel=target_channel, mode=mode)

    def process_job(self, job_id: int) -> str:
        try:
            PublishRepository.mark_processing(job_id)
            # TODO: 실제 채널 API 연동
            # 현재는 설정에 등록된 API URL 존재 여부만 확인하여 로그 메시지에 반영
            jobs = PublishRepository.list_recent(300)
            target = next((j for j in jobs if j.id == job_id), None)
            api_url = None
            if target:
                setting = PublishChannelSettingRepository.get_by_channel(target.target_channel)
                api_url = setting.api_url if setting else None
            # TODO: 실제 채널 API 연동
            if api_url:
                PublishRepository.mark_done(job_id, f"샘플 발행 완료(실연동 전) - API URL: {api_url}")
            else:
                PublishRepository.mark_done(job_id, "샘플 발행 완료(실연동 전) - API URL 미설정")
            return "완료"
        except Exception as exc:
            PublishRepository.mark_failed(job_id, str(exc))
            return f"실패: {exc}"


publisher_service = PublisherService()

