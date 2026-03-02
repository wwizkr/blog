from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from html import unescape
import mimetypes
import re
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
import json
from bs4 import BeautifulSoup

from sqlalchemy import func, select

from core.settings import settings

from storage.database import session_scope
from storage.models import (
    AIProvider,
    AppSetting,
    ArticleTemplate,
    Category,
    ContentLabel,
    CrawlJob,
    GeneratedArticle,
    ImageLabel,
    Keyword,
    KeywordRelatedBlock,
    KeywordRelatedRelation,
    Persona,
    PublishJob,
    PublishChannel,
    PublishChannelSetting,
    RawContent,
    RawImage,
    SourceChannel,
    WritingChannel,
)

_CONTENT_TONE_KO = {
    "informative": "정보형",
    "emotional": "감성형",
    "review": "후기형",
    "정보형": "정보형",
    "감성형": "감성형",
    "후기형": "후기형",
}

_CONTENT_SENTIMENT_KO = {
    "positive": "긍정",
    "negative": "부정",
    "neutral": "중립",
    "긍정": "긍정",
    "부정": "부정",
    "중립": "중립",
}

_CONTENT_TOPIC_KO = {
    "food": "음식",
    "tech": "기술",
    "travel": "여행",
    "beauty": "뷰티",
    "shopping": "쇼핑",
    "general": "일반",
    "음식": "음식",
    "기술": "기술",
    "여행": "여행",
    "뷰티": "뷰티",
    "쇼핑": "쇼핑",
    "일반": "일반",
}

_IMAGE_CATEGORY_KO = {
    "food": "음식",
    "room": "숙소",
    "scenery": "풍경",
    "other": "기타",
    "음식": "음식",
    "숙소": "숙소",
    "풍경": "풍경",
    "기타": "기타",
}

_IMAGE_MOOD_KO = {
    "neutral": "중립",
    "dark": "어두움",
    "bright": "밝음",
    "중립": "중립",
    "어두움": "어두움",
    "밝음": "밝음",
}


def _normalize_content_tone(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return _CONTENT_TONE_KO.get(text, text)


def _normalize_content_sentiment(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return _CONTENT_SENTIMENT_KO.get(text, text)


def _normalize_content_topics(values: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        topic = _CONTENT_TOPIC_KO.get(str(raw or "").strip(), str(raw or "").strip())
        if not topic or topic in seen:
            continue
        seen.add(topic)
        cleaned.append(topic)
    return cleaned


def _normalize_image_category(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return _IMAGE_CATEGORY_KO.get(text, text)


def _normalize_image_mood(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return _IMAGE_MOOD_KO.get(text, text)


@dataclass
class CategoryDTO:
    id: int
    name: str


@dataclass
class KeywordDTO:
    id: int
    keyword: str
    category_id: int | None
    category_name: str | None
    is_active: bool
    is_auto_generated: bool = False
    total_collected_count: int = 0
    last_collected_at: datetime | None = None
    total_published_count: int = 0
    last_published_at: datetime | None = None




@dataclass
class KeywordRelatedDTO:
    relation_id: int
    source_keyword_id: int
    related_keyword_id: int
    related_keyword: str
    collect_count: int
    created_at: datetime
    last_seen_at: datetime

@dataclass
class KeywordRelatedBlockDTO:
    block_id: int
    source_keyword_id: int
    related_keyword: str
    created_at: datetime

@dataclass
class SourceChannelDTO:
    id: int
    code: str
    display_name: str
    is_enabled: bool


@dataclass
class PublishChannelSettingDTO:
    id: int
    channel_code: str
    publish_cycle_minutes: int
    publish_mode: str
    publish_format: str
    writing_style: str
    api_url: str | None


@dataclass
class CrawlJobDTO:
    id: int
    keyword: str
    channel_code: str
    status: str
    collected_count: int
    error_message: str | None
    created_at: datetime


@dataclass
class RawContentDTO:
    id: int
    keyword: str | None
    channel_code: str
    title: str
    source_url: str
    created_at: datetime


@dataclass
class RawImageDTO:
    id: int
    content_id: int
    image_url: str
    source_url: str
    page_url: str | None
    created_at: datetime


@dataclass
class GeneratedArticleDTO:
    id: int
    title: str
    format_type: str
    status: str
    created_at: datetime


@dataclass
class PublishJobDTO:
    id: int
    article_id: int
    target_channel: str
    mode: str
    status: str
    message: str | None
    created_at: datetime


@dataclass
class PublishChannelDTO:
    id: int
    code: str
    display_name: str
    is_enabled: bool


@dataclass
class PersonaDTO:
    id: int
    name: str
    age_group: str | None
    gender: str | None
    personality: str | None
    interests: str | None
    speech_style: str | None
    tone: str | None
    style_guide: str | None
    banned_words: str | None
    is_active: bool


@dataclass
class ArticleTemplateDTO:
    id: int
    name: str
    template_type: str
    system_prompt: str | None
    user_prompt: str
    output_schema: str | None
    is_active: bool
    version: int


@dataclass
class AIProviderDTO:
    id: int
    provider: str
    model_name: str
    api_key_alias: str | None
    is_paid: bool
    is_enabled: bool
    priority: int
    rate_limit_per_min: int | None
    daily_budget_limit: int | None
    status: str
    last_checked_at: datetime | None


@dataclass
class WritingChannelDTO:
    id: int
    code: str
    display_name: str
    channel_type: str
    connection_type: str
    status: str
    is_enabled: bool
    owner_name: str | None
    channel_identifier: str | None
    default_category: str | None
    default_visibility: str | None
    tag_policy: str | None
    title_max_length: int | None
    body_min_length: int | None
    body_max_length: int | None
    allowed_markup: str | None
    require_featured_image: bool
    image_max_count: int | None
    image_max_size_kb: int | None
    external_link_policy: str | None
    affiliate_disclosure_required: bool
    meta_desc_max_length: int | None
    slug_rule: str | None
    publish_frequency_limit: int | None
    reserve_publish_enabled: bool
    api_rate_limit: int | None
    api_endpoint_url: str | None
    auth_type: str | None
    auth_reference: str | None
    notes: str | None


class CategoryRepository:
    @staticmethod
    def list_all() -> list[CategoryDTO]:
        with session_scope() as session:
            rows = session.execute(select(Category).order_by(Category.name.asc())).scalars().all()
            return [CategoryDTO(id=row.id, name=row.name) for row in rows]

    @staticmethod
    def add(name: str) -> bool:
        cleaned = name.strip()
        if not cleaned:
            return False
        with session_scope() as session:
            exists = session.execute(select(Category).where(Category.name == cleaned)).scalar_one_or_none()
            if exists:
                return False
            session.add(Category(name=cleaned))
            return True

    @staticmethod
    def delete(category_id: int) -> None:
        with session_scope() as session:
            target = session.get(Category, category_id)
            if target:
                session.delete(target)

    @staticmethod
    def update(category_id: int, name: str) -> bool:
        cleaned = name.strip()
        if not cleaned:
            return False
        with session_scope() as session:
            target = session.get(Category, category_id)
            if not target:
                return False
            exists = session.execute(
                select(Category).where(Category.name == cleaned, Category.id != category_id)
            ).scalar_one_or_none()
            if exists:
                return False
            target.name = cleaned
            return True


class KeywordRepository:
    @staticmethod
    def list_all() -> list[KeywordDTO]:
        with session_scope() as session:
            rows = session.execute(select(Keyword).order_by(Keyword.created_at.desc())).scalars().all()
            if not rows:
                return []

            keyword_ids = [row.id for row in rows]
            total_collected_count: dict[int, int] = {keyword_id: 0 for keyword_id in keyword_ids}
            last_collected_at: dict[int, datetime | None] = {keyword_id: None for keyword_id in keyword_ids}

            content_rows = session.execute(
                select(RawContent.id, RawContent.keyword_id, RawContent.created_at)
                .where(RawContent.keyword_id.in_(keyword_ids))
            ).all()

            content_keyword_map: dict[int, int] = {}
            for content_id, keyword_id, created_at in content_rows:
                if keyword_id is None:
                    continue
                k = int(keyword_id)
                content_keyword_map[int(content_id)] = k
                total_collected_count[k] = total_collected_count.get(k, 0) + 1
                current_last = last_collected_at.get(k)
                if current_last is None or (created_at and created_at > current_last):
                    last_collected_at[k] = created_at

            total_published_count: dict[int, int] = {keyword_id: 0 for keyword_id in keyword_ids}
            last_published_at: dict[int, datetime | None] = {keyword_id: None for keyword_id in keyword_ids}

            publish_rows = session.execute(
                select(PublishJob.article_id, PublishJob.processed_at, PublishJob.created_at)
                .where(PublishJob.status == "done")
            ).all()
            article_ids = list({int(article_id) for article_id, _, _ in publish_rows if article_id is not None})

            article_map: dict[int, str | None] = {}
            if article_ids:
                article_rows = session.execute(
                    select(GeneratedArticle.id, GeneratedArticle.source_content_ids)
                    .where(GeneratedArticle.id.in_(article_ids))
                ).all()
                article_map = {int(article_id): source_content_ids for article_id, source_content_ids in article_rows}

            for article_id, processed_at, created_at in publish_rows:
                if article_id is None:
                    continue
                source_content_ids = article_map.get(int(article_id))
                if not source_content_ids:
                    continue
                try:
                    content_ids = json.loads(source_content_ids)
                except Exception:
                    content_ids = []
                if not isinstance(content_ids, list):
                    continue

                keyword_set: set[int] = set()
                for content_id in content_ids:
                    try:
                        key = content_keyword_map.get(int(content_id))
                    except (TypeError, ValueError):
                        key = None
                    if key is not None:
                        keyword_set.add(key)

                published_at = processed_at or created_at
                for keyword_id in keyword_set:
                    total_published_count[keyword_id] = total_published_count.get(keyword_id, 0) + 1
                    current_last = last_published_at.get(keyword_id)
                    if current_last is None or (published_at and published_at > current_last):
                        last_published_at[keyword_id] = published_at

            result: list[KeywordDTO] = []
            for row in rows:
                result.append(
                    KeywordDTO(
                        id=row.id,
                        keyword=row.keyword,
                        category_id=row.category_id,
                        category_name=row.category.name if row.category else None,
                        is_active=row.is_active,
                        is_auto_generated=row.is_auto_generated,
                        total_collected_count=total_collected_count.get(row.id, 0),
                        last_collected_at=last_collected_at.get(row.id),
                        total_published_count=total_published_count.get(row.id, 0),
                        last_published_at=last_published_at.get(row.id),
                    )
                )
            return result
    @staticmethod
    def add(keyword: str, category_id: int | None, is_auto_generated: bool = False) -> bool:
        cleaned = keyword.strip()
        if not cleaned:
            return False
        with session_scope() as session:
            exists = session.execute(select(Keyword).where(Keyword.keyword == cleaned)).scalar_one_or_none()
            if exists:
                return False
            session.add(Keyword(keyword=cleaned, category_id=category_id, is_active=True, is_auto_generated=is_auto_generated))
            return True

    @staticmethod
    def add_or_get(keyword: str, category_id: int | None, is_auto_generated: bool = False) -> int | None:
        cleaned = keyword.strip()
        if not cleaned:
            return None
        with session_scope() as session:
            exists = session.execute(select(Keyword).where(Keyword.keyword == cleaned)).scalar_one_or_none()
            if exists:
                return exists.id
            row = Keyword(keyword=cleaned, category_id=category_id, is_active=True, is_auto_generated=is_auto_generated)
            session.add(row)
            session.flush()
            return row.id

    @staticmethod
    def get_by_id(keyword_id: int) -> Keyword | None:
        with session_scope() as session:
            return session.get(Keyword, keyword_id)

    @staticmethod
    def delete(keyword_id: int) -> None:
        with session_scope() as session:
            target = session.get(Keyword, keyword_id)
            if target:
                session.delete(target)

    @staticmethod
    def toggle(keyword_id: int) -> None:
        with session_scope() as session:
            target = session.get(Keyword, keyword_id)
            if target:
                target.is_active = not target.is_active

    @staticmethod
    def list_active() -> list[KeywordDTO]:
        with session_scope() as session:
            rows = session.execute(select(Keyword).where(Keyword.is_active == True).order_by(Keyword.keyword.asc())).scalars().all()
            return [
                KeywordDTO(
                    id=row.id,
                    keyword=row.keyword,
                    category_id=row.category_id,
                    category_name=row.category.name if row.category else None,
                    is_active=row.is_active,
                    is_auto_generated=row.is_auto_generated,
                )
                for row in rows
            ]

    @staticmethod
    def count_related_keywords(source_keyword_id: int) -> int:
        with session_scope() as session:
            count = session.execute(
                select(func.count()).select_from(KeywordRelatedRelation).where(
                    KeywordRelatedRelation.source_keyword_id == source_keyword_id
                )
            ).scalar_one()
            return int(count or 0)

    @staticmethod
    def has_related_relation(source_keyword_id: int, related_keyword_id: int) -> bool:
        with session_scope() as session:
            row = session.execute(
                select(KeywordRelatedRelation.id).where(
                    KeywordRelatedRelation.source_keyword_id == source_keyword_id,
                    KeywordRelatedRelation.related_keyword_id == related_keyword_id,
                )
            ).first()
            return row is not None

    @staticmethod
    def is_blocked_related(source_keyword_id: int, related_keyword: str) -> bool:
        cleaned = related_keyword.strip()
        if not cleaned:
            return True
        with session_scope() as session:
            row = session.execute(
                select(KeywordRelatedBlock).where(
                    KeywordRelatedBlock.source_keyword_id == source_keyword_id,
                    KeywordRelatedBlock.related_keyword == cleaned,
                )
            ).scalar_one_or_none()
            return row is not None

    @staticmethod
    def upsert_related_relation(source_keyword_id: int, related_keyword_id: int, source_type: str = "content") -> None:
        if source_keyword_id == related_keyword_id:
            return
        with session_scope() as session:
            row = session.execute(
                select(KeywordRelatedRelation).where(
                    KeywordRelatedRelation.source_keyword_id == source_keyword_id,
                    KeywordRelatedRelation.related_keyword_id == related_keyword_id,
                )
            ).scalar_one_or_none()
            if row:
                row.collect_count += 1
                row.last_seen_at = datetime.utcnow()
                return
            session.add(
                KeywordRelatedRelation(
                    source_keyword_id=source_keyword_id,
                    related_keyword_id=related_keyword_id,
                    source_type=source_type,
                    collect_count=1,
                    last_seen_at=datetime.utcnow(),
                )
            )

    @staticmethod
    def list_related_keywords(source_keyword_id: int) -> list[KeywordRelatedDTO]:
        with session_scope() as session:
            rows = session.execute(
                select(KeywordRelatedRelation)
                .where(KeywordRelatedRelation.source_keyword_id == source_keyword_id)
                .order_by(KeywordRelatedRelation.last_seen_at.desc())
            ).scalars().all()
            result: list[KeywordRelatedDTO] = []
            for row in rows:
                related = session.get(Keyword, row.related_keyword_id)
                if not related:
                    continue
                result.append(
                    KeywordRelatedDTO(
                        relation_id=row.id,
                        source_keyword_id=row.source_keyword_id,
                        related_keyword_id=row.related_keyword_id,
                        related_keyword=related.keyword,
                        collect_count=row.collect_count,
                        created_at=row.created_at,
                        last_seen_at=row.last_seen_at,
                    )
                )
            return result

    @staticmethod
    def list_related_blocks(source_keyword_id: int) -> list[KeywordRelatedBlockDTO]:
        with session_scope() as session:
            rows = session.execute(
                select(KeywordRelatedBlock)
                .where(KeywordRelatedBlock.source_keyword_id == source_keyword_id)
                .order_by(KeywordRelatedBlock.created_at.desc())
            ).scalars().all()
            return [
                KeywordRelatedBlockDTO(
                    block_id=row.id,
                    source_keyword_id=row.source_keyword_id,
                    related_keyword=row.related_keyword,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    @staticmethod
    def unblock_related_block(block_id: int) -> None:
        with session_scope() as session:
            target = session.get(KeywordRelatedBlock, block_id)
            if target:
                session.delete(target)

    @staticmethod
    def block_and_remove_related(source_keyword_id: int, related_keyword_id: int) -> None:
        with session_scope() as session:
            related = session.get(Keyword, related_keyword_id)
            if not related:
                return

            block_exists = session.execute(
                select(KeywordRelatedBlock).where(
                    KeywordRelatedBlock.source_keyword_id == source_keyword_id,
                    KeywordRelatedBlock.related_keyword == related.keyword,
                )
            ).scalar_one_or_none()
            if not block_exists:
                session.add(
                    KeywordRelatedBlock(
                        source_keyword_id=source_keyword_id,
                        related_keyword=related.keyword,
                    )
                )

            relation = session.execute(
                select(KeywordRelatedRelation).where(
                    KeywordRelatedRelation.source_keyword_id == source_keyword_id,
                    KeywordRelatedRelation.related_keyword_id == related_keyword_id,
                )
            ).scalar_one_or_none()
            if relation:
                session.delete(relation)

            related_ref_count = session.execute(
                select(func.count()).select_from(KeywordRelatedRelation).where(
                    KeywordRelatedRelation.related_keyword_id == related_keyword_id
                )
            ).scalar_one()
            if int(related_ref_count or 0) == 0 and related.is_auto_generated:
                related.is_active = False

class SourceChannelRepository:
    @staticmethod
    def list_all() -> list[SourceChannelDTO]:
        with session_scope() as session:
            rows = session.execute(select(SourceChannel).order_by(SourceChannel.display_name.asc())).scalars().all()
            return [
                SourceChannelDTO(id=row.id, code=row.code, display_name=row.display_name, is_enabled=row.is_enabled)
                for row in rows
            ]

    @staticmethod
    def list_enabled_codes() -> list[str]:
        with session_scope() as session:
            rows = session.execute(select(SourceChannel).where(SourceChannel.is_enabled == True)).scalars().all()
            return [row.code for row in rows]

    @staticmethod
    def toggle(channel_id: int) -> None:
        with session_scope() as session:
            target = session.get(SourceChannel, channel_id)
            if target:
                target.is_enabled = not target.is_enabled

    @staticmethod
    def sync_from_collectors(channels: list[tuple[str, str]]) -> None:
        with session_scope() as session:
            existing = {row.code: row for row in session.execute(select(SourceChannel)).scalars().all()}
            for code, display_name in channels:
                row = existing.get(code)
                if row:
                    row.display_name = display_name
                else:
                    session.add(SourceChannel(code=code, display_name=display_name, is_enabled=True))


class CrawlRepository:
    @staticmethod
    def create_job(keyword_id: int, channel_code: str) -> int:
        with session_scope() as session:
            job = CrawlJob(
                keyword_id=keyword_id,
                channel_code=channel_code,
                status="pending",
                collected_count=0,
            )
            session.add(job)
            session.flush()
            return job.id

    @staticmethod
    def mark_started(job_id: int) -> None:
        with session_scope() as session:
            job = session.get(CrawlJob, job_id)
            if job:
                job.status = "running"
                job.started_at = datetime.utcnow()

    @staticmethod
    def mark_finished(job_id: int, collected_count: int) -> None:
        with session_scope() as session:
            job = session.get(CrawlJob, job_id)
            if job:
                job.status = "completed"
                job.collected_count = collected_count
                job.finished_at = datetime.utcnow()

    @staticmethod
    def mark_failed(job_id: int, message: str) -> None:
        with session_scope() as session:
            job = session.get(CrawlJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = message[:500]
                job.finished_at = datetime.utcnow()

    @staticmethod
    def _image_store_dir() -> Path:
        base = settings.data_dir / "collected_images"
        base.mkdir(parents=True, exist_ok=True)
        return base

    @staticmethod
    def _guess_extension(image_url: str, content_type: str | None) -> str:
        path_ext = Path(urlparse(image_url).path).suffix.lower()
        if path_ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}:
            return path_ext
        if content_type:
            guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
            if guessed:
                return guessed
        return ".jpg"

    @staticmethod
    def _download_image_to_local(image_url: str, content_id: int) -> str | None:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            }
            response = requests.get(image_url, headers=headers, timeout=15)
            response.raise_for_status()
            content = response.content
            if not content:
                return None
            if len(content) > 15 * 1024 * 1024:
                return None

            ext = CrawlRepository._guess_extension(image_url, response.headers.get("Content-Type"))
            digest = hashlib.sha1(image_url.encode("utf-8")).hexdigest()[:16]
            day_dir = CrawlRepository._image_store_dir() / datetime.utcnow().strftime("%Y%m%d")
            day_dir.mkdir(parents=True, exist_ok=True)
            filename = f"c{content_id}_{digest}{ext}"
            file_path = day_dir / filename
            file_path.write_bytes(content)
            return str(file_path)
        except Exception:
            return None

    @staticmethod
    def _get_naver_type_width(url: str) -> int:
        try:
            parsed = urlparse(url)
            q = parse_qs(parsed.query or "")
            type_val = (q.get("type") or [""])[0].lower()
            m = re.match(r"^w(\d+)$", type_val)
            if m:
                return int(m.group(1))
        except Exception:
            return 0
        return 0

    @staticmethod
    def _set_naver_type(url: str, width: int) -> str:
        if not url:
            return ""
        width = 966
        try:
            parsed = urlparse(url)
            q = parse_qs(parsed.query or "")
            q["type"] = [f"w{width}"]
            return urlunparse(parsed._replace(query=urlencode(q, doseq=True)))
        except Exception:
            connector = "&" if "?" in url else "?"
            return f"{url}{connector}type=w{width}"

    @staticmethod
    def _normalize_naver_image_url(url: str) -> str:
        if not url:
            return ""
        try:
            parsed = urlparse(url)
        except Exception:
            return url
        host = (parsed.netloc or "").lower()
        if host == "mblogthumb-phinf.pstatic.net":
            return CrawlRepository._set_naver_type(url, 966)
        return url

    @staticmethod
    def _normalize_naver_body_html_images(body_html: str) -> str:
        if not body_html or "<img" not in body_html.lower():
            return body_html

        soup = BeautifulSoup(body_html, "html.parser")
        changed = False
        for img in soup.select("img"):
            candidates: list[str] = []

            def _push(value: str | None) -> None:
                v = str(value or "").strip()
                if not v or v.startswith("data:"):
                    return
                if v.startswith("//"):
                    v = f"https:{v}"
                lowered = v.lower()
                if "ssl.pstatic.net/static/blog/blank.gif" in lowered:
                    return
                if "/original_4.gif" in lowered:
                    return
                if v not in candidates:
                    candidates.append(v)

            for attr in ["data-lazy-src", "data-src", "src"]:
                _push(img.get(attr))

            parent = img
            for _ in range(5):
                parent = parent.parent if parent else None
                if parent is None:
                    break
                raw = parent.get("data-linkdata")
                if not raw:
                    continue
                try:
                    data = json.loads(unescape(str(raw)))
                except Exception:
                    break
                src = str(data.get("src") or "").strip()
                _push(src)
                try:
                    original_width = int(str(data.get("originalWidth") or "0"))
                except Exception:
                    original_width = 0
                if src and original_width > 0:
                    _push(CrawlRepository._set_naver_type(src, original_width))
                break

            if not candidates:
                img.decompose()
                changed = True
                continue

            best = sorted(
                candidates,
                key=lambda u: (CrawlRepository._get_naver_type_width(u), len(u)),
                reverse=True,
            )[0]
            normalized = CrawlRepository._normalize_naver_image_url(best)
            if not normalized:
                continue

            if (img.get("src") or "").strip() != normalized:
                img["src"] = normalized
                changed = True
            if img.get("data-lazy-src") is not None and (img.get("data-lazy-src") or "").strip() != normalized:
                img["data-lazy-src"] = normalized
                changed = True

        return str(soup) if changed else body_html
    @staticmethod
    def save_raw_contents(
        keyword_id: int,
        category_id: int | None,
        channel_code: str,
        rows: list[dict],
    ) -> int:
        with session_scope() as session:
            inserted = 0
            for row in rows:
                source_url = str(row.get("source_url") or "").strip()
                if not source_url:
                    continue
                exists = session.execute(select(RawContent).where(RawContent.source_url == source_url)).scalar_one_or_none()
                if exists:
                    continue

                body_html = str(row.get("body_html") or "").strip()
                if channel_code == "naver_blog" and body_html:
                    body_html = CrawlRepository._normalize_naver_body_html_images(body_html)
                body_text = str(row.get("body_text") or "").strip()
                payload_body = body_html or body_text
                if not payload_body:
                    continue

                item = RawContent(
                    keyword_id=keyword_id,
                    category_id=category_id,
                    channel_code=channel_code,
                    title=str(row.get("title") or "")[:500] or "(제목없음)",
                    body_text=payload_body,
                    source_url=source_url,
                    author=(str(row.get("author") or "").strip() or None),
                )
                session.add(item)
                session.flush()

                for image_url in row.get("images", []):
                    image_url = str(image_url or "").strip()
                    if not image_url:
                        continue
                    image_exists = session.execute(select(RawImage).where(RawImage.source_url == image_url)).scalar_one_or_none()
                    if image_exists:
                        continue

                    local_path = CrawlRepository._download_image_to_local(image_url=image_url, content_id=item.id)
                    session.add(
                        RawImage(
                            content_id=item.id,
                            image_url=image_url,
                            source_url=image_url,
                            page_url=source_url,
                            local_path=local_path,
                        )
                    )
                inserted += 1
            return inserted

    @staticmethod
    def list_recent_jobs(limit: int = 50) -> list[CrawlJobDTO]:
        with session_scope() as session:
            rows = session.execute(select(CrawlJob).order_by(CrawlJob.created_at.desc()).limit(limit)).scalars().all()
            result: list[CrawlJobDTO] = []
            for row in rows:
                result.append(
                    CrawlJobDTO(
                        id=row.id,
                        keyword=row.keyword.keyword if row.keyword else "-",
                        channel_code=row.channel_code,
                        status=row.status,
                        collected_count=row.collected_count,
                        error_message=row.error_message,
                        created_at=row.created_at,
                    )
                )
            return result

    @staticmethod
    def list_recent_contents(limit: int = 50) -> list[RawContentDTO]:
        with session_scope() as session:
            rows = session.execute(select(RawContent).order_by(RawContent.created_at.desc()).limit(limit)).scalars().all()
            return [
                RawContentDTO(
                    id=row.id,
                    keyword=row.keyword.keyword if row.keyword else None,
                    channel_code=row.channel_code,
                    title=row.title,
                    source_url=row.source_url,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    @staticmethod
    def list_unlabeled_contents(limit: int = 200) -> list[RawContent]:
        with session_scope() as session:
            labeled_subquery = select(ContentLabel.content_id)
            rows = session.execute(
                select(RawContent).where(~RawContent.id.in_(labeled_subquery)).order_by(RawContent.created_at.desc()).limit(limit)
            ).scalars().all()
            return rows

    @staticmethod
    def list_unlabeled_images(limit: int = 500) -> list[RawImage]:
        with session_scope() as session:
            labeled_subquery = select(ImageLabel.image_id)
            rows = session.execute(
                select(RawImage).where(~RawImage.id.in_(labeled_subquery)).order_by(RawImage.created_at.desc()).limit(limit)
            ).scalars().all()
            return rows


class LabelRepository:
    @staticmethod
    def upsert_content_label(content_id: int, tone: str | None, sentiment: str | None, topics: list[str], quality_score: int) -> None:
        normalized_tone = _normalize_content_tone(tone)
        normalized_sentiment = _normalize_content_sentiment(sentiment)
        normalized_topics = _normalize_content_topics(topics)
        with session_scope() as session:
            existing = session.execute(select(ContentLabel).where(ContentLabel.content_id == content_id)).scalar_one_or_none()
            payload = json.dumps(normalized_topics, ensure_ascii=False)
            if existing:
                existing.tone = normalized_tone
                existing.sentiment = normalized_sentiment
                existing.topics = payload
                existing.quality_score = quality_score
                existing.label_method = "rule"
                existing.labeled_at = datetime.utcnow()
                return
            session.add(
                ContentLabel(
                    content_id=content_id,
                    tone=normalized_tone,
                    sentiment=normalized_sentiment,
                    topics=payload,
                    quality_score=quality_score,
                    label_method="rule",
                )
            )

    @staticmethod
    def upsert_image_label(
        image_id: int,
        category: str | None,
        mood: str | None,
        quality_score: int,
        is_thumbnail_candidate: bool,
    ) -> None:
        normalized_category = _normalize_image_category(category)
        normalized_mood = _normalize_image_mood(mood)
        with session_scope() as session:
            existing = session.execute(select(ImageLabel).where(ImageLabel.image_id == image_id)).scalar_one_or_none()
            if existing:
                existing.category = normalized_category
                existing.mood = normalized_mood
                existing.quality_score = quality_score
                existing.is_thumbnail_candidate = is_thumbnail_candidate
                existing.label_method = "rule"
                existing.labeled_at = datetime.utcnow()
                return
            session.add(
                ImageLabel(
                    image_id=image_id,
                    category=normalized_category,
                    mood=normalized_mood,
                    quality_score=quality_score,
                    is_thumbnail_candidate=is_thumbnail_candidate,
                    label_method="rule",
                )
            )

    @staticmethod
    def get_label_stats() -> dict:
        with session_scope() as session:
            content_total = session.execute(select(RawContent)).scalars().all()
            image_total = session.execute(select(RawImage)).scalars().all()
            content_labeled = session.execute(select(ContentLabel)).scalars().all()
            image_labeled = session.execute(select(ImageLabel)).scalars().all()
            return {
                "contents_total": len(content_total),
                "contents_labeled": len(content_labeled),
                "images_total": len(image_total),
                "images_labeled": len(image_labeled),
            }


class PersonaRepository:
    @staticmethod
    def list_all(active_only: bool = False) -> list[PersonaDTO]:
        with session_scope() as session:
            stmt = select(Persona)
            if active_only:
                stmt = stmt.where(Persona.is_active == True)
            rows = session.execute(stmt.order_by(Persona.name.asc())).scalars().all()
            return [
                PersonaDTO(
                    id=row.id,
                    name=row.name,
                    age_group=row.age_group,
                    gender=row.gender,
                    personality=row.personality,
                    interests=row.interests,
                    speech_style=row.speech_style,
                    tone=row.tone,
                    style_guide=row.style_guide,
                    banned_words=row.banned_words,
                    is_active=row.is_active,
                )
                for row in rows
            ]

    @staticmethod
    def add(
        name: str,
        age_group: str | None = None,
        gender: str | None = None,
        personality: str | None = None,
        interests: str | None = None,
        speech_style: str | None = None,
        tone: str | None = None,
        style_guide: str | None = None,
        banned_words: str | None = None,
    ) -> bool:
        cleaned_name = name.strip()
        if not cleaned_name:
            return False
        with session_scope() as session:
            exists = session.execute(select(Persona).where(Persona.name == cleaned_name)).scalar_one_or_none()
            if exists:
                return False
            session.add(
                Persona(
                    name=cleaned_name,
                    age_group=(age_group or '').strip() or None,
                    gender=(gender or '').strip() or None,
                    personality=(personality or '').strip() or None,
                    interests=(interests or '').strip() or None,
                    speech_style=(speech_style or '').strip() or None,
                    tone=(tone or '').strip() or None,
                    style_guide=(style_guide or '').strip() or None,
                    banned_words=(banned_words or '').strip() or None,
                    is_active=True,
                    updated_at=datetime.utcnow(),
                )
            )
            return True

    @staticmethod
    def update(
        persona_id: int,
        name: str,
        age_group: str | None,
        gender: str | None,
        personality: str | None,
        interests: str | None,
        speech_style: str | None,
        tone: str | None,
        style_guide: str | None,
        banned_words: str | None,
        is_active: bool,
    ) -> bool:
        cleaned_name = name.strip()
        if not cleaned_name:
            return False
        with session_scope() as session:
            target = session.get(Persona, persona_id)
            if not target:
                return False
            duplicate = session.execute(select(Persona).where(Persona.name == cleaned_name, Persona.id != persona_id)).scalar_one_or_none()
            if duplicate:
                return False
            target.name = cleaned_name
            target.age_group = (age_group or '').strip() or None
            target.gender = (gender or '').strip() or None
            target.personality = (personality or '').strip() or None
            target.interests = (interests or '').strip() or None
            target.speech_style = (speech_style or '').strip() or None
            target.tone = (tone or '').strip() or None
            target.style_guide = (style_guide or '').strip() or None
            target.banned_words = (banned_words or '').strip() or None
            target.is_active = is_active
            target.updated_at = datetime.utcnow()
            return True

    @staticmethod
    def delete(persona_id: int) -> None:
        with session_scope() as session:
            target = session.get(Persona, persona_id)
            if target:
                session.delete(target)

    @staticmethod
    def get_by_id(persona_id: int) -> Persona | None:
        with session_scope() as session:
            return session.get(Persona, persona_id)

class ArticleTemplateRepository:
    @staticmethod
    def list_all(template_type: str | None = None, active_only: bool = False) -> list[ArticleTemplateDTO]:
        with session_scope() as session:
            stmt = select(ArticleTemplate)
            if template_type:
                stmt = stmt.where(ArticleTemplate.template_type == template_type)
            if active_only:
                stmt = stmt.where(ArticleTemplate.is_active == True)
            rows = session.execute(stmt.order_by(ArticleTemplate.template_type.asc(), ArticleTemplate.name.asc())).scalars().all()
            return [
                ArticleTemplateDTO(
                    id=row.id,
                    name=row.name,
                    template_type=row.template_type,
                    system_prompt=row.system_prompt,
                    user_prompt=row.user_prompt,
                    output_schema=row.output_schema,
                    is_active=row.is_active,
                    version=row.version,
                )
                for row in rows
            ]

    @staticmethod
    def add(
        name: str,
        template_type: str,
        user_prompt: str,
        system_prompt: str | None = None,
        output_schema: str | None = None,
    ) -> bool:
        cleaned_name = name.strip()
        cleaned_type = template_type.strip()
        cleaned_user_prompt = user_prompt.strip()
        if not cleaned_name or not cleaned_type or not cleaned_user_prompt:
            return False
        with session_scope() as session:
            exists = session.execute(
                select(ArticleTemplate).where(
                    ArticleTemplate.name == cleaned_name,
                    ArticleTemplate.template_type == cleaned_type,
                )
            ).scalar_one_or_none()
            if exists:
                return False
            session.add(
                ArticleTemplate(
                    name=cleaned_name,
                    template_type=cleaned_type,
                    user_prompt=cleaned_user_prompt,
                    system_prompt=(system_prompt or "").strip() or None,
                    output_schema=(output_schema or "").strip() or None,
                    is_active=True,
                    version=1,
                    updated_at=datetime.utcnow(),
                )
            )
            return True

    @staticmethod
    def update(
        template_id: int,
        name: str,
        template_type: str,
        user_prompt: str,
        system_prompt: str | None,
        output_schema: str | None,
        is_active: bool,
        version: int,
    ) -> bool:
        cleaned_name = name.strip()
        cleaned_type = template_type.strip()
        cleaned_user_prompt = user_prompt.strip()
        if not cleaned_name or not cleaned_type or not cleaned_user_prompt:
            return False
        with session_scope() as session:
            target = session.get(ArticleTemplate, template_id)
            if not target:
                return False
            duplicate = session.execute(
                select(ArticleTemplate).where(
                    ArticleTemplate.name == cleaned_name,
                    ArticleTemplate.template_type == cleaned_type,
                    ArticleTemplate.id != template_id,
                )
            ).scalar_one_or_none()
            if duplicate:
                return False
            target.name = cleaned_name
            target.template_type = cleaned_type
            target.user_prompt = cleaned_user_prompt
            target.system_prompt = (system_prompt or "").strip() or None
            target.output_schema = (output_schema or "").strip() or None
            target.is_active = is_active
            target.version = max(1, version)
            target.updated_at = datetime.utcnow()
            return True

    @staticmethod
    def delete(template_id: int) -> None:
        with session_scope() as session:
            target = session.get(ArticleTemplate, template_id)
            if target:
                session.delete(target)

    @staticmethod
    def get_by_id(template_id: int) -> ArticleTemplate | None:
        with session_scope() as session:
            return session.get(ArticleTemplate, template_id)


class AIProviderRepository:
    @staticmethod
    def list_all(enabled_only: bool = False) -> list[AIProviderDTO]:
        with session_scope() as session:
            stmt = select(AIProvider)
            if enabled_only:
                stmt = stmt.where(AIProvider.is_enabled == True)
            rows = session.execute(stmt.order_by(AIProvider.priority.asc(), AIProvider.id.asc())).scalars().all()
            return [
                AIProviderDTO(
                    id=row.id,
                    provider=row.provider,
                    model_name=row.model_name,
                    api_key_alias=row.api_key_alias,
                    is_paid=row.is_paid,
                    is_enabled=row.is_enabled,
                    priority=row.priority,
                    rate_limit_per_min=row.rate_limit_per_min,
                    daily_budget_limit=row.daily_budget_limit,
                    status=row.status,
                    last_checked_at=row.last_checked_at,
                )
                for row in rows
            ]

    @staticmethod
    def add(
        provider: str,
        model_name: str,
        api_key_alias: str | None,
        is_paid: bool,
        priority: int,
        rate_limit_per_min: int | None,
        daily_budget_limit: int | None,
        status: str,
    ) -> bool:
        p = provider.strip()
        m = model_name.strip()
        if not p or not m:
            return False
        with session_scope() as session:
            session.add(
                AIProvider(
                    provider=p,
                    model_name=m,
                    api_key_alias=(api_key_alias or '').strip() or None,
                    is_paid=is_paid,
                    is_enabled=True,
                    priority=max(1, priority),
                    rate_limit_per_min=rate_limit_per_min,
                    daily_budget_limit=daily_budget_limit,
                    status=(status or 'unknown').strip() or 'unknown',
                    updated_at=datetime.utcnow(),
                )
            )
            return True

    @staticmethod
    def update(
        provider_id: int,
        provider: str,
        model_name: str,
        api_key_alias: str | None,
        is_paid: bool,
        is_enabled: bool,
        priority: int,
        rate_limit_per_min: int | None,
        daily_budget_limit: int | None,
        status: str,
    ) -> bool:
        p = provider.strip()
        m = model_name.strip()
        if not p or not m:
            return False
        with session_scope() as session:
            row = session.get(AIProvider, provider_id)
            if not row:
                return False
            row.provider = p
            row.model_name = m
            row.api_key_alias = (api_key_alias or '').strip() or None
            row.is_paid = is_paid
            row.is_enabled = is_enabled
            row.priority = max(1, priority)
            row.rate_limit_per_min = rate_limit_per_min
            row.daily_budget_limit = daily_budget_limit
            row.status = (status or 'unknown').strip() or 'unknown'
            row.updated_at = datetime.utcnow()
            return True

    @staticmethod
    def delete(provider_id: int) -> None:
        with session_scope() as session:
            row = session.get(AIProvider, provider_id)
            if row:
                session.delete(row)

    @staticmethod
    def get_by_id(provider_id: int) -> AIProvider | None:
        with session_scope() as session:
            return session.get(AIProvider, provider_id)

class ArticleRepository:
    @staticmethod
    def add(
        title: str,
        content: str,
        format_type: str,
        persona_name: str | None,
        source_content_ids: list[int] | None,
        persona_id: int | None = None,
        template_id: int | None = None,
        template_name: str | None = None,
        template_version: int | None = None,
    ) -> int:
        with session_scope() as session:
            row = GeneratedArticle(
                title=title.strip()[:500],
                content=content,
                format_type=format_type,
                persona_id=persona_id,
                persona_name=persona_name,
                template_id=template_id,
                template_name=template_name,
                template_version=template_version,
                status="draft",
                source_content_ids=json.dumps(source_content_ids or []),
            )
            session.add(row)
            session.flush()
            return row.id

    @staticmethod
    def update_content(article_id: int, title: str, content: str) -> None:
        with session_scope() as session:
            row = session.get(GeneratedArticle, article_id)
            if row:
                row.title = title[:500]
                row.content = content
                row.updated_at = datetime.utcnow()

    @staticmethod
    def update_status(article_id: int, status: str) -> None:
        with session_scope() as session:
            row = session.get(GeneratedArticle, article_id)
            if row:
                row.status = status
                row.updated_at = datetime.utcnow()

    @staticmethod
    def list_recent(limit: int = 100) -> list[GeneratedArticleDTO]:
        with session_scope() as session:
            rows = session.execute(select(GeneratedArticle).order_by(GeneratedArticle.created_at.desc()).limit(limit)).scalars().all()
            return [
                GeneratedArticleDTO(
                    id=row.id,
                    title=row.title,
                    format_type=row.format_type,
                    status=row.status,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    @staticmethod
    def get_by_id(article_id: int) -> GeneratedArticle | None:
        with session_scope() as session:
            row = session.get(GeneratedArticle, article_id)
            return row


class PublishRepository:
    @staticmethod
    def enqueue(article_id: int, target_channel: str, mode: str) -> int:
        with session_scope() as session:
            row = PublishJob(
                article_id=article_id,
                target_channel=target_channel,
                mode=mode,
                status="queued",
            )
            session.add(row)
            session.flush()
            return row.id

    @staticmethod
    def list_recent(limit: int = 100) -> list[PublishJobDTO]:
        with session_scope() as session:
            rows = session.execute(select(PublishJob).order_by(PublishJob.created_at.desc()).limit(limit)).scalars().all()
            return [
                PublishJobDTO(
                    id=row.id,
                    article_id=row.article_id,
                    target_channel=row.target_channel,
                    mode=row.mode,
                    status=row.status,
                    message=row.message,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    @staticmethod
    def mark_processing(job_id: int) -> None:
        with session_scope() as session:
            row = session.get(PublishJob, job_id)
            if row:
                row.status = "processing"

    @staticmethod
    def mark_done(job_id: int, message: str = "발행 성공") -> None:
        with session_scope() as session:
            row = session.get(PublishJob, job_id)
            if row:
                row.status = "done"
                row.message = message[:500]
                row.processed_at = datetime.utcnow()

    @staticmethod
    def mark_failed(job_id: int, message: str) -> None:
        with session_scope() as session:
            row = session.get(PublishJob, job_id)
            if row:
                row.status = "failed"
                row.message = message[:500]
                row.processed_at = datetime.utcnow()


class PublishChannelSettingRepository:
    @staticmethod
    def ensure_for_channels(channel_codes: list[str]) -> None:
        with session_scope() as session:
            existing = {
                row.channel_code
                for row in session.execute(select(PublishChannelSetting)).scalars().all()
            }
            for code in channel_codes:
                if code in existing:
                    continue
                session.add(
                    PublishChannelSetting(
                        channel_code=code,
                        publish_cycle_minutes=60,
                        publish_mode="semi_auto",
                        publish_format="blog",
                        writing_style="informative",
                        api_url=None,
                        updated_at=datetime.utcnow(),
                    )
                )

    @staticmethod
    def list_all() -> list[PublishChannelSettingDTO]:
        with session_scope() as session:
            rows = session.execute(select(PublishChannelSetting).order_by(PublishChannelSetting.channel_code.asc())).scalars().all()
            return [
                PublishChannelSettingDTO(
                    id=row.id,
                    channel_code=row.channel_code,
                    publish_cycle_minutes=row.publish_cycle_minutes,
                    publish_mode=row.publish_mode,
                    publish_format=row.publish_format,
                    writing_style=row.writing_style,
                    api_url=row.api_url,
                )
                for row in rows
            ]

    @staticmethod
    def upsert(
        channel_code: str,
        publish_cycle_minutes: int,
        publish_mode: str,
        publish_format: str,
        writing_style: str,
        api_url: str | None,
    ) -> None:
        with session_scope() as session:
            row = session.execute(
                select(PublishChannelSetting).where(PublishChannelSetting.channel_code == channel_code)
            ).scalar_one_or_none()
            if row:
                row.publish_cycle_minutes = publish_cycle_minutes
                row.publish_mode = publish_mode
                row.publish_format = publish_format
                row.writing_style = writing_style
                row.api_url = (api_url or "").strip() or None
                row.updated_at = datetime.utcnow()
                return
            session.add(
                PublishChannelSetting(
                    channel_code=channel_code,
                    publish_cycle_minutes=publish_cycle_minutes,
                    publish_mode=publish_mode,
                    publish_format=publish_format,
                    writing_style=writing_style,
                    api_url=(api_url or "").strip() or None,
                    updated_at=datetime.utcnow(),
                )
            )

    @staticmethod
    def get_by_channel(channel_code: str) -> PublishChannelSettingDTO | None:
        with session_scope() as session:
            row = session.execute(
                select(PublishChannelSetting).where(PublishChannelSetting.channel_code == channel_code)
            ).scalar_one_or_none()
            if not row:
                return None
            return PublishChannelSettingDTO(
                id=row.id,
                channel_code=row.channel_code,
                publish_cycle_minutes=row.publish_cycle_minutes,
                publish_mode=row.publish_mode,
                publish_format=row.publish_format,
                writing_style=row.writing_style,
                api_url=row.api_url,
            )


class PublishChannelRepository:
    @staticmethod
    def list_all() -> list[PublishChannelDTO]:
        with session_scope() as session:
            rows = session.execute(select(PublishChannel).order_by(PublishChannel.display_name.asc())).scalars().all()
            return [
                PublishChannelDTO(id=row.id, code=row.code, display_name=row.display_name, is_enabled=row.is_enabled)
                for row in rows
            ]

    @staticmethod
    def list_enabled() -> list[PublishChannelDTO]:
        with session_scope() as session:
            rows = session.execute(
                select(PublishChannel).where(PublishChannel.is_enabled == True).order_by(PublishChannel.display_name.asc())
            ).scalars().all()
            return [
                PublishChannelDTO(id=row.id, code=row.code, display_name=row.display_name, is_enabled=row.is_enabled)
                for row in rows
            ]

    @staticmethod
    def add(code: str, display_name: str) -> bool:
        c = code.strip()
        d = display_name.strip()
        if not c or not d:
            return False
        with session_scope() as session:
            exists = session.execute(select(PublishChannel).where(PublishChannel.code == c)).scalar_one_or_none()
            if exists:
                return False
            session.add(PublishChannel(code=c, display_name=d, is_enabled=True))
            return True

    @staticmethod
    def toggle(channel_id: int) -> None:
        with session_scope() as session:
            row = session.get(PublishChannel, channel_id)
            if row:
                row.is_enabled = not row.is_enabled


class WritingChannelRepository:
    @staticmethod
    def list_all(enabled_only: bool = False) -> list[WritingChannelDTO]:
        with session_scope() as session:
            stmt = select(WritingChannel)
            if enabled_only:
                stmt = stmt.where(WritingChannel.is_enabled == True)
            rows = session.execute(stmt.order_by(WritingChannel.display_name.asc())).scalars().all()
            return [
                WritingChannelDTO(
                    id=row.id,
                    code=row.code,
                    display_name=row.display_name,
                    channel_type=row.channel_type,
                    connection_type=row.connection_type,
                    status=row.status,
                    is_enabled=row.is_enabled,
                    owner_name=row.owner_name,
                    channel_identifier=row.channel_identifier,
                    default_category=row.default_category,
                    default_visibility=row.default_visibility,
                    tag_policy=row.tag_policy,
                    title_max_length=row.title_max_length,
                    body_min_length=row.body_min_length,
                    body_max_length=row.body_max_length,
                    allowed_markup=row.allowed_markup,
                    require_featured_image=row.require_featured_image,
                    image_max_count=row.image_max_count,
                    image_max_size_kb=row.image_max_size_kb,
                    external_link_policy=row.external_link_policy,
                    affiliate_disclosure_required=row.affiliate_disclosure_required,
                    meta_desc_max_length=row.meta_desc_max_length,
                    slug_rule=row.slug_rule,
                    publish_frequency_limit=row.publish_frequency_limit,
                    reserve_publish_enabled=row.reserve_publish_enabled,
                    api_rate_limit=row.api_rate_limit,
                    api_endpoint_url=row.api_endpoint_url,
                    auth_type=row.auth_type,
                    auth_reference=row.auth_reference,
                    notes=row.notes,
                )
                for row in rows
            ]

    @staticmethod
    def get_by_id(channel_id: int) -> WritingChannel | None:
        with session_scope() as session:
            return session.get(WritingChannel, channel_id)

    @staticmethod
    def add(
        code: str,
        display_name: str,
        channel_type: str,
        connection_type: str,
        status: str,
        is_enabled: bool,
        owner_name: str | None = None,
        channel_identifier: str | None = None,
        default_category: str | None = None,
        default_visibility: str | None = None,
        tag_policy: str | None = None,
        title_max_length: int | None = None,
        body_min_length: int | None = None,
        body_max_length: int | None = None,
        allowed_markup: str | None = None,
        require_featured_image: bool = False,
        image_max_count: int | None = None,
        image_max_size_kb: int | None = None,
        external_link_policy: str | None = None,
        affiliate_disclosure_required: bool = False,
        meta_desc_max_length: int | None = None,
        slug_rule: str | None = None,
        publish_frequency_limit: int | None = None,
        reserve_publish_enabled: bool = True,
        api_rate_limit: int | None = None,
        api_endpoint_url: str | None = None,
        auth_type: str | None = None,
        auth_reference: str | None = None,
        notes: str | None = None,
    ) -> bool:
        c = code.strip()
        d = display_name.strip()
        if not c or not d:
            return False
        with session_scope() as session:
            exists = session.execute(select(WritingChannel).where(WritingChannel.code == c)).scalar_one_or_none()
            if exists:
                return False
            session.add(
                WritingChannel(
                    code=c,
                    display_name=d,
                    channel_type=(channel_type or "blog").strip() or "blog",
                    connection_type=(connection_type or "api").strip() or "api",
                    status=(status or "active").strip() or "active",
                    is_enabled=bool(is_enabled),
                    owner_name=(owner_name or "").strip() or None,
                    channel_identifier=(channel_identifier or "").strip() or None,
                    default_category=(default_category or "").strip() or None,
                    default_visibility=(default_visibility or "").strip() or None,
                    tag_policy=(tag_policy or "").strip() or None,
                    title_max_length=title_max_length,
                    body_min_length=body_min_length,
                    body_max_length=body_max_length,
                    allowed_markup=(allowed_markup or "").strip() or None,
                    require_featured_image=bool(require_featured_image),
                    image_max_count=image_max_count,
                    image_max_size_kb=image_max_size_kb,
                    external_link_policy=(external_link_policy or "").strip() or None,
                    affiliate_disclosure_required=bool(affiliate_disclosure_required),
                    meta_desc_max_length=meta_desc_max_length,
                    slug_rule=(slug_rule or "").strip() or None,
                    publish_frequency_limit=publish_frequency_limit,
                    reserve_publish_enabled=bool(reserve_publish_enabled),
                    api_rate_limit=api_rate_limit,
                    api_endpoint_url=(api_endpoint_url or "").strip() or None,
                    auth_type=(auth_type or "").strip() or None,
                    auth_reference=(auth_reference or "").strip() or None,
                    notes=(notes or "").strip() or None,
                    updated_at=datetime.utcnow(),
                )
            )
            return True

    @staticmethod
    def update(
        channel_id: int,
        code: str,
        display_name: str,
        channel_type: str,
        connection_type: str,
        status: str,
        is_enabled: bool,
        owner_name: str | None = None,
        channel_identifier: str | None = None,
        default_category: str | None = None,
        default_visibility: str | None = None,
        tag_policy: str | None = None,
        title_max_length: int | None = None,
        body_min_length: int | None = None,
        body_max_length: int | None = None,
        allowed_markup: str | None = None,
        require_featured_image: bool = False,
        image_max_count: int | None = None,
        image_max_size_kb: int | None = None,
        external_link_policy: str | None = None,
        affiliate_disclosure_required: bool = False,
        meta_desc_max_length: int | None = None,
        slug_rule: str | None = None,
        publish_frequency_limit: int | None = None,
        reserve_publish_enabled: bool = True,
        api_rate_limit: int | None = None,
        api_endpoint_url: str | None = None,
        auth_type: str | None = None,
        auth_reference: str | None = None,
        notes: str | None = None,
    ) -> bool:
        c = code.strip()
        d = display_name.strip()
        if not c or not d:
            return False
        with session_scope() as session:
            row = session.get(WritingChannel, channel_id)
            if not row:
                return False
            duplicate = session.execute(
                select(WritingChannel).where(
                    WritingChannel.code == c,
                    WritingChannel.id != channel_id,
                )
            ).scalar_one_or_none()
            if duplicate:
                return False
            row.code = c
            row.display_name = d
            row.channel_type = (channel_type or "blog").strip() or "blog"
            row.connection_type = (connection_type or "api").strip() or "api"
            row.status = (status or "active").strip() or "active"
            row.is_enabled = bool(is_enabled)
            row.owner_name = (owner_name or "").strip() or None
            row.channel_identifier = (channel_identifier or "").strip() or None
            row.default_category = (default_category or "").strip() or None
            row.default_visibility = (default_visibility or "").strip() or None
            row.tag_policy = (tag_policy or "").strip() or None
            row.title_max_length = title_max_length
            row.body_min_length = body_min_length
            row.body_max_length = body_max_length
            row.allowed_markup = (allowed_markup or "").strip() or None
            row.require_featured_image = bool(require_featured_image)
            row.image_max_count = image_max_count
            row.image_max_size_kb = image_max_size_kb
            row.external_link_policy = (external_link_policy or "").strip() or None
            row.affiliate_disclosure_required = bool(affiliate_disclosure_required)
            row.meta_desc_max_length = meta_desc_max_length
            row.slug_rule = (slug_rule or "").strip() or None
            row.publish_frequency_limit = publish_frequency_limit
            row.reserve_publish_enabled = bool(reserve_publish_enabled)
            row.api_rate_limit = api_rate_limit
            row.api_endpoint_url = (api_endpoint_url or "").strip() or None
            row.auth_type = (auth_type or "").strip() or None
            row.auth_reference = (auth_reference or "").strip() or None
            row.notes = (notes or "").strip() or None
            row.updated_at = datetime.utcnow()
            return True

    @staticmethod
    def toggle(channel_id: int) -> None:
        with session_scope() as session:
            row = session.get(WritingChannel, channel_id)
            if row:
                row.is_enabled = not row.is_enabled
                row.updated_at = datetime.utcnow()

    @staticmethod
    def delete(channel_id: int) -> None:
        with session_scope() as session:
            row = session.get(WritingChannel, channel_id)
            if row:
                session.delete(row)



















class AppSettingRepository:
    RELATED_KEYWORD_LIMIT_KEY = "related_keyword_limit"

    @staticmethod
    def get_value(setting_key: str, default: str | None = None) -> str | None:
        with session_scope() as session:
            row = session.execute(select(AppSetting).where(AppSetting.setting_key == setting_key)).scalar_one_or_none()
            return row.setting_value if row else default

    @staticmethod
    def set_value(setting_key: str, setting_value: str) -> None:
        with session_scope() as session:
            row = session.execute(select(AppSetting).where(AppSetting.setting_key == setting_key)).scalar_one_or_none()
            if row:
                row.setting_value = setting_value
                row.updated_at = datetime.utcnow()
                return
            session.add(
                AppSetting(
                    setting_key=setting_key,
                    setting_value=setting_value,
                    updated_at=datetime.utcnow(),
                )
            )

    @staticmethod
    def get_related_keyword_limit(default: int = 10) -> int:
        raw = AppSettingRepository.get_value(AppSettingRepository.RELATED_KEYWORD_LIMIT_KEY)
        if raw is None:
            return max(5, min(10, default))
        try:
            value = int(raw)
        except ValueError:
            return max(5, min(10, default))
        return max(5, min(10, value))

    @staticmethod
    def set_related_keyword_limit(value: int) -> None:
        safe_value = max(5, min(10, int(value)))
        AppSettingRepository.set_value(AppSettingRepository.RELATED_KEYWORD_LIMIT_KEY, str(safe_value))













