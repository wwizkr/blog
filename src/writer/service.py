from __future__ import annotations

from storage.repositories import (
    AIProviderRepository,
    ArticleRepository,
    ArticleTemplateRepository,
    CrawlRepository,
    PersonaRepository,
    WritingChannelRepository,
)


class WriterService:
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

        source_rows = CrawlRepository.list_recent_contents(source_limit)
        if not source_rows:
            raise ValueError("생성 가능한 원문 데이터가 없습니다. 먼저 수집을 실행하세요.")

        channel = WritingChannelRepository.get_by_id(writing_channel_id) if writing_channel_id else None
        provider = AIProviderRepository.get_by_id(ai_provider_id) if ai_provider_id else None
        keyword = source_rows[0].keyword or "콘텐츠"
        target_channel = channel.display_name if channel else template.template_type
        format_type = self._resolve_format_type(template.template_type, channel.channel_type if channel else None)
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
            "target_channel": target_channel,
            "channel_code": channel.code if channel else "",
            "channel_type": channel.channel_type if channel else template.template_type,
            "ai_provider": provider.provider if provider else "",
            "ai_model": provider.model_name if provider else "",
        }

        title = self._build_title(format_type, persona.name, keyword, template.name)
        content = self._render_template(template.user_prompt, context)
        if channel:
            content = self._prepend_channel_notes(content=content, channel_name=channel.display_name, channel_type=channel.channel_type)
        article_id = ArticleRepository.add(
            title=title,
            content=content,
            format_type=format_type,
            persona_id=persona.id,
            persona_name=persona.name,
            template_id=template.id,
            template_name=template.name,
            template_version=template.version,
            source_content_ids=[row.id for row in source_rows],
        )
        return {"id": article_id, "title": title, "content": content}

    def _resolve_format_type(self, template_type: str, channel_type: str | None) -> str:
        ctype = (channel_type or "").strip().lower()
        if ctype in {"blog", "cms"}:
            return "blog"
        if ctype in {"sns", "longform"}:
            return "sns"
        if ctype in {"community", "board"}:
            return "board"
        return template_type

    def _prepend_channel_notes(self, content: str, channel_name: str, channel_type: str) -> str:
        header = f"[작성 채널: {channel_name} / 유형: {channel_type}]"
        if content.startswith(header):
            return content
        return f"{header}\n\n{content}"

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

    def _render_template(self, template_text: str, context: dict[str, str]) -> str:
        rendered = template_text
        for key, value in context.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)
        return rendered


writer_service = WriterService()

