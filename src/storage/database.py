from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from collector.manager import collector_manager
from core.settings import settings
from storage.models import (
    AIProvider,
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
    _sync_channels_from_collectors()
    _seed_publish_channels()
    _seed_publish_channel_settings()
    _seed_writing_channels()
    _seed_personas()
    _seed_article_templates()
    _seed_ai_providers()


def _ensure_generated_articles_columns() -> None:
    required_columns = {
        "persona_id": "INTEGER",
        "template_id": "INTEGER",
        "template_name": "VARCHAR(120)",
        "template_version": "INTEGER",
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
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS keyword_related_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_keyword_id INTEGER NOT NULL,
                related_keyword VARCHAR(200) NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(source_keyword_id) REFERENCES keywords(id) ON DELETE CASCADE,
                UNIQUE(source_keyword_id, related_keyword)
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
    with session_scope() as session:
        existing = {(row.name, row.template_type) for row in session.query(ArticleTemplate).all()}
        defaults = [
            (
                "블로그 기본형",
                "blog",
                "# {{keyword}} 정리\n\n페르소나: {{persona_name}} ({{persona_age_group}}, {{persona_gender}})\n성격: {{persona_personality}}\n말투: {{persona_speech_style}}\n톤: {{persona_tone}}\n\n## 핵심 요약\n{{source_summary}}\n\n## 주요 관심사 반영\n{{persona_interests}}\n\n## 마무리\n{{persona_style}}",
            ),
            (
                "SNS 요약형",
                "sns",
                "{{persona_name}} 말투({{persona_speech_style}})로 {{keyword}}를 5문장 이내로 요약하세요.\n\n근거:\n{{source_summary}}",
            ),
            (
                "게시판 정보형",
                "board",
                "[{{keyword}}] 게시판용 요약\n\n작성자 페르소나: {{persona_name}}\n연령/성별: {{persona_age_group}} / {{persona_gender}}\n성격: {{persona_personality}}\n\n핵심 자료:\n{{source_summary}}\n\n금칙어: {{persona_banned_words}}",
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

