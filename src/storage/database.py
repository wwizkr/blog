from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from collector.manager import collector_manager
from core.settings import settings
from core.settings_keys import WriterSettingKeys
from storage.models import (
    AIProvider,
    AppSetting,
    ArticleTemplate,
    Base,
    Persona,
    PublishChannel,
    PublishChannelSetting,
    SourceChannel,
    WritingChannel,
)

_engine = None
_SessionFactory: sessionmaker[Session] | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(settings.database_url, echo=False, future=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionFactory


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database() -> None:
    Base.metadata.create_all(bind=get_engine())
    _ensure_generated_articles_columns()
    _ensure_personas_columns()
    _ensure_keywords_columns()
    _ensure_related_keyword_tables()
    _ensure_keyword_seo_profile_tables()
    _ensure_labeling_columns()
    _sync_channels_from_collectors()
    _seed_publish_channels()
    _seed_publish_channel_settings()
    _seed_writing_channels()
    _seed_personas()
    _seed_article_templates()
    _seed_ai_providers()
    _seed_writer_defaults()


def _ensure_labeling_columns() -> None:
    raw_content_columns = {
        "body_html": "TEXT",
        "label_status": "VARCHAR(20) DEFAULT 'pending'",
        "label_attempt_count": "INTEGER DEFAULT 0",
        "last_labeled_at": "DATETIME",
        "label_confidence": "INTEGER",
    }
    raw_image_columns = {
        "label_status": "VARCHAR(20) DEFAULT 'pending'",
        "label_attempt_count": "INTEGER DEFAULT 0",
        "last_labeled_at": "DATETIME",
        "label_confidence": "INTEGER",
    }
    content_label_columns = {
        "structure_type": "VARCHAR(30)",
        "title_type": "VARCHAR(30)",
        "commercial_intent": "INTEGER DEFAULT 0",
        "writing_fit_score": "INTEGER DEFAULT 0",
        "cta_present": "BOOLEAN DEFAULT 0",
        "faq_structure": "BOOLEAN DEFAULT 0",
    }
    image_label_columns = {
        "image_type": "VARCHAR(30)",
        "subject_tags": "TEXT",
        "commercial_intent": "INTEGER DEFAULT 0",
        "keyword_relevance_score": "INTEGER DEFAULT 0",
        "text_overlay": "BOOLEAN DEFAULT 0",
        "thumbnail_score": "INTEGER DEFAULT 0",
    }
    with get_engine().begin() as conn:
        content_existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(raw_contents)").fetchall()}
        for column_name, column_type in raw_content_columns.items():
            if column_name in content_existing:
                continue
            conn.exec_driver_sql(f"ALTER TABLE raw_contents ADD COLUMN {column_name} {column_type}")

        image_existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(raw_images)").fetchall()}
        for column_name, column_type in raw_image_columns.items():
            if column_name in image_existing:
                continue
            conn.exec_driver_sql(f"ALTER TABLE raw_images ADD COLUMN {column_name} {column_type}")

        content_label_existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(content_labels)").fetchall()}
        for column_name, column_type in content_label_columns.items():
            if column_name in content_label_existing:
                continue
            conn.exec_driver_sql(f"ALTER TABLE content_labels ADD COLUMN {column_name} {column_type}")

        image_label_existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(image_labels)").fetchall()}
        for column_name, column_type in image_label_columns.items():
            if column_name in image_label_existing:
                continue
            conn.exec_driver_sql(f"ALTER TABLE image_labels ADD COLUMN {column_name} {column_type}")

        conn.exec_driver_sql("UPDATE raw_contents SET label_status = 'pending' WHERE label_status IS NULL OR TRIM(label_status) = ''")
        conn.exec_driver_sql("UPDATE raw_images SET label_status = 'pending' WHERE label_status IS NULL OR TRIM(label_status) = ''")


def _ensure_generated_articles_columns() -> None:
    required_columns = {
        "persona_id": "INTEGER",
        "template_id": "INTEGER",
        "template_name": "VARCHAR(120)",
        "template_version": "INTEGER",
        "writing_channel_id": "INTEGER",
        "ai_provider_id": "INTEGER",
        "generation_meta_json": "TEXT",
    }
    with get_engine().begin() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(generated_articles)").fetchall()}
        for column_name, column_type in required_columns.items():
            if column_name in existing:
                continue
            conn.exec_driver_sql(f"ALTER TABLE generated_articles ADD COLUMN {column_name} {column_type}")


def _ensure_personas_columns() -> None:
    required_columns = {
        "age_group": "VARCHAR(30)",
        "gender": "VARCHAR(20)",
        "personality": "VARCHAR(200)",
        "interests": "TEXT",
        "speech_style": "VARCHAR(120)",
    }
    with get_engine().begin() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(personas)").fetchall()}
        for column_name, column_type in required_columns.items():
            if column_name in existing:
                continue
            conn.exec_driver_sql(f"ALTER TABLE personas ADD COLUMN {column_name} {column_type}")


def _ensure_keywords_columns() -> None:
    required_columns = {
        "is_auto_generated": "BOOLEAN DEFAULT 0",
    }
    with get_engine().begin() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(keywords)").fetchall()}
        for column_name, column_type in required_columns.items():
            if column_name in existing:
                continue
            conn.exec_driver_sql(f"ALTER TABLE keywords ADD COLUMN {column_name} {column_type}")


def _ensure_related_keyword_tables() -> None:
    with get_engine().begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS keyword_related_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_keyword_id INTEGER NOT NULL,
                related_keyword_id INTEGER NOT NULL,
                source_type VARCHAR(20) NOT NULL DEFAULT 'content',
                collect_count INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(source_keyword_id) REFERENCES keywords(id) ON DELETE CASCADE,
                FOREIGN KEY(related_keyword_id) REFERENCES keywords(id) ON DELETE CASCADE,
                UNIQUE(source_keyword_id, related_keyword_id)
            )
            """
        )
        conn.exec_driver_sql("DROP TABLE IF EXISTS keyword_related_blocks")


def _ensure_keyword_seo_profile_tables() -> None:
    with get_engine().begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS keyword_seo_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword_id INTEGER NOT NULL UNIQUE,
                sample_count INTEGER NOT NULL DEFAULT 0,
                avg_title_length INTEGER NOT NULL DEFAULT 0,
                avg_body_length INTEGER NOT NULL DEFAULT 0,
                avg_heading_count INTEGER NOT NULL DEFAULT 0,
                avg_image_count INTEGER NOT NULL DEFAULT 0,
                avg_list_count INTEGER NOT NULL DEFAULT 0,
                dominant_format VARCHAR(30),
                common_sections_json TEXT,
                common_terms_json TEXT,
                recommended_length_min INTEGER,
                recommended_length_max INTEGER,
                recommended_heading_count INTEGER,
                recommended_image_count INTEGER,
                summary_text TEXT,
                analysis_basis_json TEXT,
                analyzed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS keyword_seo_profile_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword_id INTEGER NOT NULL,
                sample_count INTEGER NOT NULL DEFAULT 0,
                summary_text TEXT,
                metrics_json TEXT,
                source_content_ids_json TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
            )
            """
        )


def _sync_channels_from_collectors() -> None:
    collector_channels = collector_manager.list_channels()
    with session_scope() as session:
        existing_codes = {row.code for row in session.query(SourceChannel).all()}
        for code, display_name in collector_channels:
            if code not in existing_codes:
                session.add(SourceChannel(code=code, display_name=display_name, is_enabled=True))


def _seed_publish_channel_settings() -> None:
    with session_scope() as session:
        existing = {row.channel_code for row in session.query(PublishChannelSetting).all()}
        channels = session.query(PublishChannel).all()
        for channel in channels:
            if channel.code in existing:
                continue
            session.add(
                PublishChannelSetting(
                    channel_code=channel.code,
                    publish_cycle_minutes=60,
                    publish_mode="semi_auto",
                    publish_format="blog",
                    writing_style="informative",
                    api_url=None,
                )
            )


def _seed_publish_channels() -> None:
    with session_scope() as session:
        existing = {row.code for row in session.query(PublishChannel).all()}
        defaults = [
            ("naver_blog", "네이버 블로그"),
            ("tistory", "티스토리"),
            ("custom_api", "커스텀 API"),
        ]
        for code, display_name in defaults:
            if code in existing:
                continue
            session.add(PublishChannel(code=code, display_name=display_name, is_enabled=True))

def _seed_writing_channels() -> None:
    with session_scope() as session:
        existing = {row.code for row in session.query(WritingChannel).all()}
        defaults = [
            {
                "code": "naver_blog",
                "display_name": "네이버 블로그",
                "channel_type": "blog",
                "connection_type": "manual",
                "status": "active",
                "allowed_markup": "rich_text",
                "title_max_length": 60,
                "body_min_length": 1200,
                "body_max_length": 5000,
                "tag_policy": "optional",
            },
            {
                "code": "tistory",
                "display_name": "티스토리",
                "channel_type": "blog",
                "connection_type": "api",
                "status": "active",
                "allowed_markup": "html",
                "title_max_length": 70,
                "body_min_length": 1200,
                "body_max_length": 6000,
                "tag_policy": "recommended",
            },
            {
                "code": "wordpress",
                "display_name": "워드프레스",
                "channel_type": "cms",
                "connection_type": "api",
                "status": "active",
                "allowed_markup": "html",
                "title_max_length": 80,
                "body_min_length": 1200,
                "body_max_length": 7000,
                "tag_policy": "recommended",
            },
        ]
        for item in defaults:
            if item["code"] in existing:
                continue
            session.add(
                WritingChannel(
                    code=item["code"],
                    display_name=item["display_name"],
                    channel_type=item["channel_type"],
                    connection_type=item["connection_type"],
                    status=item["status"],
                    is_enabled=True,
                    allowed_markup=item["allowed_markup"],
                    title_max_length=item["title_max_length"],
                    body_min_length=item["body_min_length"],
                    body_max_length=item["body_max_length"],
                    tag_policy=item["tag_policy"],
                    default_visibility="public",
                    external_link_policy="allow",
                    reserve_publish_enabled=True,
                    updated_at=datetime.utcnow(),
                )
            )


def _seed_personas() -> None:
    with session_scope() as session:
        existing = {row.name for row in session.query(Persona).all()}
        defaults = [
            {
                "name": "기본 페르소나",
                "age_group": "30대",
                "gender": "무관",
                "personality": "분석적",
                "interests": "생산성,콘텐츠마케팅",
                "speech_style": "정중한 설명형",
                "tone": "정보형",
                "style_guide": "사실 중심으로 간결하게 작성",
            },
            {
                "name": "친절 가이드",
                "age_group": "20대",
                "gender": "무관",
                "personality": "친근함",
                "interests": "실전팁,튜토리얼",
                "speech_style": "친절한 코치형",
                "tone": "친근형",
                "style_guide": "초보자에게 설명하듯 단계별로 작성",
            },
        ]
        for item in defaults:
            if item["name"] in existing:
                continue
            session.add(
                Persona(
                    name=item["name"],
                    age_group=item["age_group"],
                    gender=item["gender"],
                    personality=item["personality"],
                    interests=item["interests"],
                    speech_style=item["speech_style"],
                    tone=item["tone"],
                    style_guide=item["style_guide"],
                    banned_words=None,
                    is_active=True,
                    updated_at=datetime.utcnow(),
                )
            )


def _seed_article_templates() -> None:
    blog_legacy = "# {{keyword}} 정리\n\n페르소나: {{persona_name}} ({{persona_age_group}}, {{persona_gender}})\n성격: {{persona_personality}}\n말투: {{persona_speech_style}}\n톤: {{persona_tone}}\n\n## 핵심 요약\n{{source_summary}}\n\n## 주요 관심사 반영\n{{persona_interests}}\n\n## 마무리\n{{persona_style}}"
    sns_legacy = "{{persona_name}} 말투({{persona_speech_style}})로 {{keyword}}를 5문장 이내로 요약하세요.\n\n근거:\n{{source_summary}}"
    board_legacy = "[{{keyword}}] 게시판용 요약\n\n작성자 페르소나: {{persona_name}}\n연령/성별: {{persona_age_group}} / {{persona_gender}}\n성격: {{persona_personality}}\n\n핵심 자료:\n{{source_summary}}\n\n금칙어: {{persona_banned_words}}"
    blog_seo_only = (
        "# {{keyword}} 정리\n\n"
        "페르소나: {{persona_name}} ({{persona_age_group}}, {{persona_gender}})\n"
        "성격: {{persona_personality}}\n"
        "말투: {{persona_speech_style}}\n"
        "톤: {{persona_tone}}\n\n"
        "## SEO 전략 해석\n{{seo_strategy}}\n\n"
        "## SEO 정량 가이드\n{{seo_metrics}}\n\n"
        "## 핵심 자료 요약\n{{source_summary}}\n\n"
        "## 주요 관심사 반영\n{{persona_interests}}\n\n"
        "## 작성 지침\n{{persona_style}}\n"
    )
    sns_seo_only = (
        "{{persona_name}} 말투({{persona_speech_style}})로 {{keyword}}를 5문장 이내로 요약하되, "
        "첫 문장에는 {{seo_strategy}}의 핵심 방향을 반영하세요.\n\n"
        "SEO 핵심:\n{{seo_metrics}}\n\n"
        "근거:\n{{source_summary}}"
    )
    board_seo_only = (
        "[{{keyword}}] 게시판용 요약\n\n"
        "작성자 페르소나: {{persona_name}}\n"
        "연령/성별: {{persona_age_group}} / {{persona_gender}}\n"
        "성격: {{persona_personality}}\n\n"
        "핵심 전략:\n{{seo_strategy}}\n\n"
        "정리 기준:\n{{seo_metrics}}\n\n"
        "핵심 자료:\n{{source_summary}}\n\n"
        "금칙어: {{persona_banned_words}}"
    )

    blog_prompt = (
        "# {{keyword}} 정리\n\n"
        "페르소나: {{persona_name}} ({{persona_age_group}}, {{persona_gender}})\n"
        "성격: {{persona_personality}}\n"
        "말투: {{persona_speech_style}}\n"
        "톤: {{persona_tone}}\n\n"
        "## SEO 전략 해석\n{{seo_strategy}}\n\n"
        "## SEO 정량 가이드\n{{seo_metrics}}\n\n"
        "## 핵심 자료 요약\n{{source_summary}}\n\n"
        "## 원문 개요\n{{source_outline}}\n\n"
        "## 이미지 사용 계획\n{{image_plan}}\n\n"
        "## 사용 가능한 이미지 슬롯\n{{image_slots}}\n\n"
        "## 주요 관심사 반영\n{{persona_interests}}\n\n"
        "## 작성 지침\n{{persona_style}}\n\n"
        "중요:\n"
        "- 최종 결과는 실제 발행용 본문만 작성하세요.\n"
        "- 설명 메모나 프롬프트 해설은 쓰지 마세요.\n"
        "- 관련성이 높은 경우에만 `[[IMAGE:id]]` 슬롯을 소제목 사이에 그대로 삽입하세요.\n"
        "- 슬롯 문자열은 수정하지 마세요.\n"
    )
    sns_prompt = (
        "{{persona_name}} 말투({{persona_speech_style}})로 {{keyword}}를 5문장 이내로 요약하되, "
        "첫 문장에는 {{seo_strategy}}의 핵심 방향을 반영하세요.\n\n"
        "SEO 핵심:\n{{seo_metrics}}\n\n"
        "근거:\n{{source_summary}}\n\n"
        "사용 가능한 이미지 슬롯:\n{{image_slots}}\n\n"
        "관련성이 충분할 때만 슬롯을 마지막 줄에 1개까지 그대로 넣으세요."
    )
    board_prompt = (
        "[{{keyword}}] 게시판용 요약\n\n"
        "작성자 페르소나: {{persona_name}}\n"
        "연령/성별: {{persona_age_group}} / {{persona_gender}}\n"
        "성격: {{persona_personality}}\n\n"
        "핵심 전략:\n{{seo_strategy}}\n\n"
        "정리 기준:\n{{seo_metrics}}\n\n"
        "핵심 자료:\n{{source_summary}}\n\n"
        "이미지 슬롯:\n{{image_slots}}\n\n"
        "금칙어: {{persona_banned_words}}\n\n"
        "관련 이미지가 적절하면 `[[IMAGE:id]]` 슬롯을 본문 중간에 그대로 넣으세요."
    )
    with session_scope() as session:
        rows = session.query(ArticleTemplate).all()
        existing = {(row.name, row.template_type) for row in rows}
        for row in rows:
            key = (row.name, row.template_type)
            if key == ("블로그 기본형", "blog") and (row.user_prompt or "").strip() in {blog_legacy, blog_seo_only}:
                row.user_prompt = blog_prompt
                row.updated_at = datetime.utcnow()
            elif key == ("SNS 요약형", "sns") and (row.user_prompt or "").strip() in {sns_legacy, sns_seo_only}:
                row.user_prompt = sns_prompt
                row.updated_at = datetime.utcnow()
            elif key == ("게시판 정보형", "board") and (row.user_prompt or "").strip() in {board_legacy, board_seo_only}:
                row.user_prompt = board_prompt
                row.updated_at = datetime.utcnow()
        defaults = [
            (
                "블로그 기본형",
                "blog",
                blog_prompt,
            ),
            (
                "SNS 요약형",
                "sns",
                sns_prompt,
            ),
            (
                "게시판 정보형",
                "board",
                board_prompt,
            ),
        ]
        for name, template_type, user_prompt in defaults:
            if (name, template_type) in existing:
                continue
            session.add(
                ArticleTemplate(
                    name=name,
                    template_type=template_type,
                    system_prompt=None,
                    user_prompt=user_prompt,
                    output_schema=None,
                    is_active=True,
                    version=1,
                    updated_at=datetime.utcnow(),
                )
            )


def _seed_ai_providers() -> None:
    with session_scope() as session:
        exists = session.query(AIProvider).first()
        if exists:
            return
        session.add(
            AIProvider(
                provider="openai",
                model_name="gpt-4.1-mini",
                api_key_alias="OPENAI_API_KEY",
                is_paid=True,
                is_enabled=True,
                priority=1,
                rate_limit_per_min=60,
                daily_budget_limit=100,
                status="ready",
                last_checked_at=None,
                updated_at=datetime.utcnow(),
            )
        )
        session.add(
            AIProvider(
                provider="google",
                model_name="gemini-1.5-flash",
                api_key_alias="GEMINI_API_KEY",
                is_paid=False,
                is_enabled=True,
                priority=2,
                rate_limit_per_min=30,
                daily_budget_limit=0,
                status="ready",
                last_checked_at=None,
                updated_at=datetime.utcnow(),
            )
        )


def _seed_writer_defaults() -> None:
    with session_scope() as session:
        persona = session.query(Persona).filter(Persona.is_active == True).order_by(Persona.id.asc()).first()
        if not persona:
            return

        template_rows = session.query(ArticleTemplate).filter(ArticleTemplate.is_active == True).order_by(ArticleTemplate.id.asc()).all()
        if not template_rows:
            return
        template_by_type = {str(row.template_type or "").strip().lower(): row for row in template_rows}
        blog_template = template_by_type.get("blog") or (template_rows[0] if template_rows else None)
        sns_template = template_by_type.get("sns") or blog_template
        board_template = template_by_type.get("board") or blog_template
        if not blog_template:
            return

        provider = session.query(AIProvider).filter(AIProvider.is_enabled == True).order_by(AIProvider.priority.asc(), AIProvider.id.asc()).first()
        provider_id = int(provider.id) if provider else None

        channels = session.query(WritingChannel).filter(WritingChannel.is_enabled == True).order_by(WritingChannel.id.asc()).all()
        if not channels:
            return

        settings_map = {
            row.setting_key: row
            for row in session.query(AppSetting).filter(
                AppSetting.setting_key.in_([
                    WriterSettingKeys.DEFAULT_AI_PROVIDER_ID,
                    WriterSettingKeys.AI_PROVIDER_PRIORITY,
                    WriterSettingKeys.MIN_SEO_REVIEW_SCORE,
                    WriterSettingKeys.CHANNEL_POLICIES,
                ])
            ).all()
        }

        def _set_if_missing(key: str, value: str) -> None:
            existing = settings_map.get(key)
            if existing and str(existing.setting_value or "").strip():
                return
            if existing:
                existing.setting_value = value
                existing.updated_at = datetime.utcnow()
                return
            session.add(AppSetting(setting_key=key, setting_value=value, updated_at=datetime.utcnow()))

        if provider_id:
            _set_if_missing(WriterSettingKeys.DEFAULT_AI_PROVIDER_ID, str(provider_id))
        _set_if_missing(WriterSettingKeys.AI_PROVIDER_PRIORITY, "quality_first")
        _set_if_missing(WriterSettingKeys.MIN_SEO_REVIEW_SCORE, "60")

        policy_row = settings_map.get(WriterSettingKeys.CHANNEL_POLICIES)
        try:
            policy_map = json.loads(str(policy_row.setting_value or "{}")) if policy_row and str(policy_row.setting_value or "").strip() else {}
        except Exception:
            policy_map = {}
        if not isinstance(policy_map, dict):
            policy_map = {}

        changed = False
        for channel in channels:
            key = str(int(channel.id))
            existing_policy = policy_map.get(key)
            if isinstance(existing_policy, dict) and existing_policy.get("persona_ids") and existing_policy.get("template_ids"):
                continue
            channel_type = str(channel.channel_type or "").strip().lower()
            if channel_type in {"sns", "longform"}:
                template = sns_template
            elif channel_type in {"community", "board"}:
                template = board_template
            else:
                template = blog_template
            if not template:
                continue
            policy_map[key] = {
                "persona_ids": [int(persona.id)],
                "template_ids": [int(template.id)],
                "persona_cursor": 0,
                "template_cursor": 0,
                "default_ai_provider_id": provider_id,
                "min_source_count": 3,
                "default_tone": "informative",
                "default_reader_level": "general",
                "default_length": "medium",
                "creativity_level": 3,
                "factuality_level": 4,
                "seo_keywords": "",
                "auto_enabled": False,
                "auto_interval_minutes": 1440,
                "auto_batch_count": 1,
                "auto_retry_count": 1,
                "auto_time_window": "00:00-23:59",
            }
            changed = True

        if changed or not (policy_row and str(policy_row.setting_value or "").strip()):
            payload = json.dumps(policy_map, ensure_ascii=False)
            if policy_row:
                policy_row.setting_value = payload
                policy_row.updated_at = datetime.utcnow()
            else:
                session.add(
                    AppSetting(
                        setting_key=WriterSettingKeys.CHANNEL_POLICIES,
                        setting_value=payload,
                        updated_at=datetime.utcnow(),
                    )
                )

