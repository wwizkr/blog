from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    keywords: Mapped[list["Keyword"]] = relationship(back_populates="category", cascade="all, delete-orphan")


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    keyword: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    category: Mapped[Category | None] = relationship(back_populates="keywords")



class KeywordRelatedRelation(Base):
    __tablename__ = "keyword_related_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    related_keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), default="content", nullable=False)
    collect_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class KeywordRelatedBlock(Base):
    __tablename__ = "keyword_related_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    related_keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class SourceChannel(Base):
    __tablename__ = "source_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    channel_code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    collected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    keyword: Mapped[Keyword] = relationship()


class RawContent(Base):
    __tablename__ = "raw_contents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword_id: Mapped[int | None] = mapped_column(ForeignKey("keywords.id", ondelete="SET NULL"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    channel_code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    author: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    keyword: Mapped[Keyword | None] = relationship()
    category: Mapped[Category | None] = relationship()
    images: Mapped[list["RawImage"]] = relationship(back_populates="content", cascade="all, delete-orphan")


class RawImage(Base):
    __tablename__ = "raw_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("raw_contents.id", ondelete="CASCADE"), nullable=False)
    image_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    page_url: Mapped[str | None] = mapped_column(String(1000))
    local_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    content: Mapped[RawContent] = relationship(back_populates="images")


class ContentLabel(Base):
    __tablename__ = "content_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("raw_contents.id", ondelete="CASCADE"), unique=True, nullable=False)
    tone: Mapped[str | None] = mapped_column(String(30))
    sentiment: Mapped[str | None] = mapped_column(String(30))
    topics: Mapped[str | None] = mapped_column(Text)  # JSON string
    quality_score: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    label_method: Mapped[str] = mapped_column(String(20), default="rule", nullable=False)
    labeled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    content: Mapped[RawContent] = relationship()


class ImageLabel(Base):
    __tablename__ = "image_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("raw_images.id", ondelete="CASCADE"), unique=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(30))
    mood: Mapped[str | None] = mapped_column(String(30))
    quality_score: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    is_thumbnail_candidate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    label_method: Mapped[str] = mapped_column(String(20), default="rule", nullable=False)
    labeled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    image: Mapped[RawImage] = relationship()


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    age_group: Mapped[str | None] = mapped_column(String(30))
    gender: Mapped[str | None] = mapped_column(String(20))
    personality: Mapped[str | None] = mapped_column(String(200))
    interests: Mapped[str | None] = mapped_column(Text)
    speech_style: Mapped[str | None] = mapped_column(String(120))
    tone: Mapped[str | None] = mapped_column(String(100))
    style_guide: Mapped[str | None] = mapped_column(Text)
    banned_words: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ArticleTemplate(Base):
    __tablename__ = "article_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    template_type: Mapped[str] = mapped_column(String(20), nullable=False)  # blog/sns/board
    system_prompt: Mapped[str | None] = mapped_column(Text)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AIProvider(Base):
    __tablename__ = "ai_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    api_key_alias: Mapped[str | None] = mapped_column(String(120))
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    rate_limit_per_min: Mapped[int | None] = mapped_column(Integer)
    daily_budget_limit: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class WritingChannel(Base):
    __tablename__ = "writing_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(30), default="blog", nullable=False)
    connection_type: Mapped[str] = mapped_column(String(30), default="api", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    owner_name: Mapped[str | None] = mapped_column(String(100))
    channel_identifier: Mapped[str | None] = mapped_column(String(200))
    default_category: Mapped[str | None] = mapped_column(String(120))
    default_visibility: Mapped[str | None] = mapped_column(String(30))
    tag_policy: Mapped[str | None] = mapped_column(String(50))

    title_max_length: Mapped[int | None] = mapped_column(Integer)
    body_min_length: Mapped[int | None] = mapped_column(Integer)
    body_max_length: Mapped[int | None] = mapped_column(Integer)
    allowed_markup: Mapped[str | None] = mapped_column(String(50))

    require_featured_image: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    image_max_count: Mapped[int | None] = mapped_column(Integer)
    image_max_size_kb: Mapped[int | None] = mapped_column(Integer)

    external_link_policy: Mapped[str | None] = mapped_column(String(50))
    affiliate_disclosure_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    meta_desc_max_length: Mapped[int | None] = mapped_column(Integer)
    slug_rule: Mapped[str | None] = mapped_column(String(50))

    publish_frequency_limit: Mapped[int | None] = mapped_column(Integer)
    reserve_publish_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    api_rate_limit: Mapped[int | None] = mapped_column(Integer)
    api_endpoint_url: Mapped[str | None] = mapped_column(String(1000))
    auth_type: Mapped[str | None] = mapped_column(String(30))
    auth_reference: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class GeneratedArticle(Base):
    __tablename__ = "generated_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    format_type: Mapped[str] = mapped_column(String(30), nullable=False)  # blog/sns/board
    persona_id: Mapped[int | None] = mapped_column(ForeignKey("personas.id", ondelete="SET NULL"))
    persona_name: Mapped[str | None] = mapped_column(String(100))
    template_id: Mapped[int | None] = mapped_column(ForeignKey("article_templates.id", ondelete="SET NULL"))
    template_name: Mapped[str | None] = mapped_column(String(120))
    template_version: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    source_content_ids: Mapped[str | None] = mapped_column(Text)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    persona: Mapped[Persona | None] = relationship()
    template: Mapped[ArticleTemplate | None] = relationship()


class PublishJob(Base):
    __tablename__ = "publish_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("generated_articles.id", ondelete="CASCADE"), nullable=False)
    target_channel: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # semi_auto / auto
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)

    article: Mapped[GeneratedArticle] = relationship()


class PublishChannel(Base):
    __tablename__ = "publish_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PublishChannelSetting(Base):
    __tablename__ = "publish_channel_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    publish_cycle_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    publish_mode: Mapped[str] = mapped_column(String(20), default="semi_auto", nullable=False)
    publish_format: Mapped[str] = mapped_column(String(20), default="blog", nullable=False)
    writing_style: Mapped[str] = mapped_column(String(20), default="informative", nullable=False)
    api_url: Mapped[str | None] = mapped_column(String(1000))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)





class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    setting_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    setting_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

