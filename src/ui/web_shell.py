from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import socket
import time
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import parse_qs, urlparse
from urllib import error as urlerror
from urllib import request as urlrequest

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from collector.service import crawl_service
from collector.scheduler import collect_scheduler
from core.settings import settings
from labeling import labeling_service
from labeling.scheduler import labeling_auto_scheduler
from publisher import publisher_service
from core.settings_keys import (
    CollectSettingKeys,
    LabelSettingKeys,
    PublishSettingKeys,
    WriterSettingKeys,
)
from writer import writer_service
from writer.scheduler import writer_auto_scheduler
from core.menu import get_v2_default_entry, get_v2_menu_tree
from storage.database import session_scope
from storage.models import (
    AIProvider,
    ArticleTemplate,
    Category,
    ContentLabel,
    CrawlJob,
    GeneratedArticle,
    ImageLabel,
    Keyword,
    Persona,
    PublishChannel,
    PublishJob,
    RawContent,
    RawImage,
    SourceChannel,
    WritingChannel,
)
from storage.repositories import (
    AppSettingRepository,
    CategoryRepository,
    CrawlRepository,
    KeywordRepository,
    LabelRepository,
    SourceChannelRepository,
    PersonaRepository,
    ArticleTemplateRepository,
    AIProviderRepository,
    ArticleRepository,
    PublishRepository,
    PublishChannelRepository,
    PublishChannelSettingRepository,
    WritingChannelRepository,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:  # pragma: no cover
    QWebEngineView = None



class _CollectRunControl:
    def __init__(self) -> None:
        self._lock = Lock()
        self._running = False
        self._stop_requested = False

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return False
            self._running = True
            self._stop_requested = False
            return True

    def finish(self) -> None:
        with self._lock:
            self._running = False
            self._stop_requested = False

    def request_stop(self) -> bool:
        with self._lock:
            if not self._running:
                return False
            self._stop_requested = True
            return True

    def should_stop(self) -> bool:
        with self._lock:
            return self._stop_requested

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "stop_requested": self._stop_requested,
            }


collect_run_control = _CollectRunControl()


class _WriterRunControl:
    def __init__(self) -> None:
        self._lock = Lock()
        self._running = False
        self._stop_requested = False

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return False
            self._running = True
            self._stop_requested = False
            return True

    def finish(self) -> None:
        with self._lock:
            self._running = False
            self._stop_requested = False

    def request_stop(self) -> bool:
        with self._lock:
            if not self._running:
                return False
            self._stop_requested = True
            return True

    def should_stop(self) -> bool:
        with self._lock:
            return self._stop_requested

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "stop_requested": self._stop_requested,
            }


writer_run_control = _WriterRunControl()


class _PublishAutoRunner:
    def __init__(self) -> None:
        self._lock = Lock()
        self._tick_lock = Lock()
        self._enabled = False
        self._worker_started = False
        self._thread: Thread | None = None
        self._last_run_by_channel: dict[str, datetime] = {}
        self._pause_until: datetime | None = None
        self._logs: list[str] = []
        self._last_tick_at: datetime | None = None
        self._last_tick_processed = 0

    def start_worker(self) -> None:
        started = False
        with self._lock:
            if self._worker_started:
                return
            self._thread = Thread(target=self._loop, daemon=True)
            self._thread.start()
            self._worker_started = True
            started = True
        if started:
            self._append_log("자동 발행 워커 시작")

    def _loop(self) -> None:
        while True:
            try:
                self.tick_once()
            except Exception as exc:
                self._append_log(f"워커 오류: {exc}")
            time.sleep(5)

    def set_enabled(self, enabled: bool) -> None:
        changed = False
        with self._lock:
            next_enabled = bool(enabled)
            changed = (self._enabled != next_enabled)
            self._enabled = next_enabled
        if changed:
            self._append_log("자동 발행 시작" if enabled else "자동 발행 중지")

    def set_pause_until(self, pause_until: datetime | None) -> None:
        with self._lock:
            self._pause_until = pause_until
        if pause_until:
            self._append_log(f"자동 발행 일시중지 예약: {pause_until.isoformat(sep=' ', timespec='minutes')}")
        else:
            self._append_log("자동 발행 일시중지 해제")

    def status(self) -> dict:
        with self._lock:
            logs = list(self._logs[:80])
            enabled = self._enabled
            started = self._worker_started
            last_tick_at = _dt_to_iso(self._last_tick_at)
            last_tick_processed = self._last_tick_processed
            pause_until = _dt_to_iso(self._pause_until)
            run_by_channel = dict(self._last_run_by_channel)
        channels = PublishChannelRepository.list_enabled()
        PublishChannelSettingRepository.ensure_for_channels([row.code for row in channels])
        auto_channels = 0
        channel_rows: list[dict] = []
        now = datetime.utcnow()
        for channel in channels:
            setting = PublishChannelSettingRepository.get_by_channel(channel.code)
            if not setting or str(setting.publish_mode) != "auto":
                continue
            auto_channels += 1
            cycle = max(5, int(setting.publish_cycle_minutes or 60))
            last = run_by_channel.get(channel.code)
            if last:
                next_run = last + timedelta(minutes=cycle)
            else:
                next_run = now
            channel_rows.append({
                "channel_code": channel.code,
                "cycle_minutes": cycle,
                "next_run_at": _dt_to_iso(next_run),
            })
        return {
            "enabled": enabled,
            "worker_started": started,
            "auto_channel_count": auto_channels,
            "pause_until": pause_until,
            "last_tick_at": last_tick_at,
            "last_tick_processed": last_tick_processed,
            "channels": channel_rows,
            "logs": logs,
        }

    def tick_once(self, force: bool = False) -> dict:
        if not self._tick_lock.acquire(blocking=False):
            return {"ok": True, "processed": 0, "message": "이미 자동 발행 실행 중"}
        try:
            with self._lock:
                enabled = self._enabled
                pause_until = self._pause_until
            if not enabled and not force:
                return {"ok": True, "processed": 0, "message": "자동 발행 중지 상태"}
            if pause_until and datetime.utcnow() < pause_until and not force:
                return {"ok": True, "processed": 0, "message": "일시중지 기간"}

            self._sync_publish_channels_from_writing_channels()
            channels = PublishChannelRepository.list_enabled()
            if not channels:
                return {"ok": True, "processed": 0, "message": "활성 발행 채널 없음"}
            PublishChannelSettingRepository.ensure_for_channels([row.code for row in channels])

            processed = 0
            for channel in channels:
                setting = PublishChannelSettingRepository.get_by_channel(channel.code)
                if not setting or str(setting.publish_mode) != "auto":
                    continue
                now = datetime.utcnow()
                last = self._last_run_by_channel.get(channel.code)
                cycle = max(5, int(setting.publish_cycle_minutes or 60))
                if not force and last and (now - last).total_seconds() < cycle * 60:
                    remain = int(cycle * 60 - (now - last).total_seconds())
                    self._append_log(f"[{channel.code}] 대기중: 주기 미도달 ({remain}s 남음)")
                    continue

                article_id = self._pick_next_ready_article_for_channel(channel.code)
                if not article_id:
                    self._last_run_by_channel[channel.code] = now
                    self._append_log(f"[{channel.code}] 발행 대상 없음 (ready 상태 글 없음 또는 이미 처리됨)")
                    continue
                try:
                    self._append_log(f"[{channel.code}] 대상 선정 article_id={article_id} (가장 오래된 ready 우선)")
                    job_id = publisher_service.enqueue_publish(article_id=article_id, target_channel=channel.code, mode="auto")
                    result = publisher_service.process_job(job_id)
                    processed += 1
                    self._append_log(f"[{channel.code}] 자동 발행 완료 article_id={article_id}, job_id={job_id}, result={result}")
                except Exception as exc:
                    self._append_log(f"[{channel.code}] 자동 발행 실패 article_id={article_id}, error={exc}")
                finally:
                    self._last_run_by_channel[channel.code] = now

            with self._lock:
                self._last_tick_at = datetime.utcnow()
                self._last_tick_processed = processed
            return {"ok": True, "processed": processed}
        finally:
            self._tick_lock.release()

    def _pick_next_ready_article_for_channel(self, channel_code: str) -> int | None:
        with session_scope() as session:
            articles = session.execute(
                select(GeneratedArticle)
                .where(GeneratedArticle.status == "ready")
                .order_by(GeneratedArticle.created_at.asc())
                .limit(80)
            ).scalars().all()
            for article in articles:
                exists = session.execute(
                    select(PublishJob.id).where(
                        PublishJob.article_id == article.id,
                        PublishJob.target_channel == channel_code,
                        PublishJob.status.in_(["queued", "processing", "done"]),
                    )
                ).first()
                if exists:
                    continue
                return int(article.id)
        return None

    def _sync_publish_channels_from_writing_channels(self) -> None:
        writing_channels = WritingChannelRepository.list_all()
        existing = {row.code: row for row in PublishChannelRepository.list_all()}
        for channel in writing_channels:
            code = str(channel.code or "").strip()
            name = str(channel.display_name or code).strip() or code
            if not code or code in existing:
                continue
            PublishChannelRepository.add(code=code, display_name=name)

    def sync_channels(self) -> None:
        self._sync_publish_channels_from_writing_channels()

    def _append_log(self, message: str) -> None:
        stamp = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        line = f"[{stamp}] {message}"
        with self._lock:
            self._logs.insert(0, line)
            self._logs = self._logs[:80]


publish_auto_runner = _PublishAutoRunner()

class _WebShellServer:
    def __init__(self) -> None:
        self.runtime_dir = settings.data_dir / "web_shell_runtime"
        self.assets_dir = self.runtime_dir / "assets" / "web-shell"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self._copy_assets()

        self.port = self._find_free_port()
        handler_cls = partial(_WebShellRequestHandler, directory=str(self.runtime_dir))
        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), handler_cls)
        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self) -> None:
        if not self.thread.is_alive():
            self.thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return int(s.getsockname()[1])

    def _copy_assets(self) -> None:
        source_dir = settings.project_root / "src" / "ui" / "assets" / "web-shell"
        if source_dir.exists():
            for src in source_dir.rglob("*"):
                if not src.is_file():
                    continue
                rel = src.relative_to(source_dir)
                dst = self.assets_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        mublo_source = settings.project_root / "src" / "ui" / "assets" / "mublo-editor"
        mublo_target = self.runtime_dir / "assets" / "mublo-editor"
        mublo_target.mkdir(parents=True, exist_ok=True)
        for name in ["MubloEditor.js", "MubloEditor.css"]:
            src = mublo_source / name
            dst = mublo_target / name
            if src.exists():
                shutil.copy2(src, dst)


class _WebShellRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _ensure_request_id(self) -> str:
        req_id = getattr(self, "_request_id", "")
        if not req_id:
            req_id = uuid.uuid4().hex[:12]
            self._request_id = req_id
        return req_id

    def _write_validation_error(self, fields: dict[str, str], message: str = "입력값을 확인하세요.") -> None:
        return self._write_json(
            {
                "error": message,
                "error_code": "VALIDATION_ERROR",
                "fields": fields,
            },
            400,
        )

    def _serve_static_safe(self) -> None:
        try:
            return super().do_GET()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return None
    def _serve_runtime_asset(self, route: str) -> None:
        runtime_root = (settings.data_dir / "web_shell_runtime").resolve()
        rel_path = route.lstrip("/")
        target = (runtime_root / rel_path).resolve()
        try:
            target.relative_to(runtime_root)
        except Exception:
            return self._write_json({"error": "forbidden path"}, 403)
        if not target.exists() or not target.is_file():
            return self._write_json({"error": "File not found"}, 404)
        content_type, _ = mimetypes.guess_type(target.name)
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return None

    def do_GET(self) -> None:  # noqa: N802
        self._ensure_request_id()
        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)

        if route == "/" or route == "/index.html":
            return self._serve_runtime_asset("/assets/web-shell/index.html")

        if route == "/api/categories":
            return self._serve_categories()
        if route == "/api/keywords":
            return self._serve_keywords()
        if route == "/api/settings/related-keyword-limit":
            return self._serve_related_keyword_limit()

        if route == "/api/related":
            source_keyword_id = _to_int((query.get("source_keyword_id") or [None])[0])
            if not source_keyword_id:
                return self._write_json({"error": "source_keyword_id is required"}, 400)
            return self._serve_related_keywords(source_keyword_id)

        if route == "/api/related-blocks":
            source_keyword_id = _to_int((query.get("source_keyword_id") or [None])[0])
            if not source_keyword_id:
                return self._write_json({"error": "source_keyword_id is required"}, 400)
            return self._serve_related_blocks(source_keyword_id)

        if route == "/api/source-channels":
            return self._serve_source_channels()
        if route == "/api/collect/keywords":
            return self._serve_active_keywords()
        if route == "/api/collect/jobs":
            return self._serve_collect_jobs()
        if route == "/api/collect/status":
            return self._write_json(collect_run_control.status())
        if route == "/api/automation/status":
            return self._serve_automation_status()
        if route == "/api/collect/contents":
            return self._serve_collect_contents()

        if route == "/api/collected/contents":
            page = max(1, _to_int((query.get("page") or ["1"])[0]) or 1)
            page_size = max(5, min(100, _to_int((query.get("page_size") or ["15"])[0]) or 15))
            return self._serve_collected_contents(page=page, page_size=page_size)
        if route == "/api/collected/images":
            page = max(1, _to_int((query.get("page") or ["1"])[0]) or 1)
            page_size = max(6, min(120, _to_int((query.get("page_size") or ["24"])[0]) or 24))
            return self._serve_collected_images(page=page, page_size=page_size)
        if route.startswith("/api/collected/images/") and route.endswith("/file"):
            parts = route.strip("/").split("/")
            if len(parts) == 5 and parts[3].isdigit():
                return self._serve_collected_image_file(int(parts[3]))
            return self._write_json({"error": "invalid image route"}, 400)

        if route == "/api/labels/content":
            content_id = _to_int((query.get("content_id") or [None])[0])
            if not content_id:
                return self._write_json({"error": "content_id is required"}, 400)
            return self._serve_content_label(content_id)

        if route == "/api/labels/image":
            image_id = _to_int((query.get("image_id") or [None])[0])
            if not image_id:
                return self._write_json({"error": "image_id is required"}, 400)
            return self._serve_image_label(image_id)

        if route == "/api/dashboard/summary":
            return self._serve_dashboard_summary()
        if route == "/api/labeling/stats":
            return self._write_json(LabelRepository.get_label_stats())
        if route == "/api/labeling/auto/status":
            return self._write_json(labeling_auto_scheduler.status())
        if route == "/api/labeling/status-counts":
            return self._write_json(LabelRepository.get_label_status_counts())
        if route == "/api/labeling/runs":
            limit = max(10, min(200, _to_int((query.get("limit") or ["50"])[0]) or 50))
            return self._serve_labeling_run_logs(limit=limit)
        if route == "/api/labeling/automation-snapshot":
            return self._serve_labeling_automation_snapshot()
        if route == "/api/personas":
            return self._serve_personas()
        if route == "/api/templates":
            template_type = (query.get("template_type") or [None])[0]
            active_only = ((query.get("active_only") or ["0"])[0] == "1")
            return self._serve_templates(template_type=template_type, active_only=active_only)
        if route == "/api/ai-providers":
            return self._serve_ai_providers()
        if route == "/api/ai-providers/env-status":
            return self._serve_ai_provider_env_status()

        if route == "/api/writer/personas":
            return self._serve_writer_personas()
        if route == "/api/writer/templates":
            template_type = (query.get("template_type") or [None])[0]
            return self._serve_writer_templates(template_type)
        if route == "/api/writer-channels":
            return self._serve_writer_channels()
        if route == "/api/writer/run-summary":
            return self._serve_writer_run_summary()
        if route == "/api/writer/result-board":
            return self._serve_writer_result_board()
        if route == "/api/writer/status":
            return self._write_json(writer_run_control.status())
        if route == "/api/writer/auto/status":
            return self._write_json(writer_auto_scheduler.status())
        if route == "/api/writer/articles":
            return self._serve_writer_articles()
        if route.startswith("/api/writer/articles/"):
            parts = route.strip("/").split("/")
            if len(parts) == 4 and parts[3].isdigit():
                return self._serve_writer_article(int(parts[3]))

        if route == "/api/publish-channels":
            return self._serve_publish_channels()
        if route == "/api/publish-channel-settings":
            return self._serve_publish_channel_settings()
        if route.startswith("/api/publish-channel-settings/"):
            parts = route.strip("/").split("/")
            if len(parts) == 3:
                return self._serve_publish_channel_setting(parts[2])
        if route == "/api/publish/auto/status":
            return self._serve_publish_auto_status()

        if route == "/api/publisher/channels":
            return self._serve_publisher_channels()
        if route == "/api/publisher/articles":
            return self._serve_publisher_articles()
        if route == "/api/publisher/jobs":
            return self._serve_publisher_jobs()

        if route == "/api/settings/app":
            return self._serve_settings_app()
        if route == "/api/settings/runtime":
            return self._serve_settings_runtime()
        if route == "/api/v2/menu":
            return self._serve_v2_menu()
        if route == "/api/v2/settings/collect":
            return self._serve_v2_collect_settings()
        if route == "/api/v2/settings/label":
            return self._serve_v2_label_settings()
        if route == "/api/v2/settings/writer":
            return self._serve_v2_writer_settings()
        if route == "/api/v2/settings/publish":
            return self._serve_v2_publish_settings()
        if route == "/api/v2/monitor/events":
            limit = _to_int((query.get("limit") or [None])[0]) or 300
            limit = max(20, min(1000, limit))
            cursor = str((query.get("cursor") or [""])[0] or "").strip()
            stage = str((query.get("stage") or [""])[0] or "").strip().lower()
            return self._serve_v2_monitor_events(limit, cursor, stage)

        if route.startswith("/assets/"):
            return self._serve_runtime_asset(route)

        return self._serve_static_safe()

    def do_POST(self) -> None:  # noqa: N802
        self._ensure_request_id()
        route = urlparse(self.path).path

        if route == "/api/categories":
            return self._create_category()
        if route.startswith("/api/categories/") and route.endswith("/update"):
            parts = route.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit():
                return self._update_category(int(parts[2]))
        if route == "/api/keywords":
            return self._create_keyword()
        if route == "/api/keywords/bulk":
            return self._create_keywords_bulk()
        if route == "/api/keywords/toggle-batch":
            return self._toggle_keywords_batch()

        if route.startswith("/api/keywords/") and route.endswith("/toggle"):
            parts = route.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit():
                return self._toggle_keyword(int(parts[2]))

        if route == "/api/related/block":
            return self._block_related_keyword()

        if route.startswith("/api/source-channels/") and route.endswith("/toggle"):
            parts = route.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit():
                SourceChannelRepository.toggle(int(parts[2]))
                return self._write_json({"ok": True})

        if route == "/api/collect/stop":
            stopped = collect_run_control.request_stop()
            return self._write_json({"ok": stopped, "requested": stopped, **collect_run_control.status()})

        if route == "/api/collect/run":
            data = self._read_json_body()
            if data is None:
                return self._write_json({"error": "Invalid JSON body"}, 400)

            if not collect_run_control.start():
                return self._write_json({"error": "이미 수집 실행 중입니다.", **collect_run_control.status()}, 409)
            try:
                keyword_id = _to_int(data.get("keyword_id"))
                configured_max = _to_int(AppSettingRepository.get_value(CollectSettingKeys.MAX_RESULTS, "3")) or 3
                max_results = _to_int(data.get("max_results")) or configured_max
                max_results = max(1, min(20, max_results))
    
                scope = str(AppSettingRepository.get_value(CollectSettingKeys.KEYWORD_SCOPE, "selected") or "selected").strip().lower()
                if scope not in {"all", "selected", "related"}:
                    scope = "selected"
                sync_related = _to_bool(AppSettingRepository.get_value(CollectSettingKeys.NAVER_RELATED_SYNC, "1"))
    
                all_keywords = [k for k in KeywordRepository.list_all() if k.is_active and not k.is_auto_generated]
                all_active_keywords = {k.id: k for k in KeywordRepository.list_all() if k.is_active}
    
                selected_channel_codes = _safe_json_list(AppSettingRepository.get_value(CollectSettingKeys.SELECTED_CHANNEL_CODES, "[]"))
                selected_category_ids = [
                    n for n in (_to_int(v) for v in _safe_json_list(AppSettingRepository.get_value(CollectSettingKeys.SELECTED_CATEGORY_IDS, "[]")))
                    if n is not None
                ]
                selected_category_set = set(selected_category_ids)
    
                target_ids: list[int] = []
                if scope == "all":
                    target_ids = [k.id for k in all_keywords]
                elif scope == "related":
                    base_ids: list[int] = []
                    if selected_category_set:
                        base_ids = [k.id for k in all_keywords if (k.category_id or 0) in selected_category_set]
                    elif keyword_id:
                        base_ids = [keyword_id]
                    if not base_ids:
                        return self._write_json({"error": "키워드 확장 실행에는 기준 키워드 또는 체크된 카테고리가 필요합니다."}, 400)
    
                    ordered: list[int] = []
                    seen: set[int] = set()
                    for base_id in base_ids:
                        if base_id not in seen and base_id in all_active_keywords:
                            seen.add(base_id)
                            ordered.append(base_id)
                        for rel in KeywordRepository.list_related_keywords(base_id):
                            rid = int(rel.related_keyword_id)
                            if rid in all_active_keywords and rid not in seen:
                                seen.add(rid)
                                ordered.append(rid)
                    target_ids = ordered
                else:
                    if selected_category_set:
                        target_ids = [k.id for k in all_keywords if (k.category_id or 0) in selected_category_set]
                    elif keyword_id:
                        target_ids = [keyword_id]
                    else:
                        return self._write_json({"error": "체크된 내역 수집에는 체크 카테고리 또는 keyword_id가 필요합니다."}, 400)
    
                if not target_ids:
                    return self._write_json({"error": "실행 대상 키워드가 없습니다."}, 400)
    
                messages: list[str] = []
                total = len(target_ids)
                messages.append(f"실행 모드: {scope} | 대상 키워드: {total}건")
                for idx, target_id in enumerate(target_ids, 1):
                    if collect_run_control.should_stop():
                        messages.append(f"[{idx}/{total}] 중단 요청으로 실행을 종료합니다.")
                        break
                    target_row = all_active_keywords.get(target_id)
                    target_name = target_row.keyword if target_row else f"ID:{target_id}"
                    messages.append(f"[{idx}/{total}] 키워드 실행 시작: {target_name} (ID:{target_id})")
                    messages.extend(
                        crawl_service.run_for_keyword(
                            keyword_id=target_id,
                            max_results=max_results,
                            sync_related=sync_related,
                            allowed_channels=(selected_channel_codes or None) if scope != "all" else None,
                        )
                    )
    
                stopped = collect_run_control.should_stop()
                return self._write_json({"ok": not stopped, "stopped": stopped, "messages": messages, "targets": total})
            finally:
                collect_run_control.finish()

        if route == "/api/labels/content":
            return self._save_content_label()
        if route == "/api/labels/image":
            return self._save_image_label()

        if route == "/api/labeling/run-content":
            batch_size = _to_int(AppSettingRepository.get_value(LabelSettingKeys.BATCH_SIZE, "300")) or 300
            batch_size = max(10, min(1000, batch_size))
            result = labeling_service.label_unlabeled_contents(limit=batch_size)
            return self._write_json({"ok": True, **result})
        if route == "/api/labeling/run-image":
            batch_size = _to_int(AppSettingRepository.get_value(LabelSettingKeys.BATCH_SIZE, "300")) or 300
            batch_size = max(10, min(1000, batch_size))
            result = labeling_service.label_unlabeled_images(limit=batch_size)
            return self._write_json({"ok": True, **result})
        if route == "/api/labeling/auto/tick":
            result = labeling_auto_scheduler.run_once()
            return self._write_json({"ok": True, **result})

        if route == "/api/personas":
            return self._create_persona()
        if route.startswith("/api/personas/") and route.endswith("/update"):
            parts = route.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit():
                return self._update_persona(int(parts[2]))

        if route == "/api/templates":
            return self._create_template()
        if route.startswith("/api/templates/") and route.endswith("/update"):
            parts = route.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit():
                return self._update_template(int(parts[2]))

        if route == "/api/ai-providers":
            return self._create_ai_provider()
        if route.startswith("/api/ai-providers/") and route.endswith("/health-check"):
            parts = route.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit():
                return self._health_check_ai_provider(int(parts[2]))
        if route.startswith("/api/ai-providers/") and route.endswith("/update"):
            parts = route.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit():
                return self._update_ai_provider(int(parts[2]))

        if route == "/api/writer/generate":
            return self._writer_generate()
        if route == "/api/writer/run":
            return self._writer_run()
        if route == "/api/writer/result-board/publish":
            return self._writer_result_board_publish()
        if route == "/api/writer/articles/batch-status":
            return self._writer_batch_update_status()
        if route == "/api/writer/stop":
            stopped = writer_run_control.request_stop()
            return self._write_json({"ok": stopped, "requested": stopped, **writer_run_control.status()})
        if route.startswith("/api/writer/articles/") and route.endswith("/save"):
            parts = route.strip("/").split("/")
            if len(parts) == 5 and parts[3].isdigit():
                return self._writer_save_article(int(parts[3]))
        if route == "/api/writer-channels":
            return self._create_writer_channel()
        if route.startswith("/api/writer-channels/") and route.endswith("/update"):
            parts = route.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit():
                return self._update_writer_channel(int(parts[2]))
        if route.startswith("/api/writer-channels/") and route.endswith("/toggle"):
            parts = route.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit():
                WritingChannelRepository.toggle(int(parts[2]))
                return self._write_json({"ok": True})

        if route == "/api/publish-channels":
            return self._create_publish_channel()
        if route.startswith("/api/publish-channels/") and route.endswith("/toggle"):
            parts = route.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit():
                PublishChannelRepository.toggle(int(parts[2]))
                return self._write_json({"ok": True})

        if route == "/api/publish-channel-settings/save":
            return self._save_publish_channel_setting()
        if route == "/api/publish-channel-settings/test-url":
            return self._test_publish_channel_api_url()

        if route == "/api/publisher/enqueue":
            return self._publisher_enqueue()
        if route.startswith("/api/publisher/jobs/") and route.endswith("/process"):
            parts = route.strip("/").split("/")
            if len(parts) == 5 and parts[3].isdigit():
                return self._publisher_process_job(int(parts[3]))
        if route == "/api/publish/auto/start":
            publish_auto_runner.start_worker()
            publish_auto_runner.set_enabled(True)
            return self._write_json({"ok": True, **publish_auto_runner.status()})
        if route == "/api/publish/auto/stop":
            publish_auto_runner.set_enabled(False)
            return self._write_json({"ok": True, **publish_auto_runner.status()})
        if route == "/api/publish/auto/tick":
            result = publish_auto_runner.tick_once(force=True)
            return self._write_json({"ok": True, **result, **publish_auto_runner.status()})
        if route == "/api/publish/auto/pause-until":
            return self._save_publish_auto_pause_until()

        if route == "/api/settings/runtime":
            return self._save_settings_runtime()
        if route == "/api/v2/settings/collect":
            return self._save_v2_collect_settings()
        if route == "/api/v2/settings/label":
            return self._save_v2_label_settings()
        if route == "/api/v2/settings/writer":
            return self._save_v2_writer_settings()
        if route == "/api/v2/settings/publish":
            return self._save_v2_publish_settings()

        return self._write_json({"error": "Not found"}, 404)

    def do_DELETE(self) -> None:  # noqa: N802
        self._ensure_request_id()
        route = urlparse(self.path).path

        if route.startswith("/api/categories/"):
            parts = route.strip("/").split("/")
            if len(parts) == 3 and parts[2].isdigit():
                CategoryRepository.delete(int(parts[2]))
                return self._write_json({"ok": True})

        if route.startswith("/api/keywords/"):
            parts = route.strip("/").split("/")
            if len(parts) == 3 and parts[2].isdigit():
                KeywordRepository.delete(int(parts[2]))
                return self._write_json({"ok": True})

        if route.startswith("/api/related-blocks/"):
            parts = route.strip("/").split("/")
            if len(parts) == 3 and parts[2].isdigit():
                KeywordRepository.unblock_related_block(int(parts[2]))
                return self._write_json({"ok": True})

        if route.startswith("/api/personas/"):
            parts = route.strip("/").split("/")
            if len(parts) == 3 and parts[2].isdigit():
                PersonaRepository.delete(int(parts[2]))
                return self._write_json({"ok": True})

        if route.startswith("/api/templates/"):
            parts = route.strip("/").split("/")
            if len(parts) == 3 and parts[2].isdigit():
                ArticleTemplateRepository.delete(int(parts[2]))
                return self._write_json({"ok": True})

        if route.startswith("/api/ai-providers/"):
            parts = route.strip("/").split("/")
            if len(parts) == 3 and parts[2].isdigit():
                AIProviderRepository.delete(int(parts[2]))
                return self._write_json({"ok": True})
        if route.startswith("/api/writer-channels/"):
            parts = route.strip("/").split("/")
            if len(parts) == 3 and parts[2].isdigit():
                WritingChannelRepository.delete(int(parts[2]))
                return self._write_json({"ok": True})

        return self._write_json({"error": "Not found"}, 404)

    def _serve_categories(self) -> None:
        rows = CategoryRepository.list_all()
        return self._write_json([{"id": row.id, "name": row.name} for row in rows])

    def _serve_keywords(self) -> None:
        rows = [row for row in KeywordRepository.list_all() if not row.is_auto_generated]
        payload = []
        for row in rows:
            payload.append(
                {
                    "id": row.id,
                    "keyword": row.keyword,
                    "category_id": row.category_id,
                    "category_name": row.category_name,
                    "is_active": row.is_active,
                    "total_collected_count": row.total_collected_count,
                    "last_collected_at": _dt_to_iso(row.last_collected_at),
                    "total_published_count": row.total_published_count,
                    "last_published_at": _dt_to_iso(row.last_published_at),
                }
            )
        return self._write_json(payload)

    def _serve_related_keyword_limit(self) -> None:
        return self._write_json({"limit": AppSettingRepository.get_related_keyword_limit(10)})

    def _serve_related_keywords(self, source_keyword_id: int) -> None:
        rows = KeywordRepository.list_related_keywords(source_keyword_id)
        payload = [
            {
                "relation_id": row.relation_id,
                "source_keyword_id": row.source_keyword_id,
                "related_keyword_id": row.related_keyword_id,
                "related_keyword": row.related_keyword,
                "collect_count": row.collect_count,
                "last_seen_at": _dt_to_iso(row.last_seen_at),
            }
            for row in rows
        ]
        return self._write_json(payload)

    def _serve_related_blocks(self, source_keyword_id: int) -> None:
        rows = KeywordRepository.list_related_blocks(source_keyword_id)
        payload = [
            {
                "block_id": row.block_id,
                "source_keyword_id": row.source_keyword_id,
                "related_keyword": row.related_keyword,
                "created_at": _dt_to_iso(row.created_at),
            }
            for row in rows
        ]
        return self._write_json(payload)

    def _serve_source_channels(self) -> None:
        rows = SourceChannelRepository.list_all()
        return self._write_json(
            [
                {
                    "id": row.id,
                    "code": row.code,
                    "display_name": row.display_name,
                    "is_enabled": row.is_enabled,
                }
                for row in rows
            ]
        )

    def _serve_active_keywords(self) -> None:
        rows = [row for row in KeywordRepository.list_active() if not row.is_auto_generated]
        return self._write_json(
            [
                {
                    "id": row.id,
                    "keyword": row.keyword,
                    "category_id": row.category_id,
                    "category_name": row.category_name,
                }
                for row in rows
            ]
        )

    def _serve_collect_jobs(self) -> None:
        rows = CrawlRepository.list_recent_jobs(100)
        return self._write_json(
            [
                {
                    "id": row.id,
                    "keyword": row.keyword,
                    "channel_code": row.channel_code,
                    "status": row.status,
                    "collected_count": row.collected_count,
                    "created_at": _dt_to_iso(row.created_at),
                }
                for row in rows
            ]
        )

    def _serve_automation_status(self) -> None:
        collect_status = collect_scheduler.status()
        labeling_status = labeling_auto_scheduler.status()
        publish_status = publish_auto_runner.status()
        writer_auto = writer_auto_scheduler.status()
        manual_writer = writer_run_control.status()
        writer_auto["manual_running"] = bool(manual_writer.get("running"))
        writer_auto["manual_stop_requested"] = bool(manual_writer.get("stop_requested"))
        return self._write_json(
            {
                "collect": collect_status,
                "labeling": labeling_status,
                "writer": writer_auto,
                "publish": publish_status,
            }
        )

    def _serve_collect_contents(self) -> None:
        rows = CrawlRepository.list_recent_contents(100)
        return self._write_json(
            [
                {
                    "id": row.id,
                    "keyword": row.keyword,
                    "channel_code": row.channel_code,
                    "title": row.title,
                    "created_at": _dt_to_iso(row.created_at),
                }
                for row in rows
            ]
        )
    def _serve_collected_contents(self, page: int = 1, page_size: int = 15) -> None:
        with session_scope() as session:
            total = int(session.query(func.count(RawContent.id)).scalar() or 0)
            total_pages = max(1, (total + page_size - 1) // page_size)
            page = min(max(1, page), total_pages)
            rows = (
                session.query(RawContent)
                .order_by(RawContent.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            payload = [
                {
                    "id": row.id,
                    "keyword": row.keyword.keyword if row.keyword else "-",
                    "channel": row.channel_code,
                    "title": row.title,
                    "source_url": row.source_url,
                    "body_text": row.body_text,
                    "label_status": row.label_status or "pending",
                    "label_attempt_count": int(row.label_attempt_count or 0),
                    "label_confidence": int(row.label_confidence or 0) if row.label_confidence is not None else None,
                    "created_at": _dt_to_iso(row.created_at),
                }
                for row in rows
            ]
        return self._write_json({"items": payload, "total": total, "page": page, "page_size": page_size, "total_pages": total_pages})

    def _serve_collected_images(self, page: int = 1, page_size: int = 24) -> None:
        with session_scope() as session:
            total = int(session.query(func.count(RawImage.id)).scalar() or 0)
            total_pages = max(1, (total + page_size - 1) // page_size)
            page = min(max(1, page), total_pages)
            rows = (
                session.query(RawImage)
                .order_by(RawImage.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            payload = [
                {
                    "id": row.id,
                    "content_id": row.content_id,
                    "image_url": row.image_url,
                    "local_path": row.local_path or "",
                    "local_url": f"/api/collected/images/{row.id}/file" if row.local_path else "",
                    "label_status": row.label_status or "pending",
                    "label_attempt_count": int(row.label_attempt_count or 0),
                    "label_confidence": int(row.label_confidence or 0) if row.label_confidence is not None else None,
                }
                for row in rows
            ]
        return self._write_json({"items": payload, "total": total, "page": page, "page_size": page_size, "total_pages": total_pages})
    def _serve_collected_image_file(self, image_id: int) -> None:
        with session_scope() as session:
            row = session.query(RawImage).filter(RawImage.id == image_id).first()
            if not row or not row.local_path:
                return self._write_json({"error": "image file not found"}, 404)

        file_path = Path(row.local_path).expanduser()
        if not file_path.is_absolute():
            file_path = (settings.project_root / file_path).resolve()
        else:
            file_path = file_path.resolve()

        try:
            allowed_root = (settings.data_dir / "collected_images").resolve()
            file_path.relative_to(allowed_root)
        except Exception:
            return self._write_json({"error": "forbidden image path"}, 403)

        if not file_path.exists() or not file_path.is_file():
            return self._write_json({"error": "image file not found"}, 404)

        content_type, _ = mimetypes.guess_type(file_path.name)
        try:
            data = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return None

    def _serve_content_label(self, content_id: int) -> None:
        with session_scope() as session:
            row = session.query(ContentLabel).filter(ContentLabel.content_id == content_id).first()
            if not row:
                return self._write_json({"tone": "", "sentiment": "", "topics": [], "quality_score": 3})
            topics = _safe_json_list(row.topics)
            return self._write_json(
                {
                    "tone": row.tone or "",
                    "sentiment": row.sentiment or "",
                    "topics": topics,
                    "quality_score": row.quality_score,
                }
            )

    def _serve_image_label(self, image_id: int) -> None:
        with session_scope() as session:
            row = session.query(ImageLabel).filter(ImageLabel.image_id == image_id).first()
            if not row:
                return self._write_json({"category": "", "mood": "", "quality_score": 3, "is_thumbnail_candidate": False})
            return self._write_json(
                {
                    "category": row.category or "",
                    "mood": row.mood or "",
                    "quality_score": row.quality_score,
                    "is_thumbnail_candidate": bool(row.is_thumbnail_candidate),
                }
            )

    def _create_category(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        name = str(data.get("name") or "").strip()
        if not name:
            return self._write_json({"error": "name is required"}, 400)
        ok = CategoryRepository.add(name)
        if not ok:
            return self._write_json({"error": "duplicate or invalid category"}, 400)
        return self._write_json({"ok": True})

    def _update_category(self, category_id: int) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        name = str(data.get("name") or "").strip()
        if not name:
            return self._write_json({"error": "name is required"}, 400)
        ok = CategoryRepository.update(category_id=category_id, name=name)
        if not ok:
            return self._write_json({"error": "duplicate or invalid category"}, 400)
        return self._write_json({"ok": True})

    def _create_keyword(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)

        keyword = str(data.get("keyword") or "").strip()
        category_id = _to_int(data.get("category_id"))

        if not category_id:
            return self._write_json({"error": "category_id is required"}, 400)
        if not keyword:
            return self._write_json({"error": "keyword is required"}, 400)

        ok = KeywordRepository.add(keyword, category_id, is_auto_generated=False)
        if not ok:
            return self._write_json({"error": "duplicate or invalid keyword"}, 400)
        return self._write_json({"ok": True})

    def _create_keywords_bulk(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        category_id = _to_int(data.get("category_id"))
        keywords_raw = data.get("keywords")
        if not category_id:
            return self._write_json({"error": "category_id is required"}, 400)
        if not isinstance(keywords_raw, list):
            return self._write_json({"error": "keywords(list) is required"}, 400)

        added = 0
        duplicated = 0
        invalid = 0
        for raw in keywords_raw:
            keyword = str(raw or "").strip()
            if not keyword:
                invalid += 1
                continue
            ok = KeywordRepository.add(keyword, category_id, is_auto_generated=False)
            if ok:
                added += 1
            else:
                duplicated += 1
        return self._write_json({"ok": True, "added": added, "duplicated": duplicated, "invalid": invalid})

    def _toggle_keywords_batch(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        ids_raw = data.get("keyword_ids")
        if not isinstance(ids_raw, list):
            return self._write_json({"error": "keyword_ids(list) is required"}, 400)
        toggled = 0
        for raw in ids_raw:
            keyword_id = _to_int(raw)
            if not keyword_id:
                continue
            KeywordRepository.toggle(keyword_id)
            toggled += 1
        return self._write_json({"ok": True, "toggled": toggled})

    def _toggle_keyword(self, keyword_id: int) -> None:
        KeywordRepository.toggle(keyword_id)
        return self._write_json({"ok": True})

    def _block_related_keyword(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        source_keyword_id = _to_int(data.get("source_keyword_id"))
        related_keyword_id = _to_int(data.get("related_keyword_id"))
        if not source_keyword_id or not related_keyword_id:
            return self._write_json({"error": "source_keyword_id and related_keyword_id are required"}, 400)
        KeywordRepository.block_and_remove_related(source_keyword_id, related_keyword_id)
        return self._write_json({"ok": True})

    def _save_content_label(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        content_id = _to_int(data.get("content_id"))
        if not content_id:
            return self._write_json({"error": "content_id is required"}, 400)
        topics = data.get("topics")
        if isinstance(topics, str):
            topics = [item.strip() for item in topics.split(",") if item.strip()]
        if not isinstance(topics, list):
            topics = []
        LabelRepository.upsert_content_label(
            content_id=content_id,
            tone=(str(data.get("tone") or "").strip() or None),
            sentiment=(str(data.get("sentiment") or "").strip() or None),
            topics=[str(item).strip() for item in topics if str(item).strip()],
            quality_score=max(1, min(5, _to_int(data.get("quality_score")) or 3)),
            label_method="manual",
        )
        LabelRepository.mark_content_labeled(content_id=content_id, confidence=1.0, stage_status="completed", completed=True)
        return self._write_json({"ok": True})

    def _save_image_label(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        image_id = _to_int(data.get("image_id"))
        if not image_id:
            return self._write_json({"error": "image_id is required"}, 400)
        LabelRepository.upsert_image_label(
            image_id=image_id,
            category=(str(data.get("category") or "").strip() or None),
            mood=(str(data.get("mood") or "").strip() or None),
            quality_score=max(1, min(5, _to_int(data.get("quality_score")) or 3)),
            is_thumbnail_candidate=bool(data.get("is_thumbnail_candidate")),
            label_method="manual",
        )
        LabelRepository.mark_image_labeled(image_id=image_id, confidence=1.0, stage_status="completed", completed=True)
        return self._write_json({"ok": True})

    def _serve_dashboard_summary(self) -> None:
        with session_scope() as session:
            payload = {
                "categories": int(session.execute(select(func.count()).select_from(Category)).scalar_one() or 0),
                "keywords": int(session.execute(select(func.count()).select_from(Keyword)).scalar_one() or 0),
                "source_channels": int(session.execute(select(func.count()).select_from(SourceChannel)).scalar_one() or 0),
                "raw_contents": int(session.execute(select(func.count()).select_from(RawContent)).scalar_one() or 0),
                "crawl_jobs": int(session.execute(select(func.count()).select_from(CrawlJob)).scalar_one() or 0),
                "personas": int(session.execute(select(func.count()).select_from(Persona)).scalar_one() or 0),
                "templates": int(session.execute(select(func.count()).select_from(ArticleTemplate)).scalar_one() or 0),
                "ai_providers": int(session.execute(select(func.count()).select_from(AIProvider)).scalar_one() or 0),
                "writing_channels": int(session.execute(select(func.count()).select_from(WritingChannel)).scalar_one() or 0),
                "publish_channels": int(session.execute(select(func.count()).select_from(PublishChannel)).scalar_one() or 0),
                "articles": int(session.execute(select(func.count()).select_from(GeneratedArticle)).scalar_one() or 0),
                "publish_jobs": int(session.execute(select(func.count()).select_from(PublishJob)).scalar_one() or 0),
            }
        return self._write_json(payload)

    def _serve_labeling_automation_snapshot(self) -> None:
        snapshot = LabelRepository.get_label_automation_snapshot()
        return self._write_json({
            "contents_total": snapshot["contents_total"],
            "contents_labeled": snapshot["contents_labeled"],
            "contents_pending": snapshot["contents_pending"],
            "images_total": snapshot["images_total"],
            "images_labeled": snapshot["images_labeled"],
            "images_pending": snapshot["images_pending"],
            "total": snapshot["total"],
            "completed": snapshot["completed"],
            "completion_rate": round(float(snapshot["completion_rate"]), 2),
            "last_content_labeled_at": _dt_to_iso(snapshot["last_content_labeled_at"]),
            "last_image_labeled_at": _dt_to_iso(snapshot["last_image_labeled_at"]),
            "avg_content_quality": round(float(snapshot["avg_content_quality"]), 2),
            "avg_image_quality": round(float(snapshot["avg_image_quality"]), 2),
            "content_method_breakdown": snapshot.get("content_method_breakdown", {}),
            "image_method_breakdown": snapshot.get("image_method_breakdown", {}),
            "free_api_daily_limit": int(snapshot.get("free_api_daily_limit", 200)),
            "paid_api_daily_limit": int(snapshot.get("paid_api_daily_limit", 20)),
            "free_api_used_today": int(snapshot.get("free_api_used_today", 0)),
            "paid_api_used_today": int(snapshot.get("paid_api_used_today", 0)),
            "free_api_remaining_today": int(snapshot.get("free_api_remaining_today", 0)),
            "paid_api_remaining_today": int(snapshot.get("paid_api_remaining_today", 0)),
        })

    def _serve_labeling_run_logs(self, limit: int = 50) -> None:
        rows = LabelRepository.list_recent_run_logs(limit=limit)
        return self._write_json(
            [
                {
                    "id": int(row["id"]),
                    "run_kind": row["run_kind"],
                    "method": row["method"],
                    "stage_summary": row["stage_summary"],
                    "labeled_count": int(row["labeled_count"]),
                    "target_count": int(row["target_count"]),
                    "free_api_used": int(row["free_api_used"]),
                    "paid_api_used": int(row["paid_api_used"]),
                    "message": row["message"],
                    "created_at": _dt_to_iso(row["created_at"]),
                }
                for row in rows
            ]
        )

    def _serve_personas(self) -> None:
        rows = PersonaRepository.list_all()
        return self._write_json([
            {"id": row.id, "name": row.name, "age_group": row.age_group, "gender": row.gender, "personality": row.personality,
             "interests": row.interests, "speech_style": row.speech_style, "tone": row.tone, "style_guide": row.style_guide,
             "banned_words": row.banned_words, "is_active": row.is_active} for row in rows
        ])

    def _serve_templates(self, template_type: str | None = None, active_only: bool = False) -> None:
        rows = ArticleTemplateRepository.list_all(template_type=template_type, active_only=active_only)
        return self._write_json([
            {"id": row.id, "name": row.name, "template_type": row.template_type, "user_prompt": row.user_prompt,
             "output_schema": row.output_schema, "is_active": row.is_active, "version": row.version} for row in rows
        ])

    def _serve_ai_providers(self) -> None:
        rows = AIProviderRepository.list_all()
        return self._write_json([
            {"id": row.id, "provider": row.provider, "model_name": row.model_name, "api_key_alias": row.api_key_alias,
             "is_paid": row.is_paid, "is_enabled": row.is_enabled, "priority": row.priority,
             "rate_limit_per_min": row.rate_limit_per_min, "daily_budget_limit": row.daily_budget_limit,
             "status": row.status, "last_checked_at": _dt_to_iso(row.last_checked_at)} for row in rows
        ])

    def _serve_ai_provider_env_status(self) -> None:
        rows = AIProviderRepository.list_all()
        payload: list[dict] = []
        for row in rows:
            alias = str(row.api_key_alias or "").strip()
            if not alias:
                continue
            payload.append({
                "provider_id": row.id,
                "alias": alias,
                "exists": bool(os.getenv(alias)),
            })
        return self._write_json({"items": payload})

    def _serve_writer_personas(self) -> None:
        rows = PersonaRepository.list_all(active_only=True)
        return self._write_json([{"id": row.id, "name": row.name, "tone": row.tone} for row in rows])

    def _serve_writer_templates(self, template_type: str | None) -> None:
        rows = ArticleTemplateRepository.list_all(template_type=template_type, active_only=True)
        return self._write_json([{"id": row.id, "name": row.name, "version": row.version} for row in rows])

    def _serve_writer_channels(self) -> None:
        rows = WritingChannelRepository.list_all()
        return self._write_json([
            {
                "id": row.id,
                "code": row.code,
                "display_name": row.display_name,
                "channel_type": row.channel_type,
                "connection_type": row.connection_type,
                "status": row.status,
                "is_enabled": row.is_enabled,
                "owner_name": row.owner_name,
                "channel_identifier": row.channel_identifier,
                "default_category": row.default_category,
                "default_visibility": row.default_visibility,
                "tag_policy": row.tag_policy,
                "title_max_length": row.title_max_length,
                "body_min_length": row.body_min_length,
                "body_max_length": row.body_max_length,
                "allowed_markup": row.allowed_markup,
                "require_featured_image": row.require_featured_image,
                "image_max_count": row.image_max_count,
                "image_max_size_kb": row.image_max_size_kb,
                "external_link_policy": row.external_link_policy,
                "affiliate_disclosure_required": row.affiliate_disclosure_required,
                "meta_desc_max_length": row.meta_desc_max_length,
                "slug_rule": row.slug_rule,
                "publish_frequency_limit": row.publish_frequency_limit,
                "reserve_publish_enabled": row.reserve_publish_enabled,
                "api_rate_limit": row.api_rate_limit,
                "api_endpoint_url": row.api_endpoint_url,
                "auth_type": row.auth_type,
                "auth_reference": row.auth_reference,
                "notes": row.notes,
            }
            for row in rows
        ])

    def _serve_writer_run_summary(self) -> None:
        channels = WritingChannelRepository.list_all(enabled_only=True)
        policies = _sanitize_writer_channel_policies(
            _safe_json_object(AppSettingRepository.get_value(WriterSettingKeys.CHANNEL_POLICIES, "{}"))
        )
        providers = {int(p.id): p for p in AIProviderRepository.list_all()}

        items: list[dict] = []
        for ch in channels:
            policy = policies.get(str(ch.id), {})
            persona_ids = [n for n in (_to_int(v) for v in (policy.get("persona_ids") or [])) if n]
            template_ids = [n for n in (_to_int(v) for v in (policy.get("template_ids") or [])) if n]
            ai_provider_id = _to_int(policy.get("default_ai_provider_id"))
            provider_name = ""
            if ai_provider_id and ai_provider_id in providers:
                p = providers[ai_provider_id]
                provider_name = f"{p.provider}/{p.model_name}"
            items.append({
                "channel_id": ch.id,
                "channel_code": ch.code,
                "channel_name": ch.display_name,
                "persona_count": len(persona_ids),
                "template_count": len(template_ids),
                "ai_provider_id": ai_provider_id,
                "ai_provider_name": provider_name,
                "auto_enabled": _to_bool(policy.get("auto_enabled")),
                "auto_batch_count": max(1, _to_int(policy.get("auto_batch_count")) or 1),
                "policy_ready": len(persona_ids) > 0 and len(template_ids) > 0,
            })
        return self._write_json({"channels": items})

    def _serve_writer_result_board(self) -> None:
        limit = 200
        with session_scope() as session:
            articles = session.execute(
                select(GeneratedArticle).order_by(GeneratedArticle.created_at.desc()).limit(limit)
            ).scalars().all()
            article_ids = [int(a.id) for a in articles]

            latest_job_by_article: dict[int, PublishJob] = {}
            latest_done_by_article: dict[int, PublishJob] = {}
            if article_ids:
                jobs = session.execute(
                    select(PublishJob)
                    .where(PublishJob.article_id.in_(article_ids))
                    .order_by(PublishJob.created_at.desc())
                ).scalars().all()
                for job in jobs:
                    aid = int(job.article_id)
                    if aid not in latest_job_by_article:
                        latest_job_by_article[aid] = job
                    if aid not in latest_done_by_article and str(job.status) == "done":
                        latest_done_by_article[aid] = job

        rows: list[dict] = []
        for article in articles:
            aid = int(article.id)
            latest_job = latest_job_by_article.get(aid)
            latest_done = latest_done_by_article.get(aid)
            publish_status = "미발행"
            publish_channel = "-"
            if latest_job:
                publish_channel = latest_job.target_channel or "-"
                status_map = {
                    "queued": "발행대기",
                    "processing": "발행중",
                    "done": "발행완료",
                    "failed": "발행실패",
                }
                publish_status = status_map.get(str(latest_job.status), str(latest_job.status))

            rows.append({
                "id": aid,
                "title": article.title,
                "article_status": article.status,
                "publish_status": publish_status,
                "publish_channel": publish_channel,
                "created_at": _dt_to_iso(article.created_at),
                "last_published_at": _dt_to_iso(latest_done.processed_at if latest_done else None),
            })

        channels = PublishChannelRepository.list_enabled()
        PublishChannelSettingRepository.ensure_for_channels([row.code for row in channels])
        channel_items: list[dict] = []
        for row in channels:
            setting = PublishChannelSettingRepository.get_by_channel(row.code)
            auto_allowed = bool(setting and str(setting.publish_mode) == "auto")
            channel_items.append({
                "code": row.code,
                "display_name": row.display_name,
                "auto_allowed": auto_allowed,
            })

        return self._write_json({"items": rows, "publish_channels": channel_items})

    def _serve_writer_articles(self) -> None:
        rows = ArticleRepository.list_recent(100)
        return self._write_json([
            {"id": row.id, "format_type": row.format_type, "status": row.status, "title": row.title, "created_at": _dt_to_iso(row.created_at)}
            for row in rows
        ])

    def _serve_writer_article(self, article_id: int) -> None:
        row = ArticleRepository.get_by_id(article_id)
        if not row:
            return self._write_json({"error": "not found"}, 404)
        return self._write_json({"id": row.id, "title": row.title, "content": row.content, "status": row.status})

    def _serve_publish_channels(self) -> None:
        publish_auto_runner.sync_channels()
        rows = PublishChannelRepository.list_all()
        return self._write_json([{"id": row.id, "code": row.code, "display_name": row.display_name, "is_enabled": row.is_enabled} for row in rows])

    def _serve_publish_channel_settings(self) -> None:
        publish_auto_runner.sync_channels()
        channels = PublishChannelRepository.list_all()
        PublishChannelSettingRepository.ensure_for_channels([row.code for row in channels])
        rows = PublishChannelSettingRepository.list_all()
        return self._write_json([
            {"id": row.id, "channel_code": row.channel_code, "publish_cycle_minutes": row.publish_cycle_minutes,
             "publish_mode": row.publish_mode, "publish_format": row.publish_format, "writing_style": row.writing_style,
             "api_url": row.api_url} for row in rows
        ])

    def _serve_publish_channel_setting(self, channel_code: str) -> None:
        row = PublishChannelSettingRepository.get_by_channel(channel_code)
        if not row:
            return self._write_json({"error": "not found"}, 404)
        return self._write_json({"id": row.id, "channel_code": row.channel_code, "publish_cycle_minutes": row.publish_cycle_minutes,
                                 "publish_mode": row.publish_mode, "publish_format": row.publish_format,
                                 "writing_style": row.writing_style, "api_url": row.api_url})

    def _serve_publisher_channels(self) -> None:
        rows = PublishChannelRepository.list_enabled()
        return self._write_json([{"id": row.id, "code": row.code, "display_name": row.display_name} for row in rows])

    def _serve_publisher_articles(self) -> None:
        rows = ArticleRepository.list_recent(100)
        return self._write_json([{"id": row.id, "format_type": row.format_type, "status": row.status, "title": row.title} for row in rows])

    def _serve_publisher_jobs(self) -> None:
        rows = PublishRepository.list_recent(100)
        return self._write_json([
            {"id": row.id, "article_id": row.article_id, "target_channel": row.target_channel, "mode": row.mode,
             "status": row.status, "message": row.message, "created_at": _dt_to_iso(row.created_at)} for row in rows
        ])

    def _serve_publish_auto_status(self) -> None:
        return self._write_json(publish_auto_runner.status())

    def _serve_settings_app(self) -> None:
        return self._write_json({"app_name": settings.app_name, "data_dir": str(settings.data_dir), "db_path": str(settings.db_path)})

    def _serve_settings_runtime(self) -> None:
        return self._write_json({"max_collect": 3, "default_timeout": 15, "related_keyword_limit": AppSettingRepository.get_related_keyword_limit(10)})

    def _serve_v2_menu(self) -> None:
        return self._write_json({
            "items": list(get_v2_menu_tree()),
            "default_node_id": get_v2_default_entry(),
        })

    def _serve_v2_collect_settings(self) -> None:
        selected_channels = _safe_json_list(AppSettingRepository.get_value(CollectSettingKeys.SELECTED_CHANNEL_CODES, "[]"))
        selected_category_ids = [
            n for n in (_to_int(v) for v in _safe_json_list(AppSettingRepository.get_value(CollectSettingKeys.SELECTED_CATEGORY_IDS, "[]")))
            if n is not None
        ]
        return self._write_json({
            "keyword_scope": AppSettingRepository.get_value(CollectSettingKeys.KEYWORD_SCOPE, "selected"),
            "interval_minutes": _to_int(AppSettingRepository.get_value(CollectSettingKeys.INTERVAL_MINUTES, "60")) or 60,
            "max_results": _to_int(AppSettingRepository.get_value(CollectSettingKeys.MAX_RESULTS, "3")) or 3,
            "request_timeout": _to_int(AppSettingRepository.get_value(CollectSettingKeys.REQUEST_TIMEOUT, "15")) or 15,
            "retry_count": _to_int(AppSettingRepository.get_value(CollectSettingKeys.RETRY_COUNT, "1")) or 1,
            "selected_channel_codes": selected_channels,
            "selected_category_ids": selected_category_ids,
            "naver_related_sync": _to_bool(AppSettingRepository.get_value(CollectSettingKeys.NAVER_RELATED_SYNC, "1")),
        })

    def _serve_v2_label_settings(self) -> None:
        snapshot = LabelRepository.get_label_automation_snapshot()
        return self._write_json({
            "method": AppSettingRepository.get_value(LabelSettingKeys.METHOD, "rule"),
            "batch_size": _to_int(AppSettingRepository.get_value(LabelSettingKeys.BATCH_SIZE, "300")) or 300,
            "quality_threshold": _to_int(AppSettingRepository.get_value(LabelSettingKeys.QUALITY_THRESHOLD, "3")) or 3,
            "relabel_policy": AppSettingRepository.get_value(LabelSettingKeys.RELABEL_POLICY, "skip"),
            "auto_enabled": _to_bool(AppSettingRepository.get_value(LabelSettingKeys.AUTO_ENABLED, "0")),
            "interval_minutes": _to_int(AppSettingRepository.get_value(LabelSettingKeys.INTERVAL_MINUTES, "15")) or 15,
            "free_api_daily_limit": _to_int(AppSettingRepository.get_value(LabelSettingKeys.FREE_API_DAILY_LIMIT, "200")) or 200,
            "paid_api_daily_limit": _to_int(AppSettingRepository.get_value(LabelSettingKeys.PAID_API_DAILY_LIMIT, "20")) or 20,
            "threshold_mid": _to_int(AppSettingRepository.get_value(LabelSettingKeys.THRESHOLD_MID, "3")) or 3,
            "threshold_high": _to_int(AppSettingRepository.get_value(LabelSettingKeys.THRESHOLD_HIGH, "4")) or 4,
            "auto_status": labeling_auto_scheduler.status(),
            "free_api_used_today": int(snapshot.get("free_api_used_today", 0)),
            "paid_api_used_today": int(snapshot.get("paid_api_used_today", 0)),
            "free_api_remaining_today": int(snapshot.get("free_api_remaining_today", 0)),
            "paid_api_remaining_today": int(snapshot.get("paid_api_remaining_today", 0)),
        })

    def _serve_v2_writer_settings(self) -> None:
        raw_channel_policies = _safe_json_object(AppSettingRepository.get_value(WriterSettingKeys.CHANNEL_POLICIES, "{}"))
        channel_policies = _sanitize_writer_channel_policies(raw_channel_policies)
        return self._write_json({
            "ai_provider_priority": AppSettingRepository.get_value(WriterSettingKeys.AI_PROVIDER_PRIORITY, "cost_first"),
            "channel_policies": channel_policies,
        })

    def _serve_v2_publish_settings(self) -> None:
        return self._write_json({
            "channel_mode": AppSettingRepository.get_value(PublishSettingKeys.CHANNEL_MODE, "semi_auto"),
            "cycle_minutes": _to_int(AppSettingRepository.get_value(PublishSettingKeys.CYCLE_MINUTES, "60")) or 60,
            "retry_count": _to_int(AppSettingRepository.get_value(PublishSettingKeys.RETRY_COUNT, "1")) or 1,
            "require_approval": _to_bool(AppSettingRepository.get_value(PublishSettingKeys.REQUIRE_APPROVAL, "1")),
        })

    def _serve_v2_monitor_events(self, limit: int, cursor: str = "", stage: str = "") -> None:
        valid_stages = {"collect", "label_content", "label_image", "writer", "publish"}
        stage_filter = stage.strip().lower()
        if stage_filter and stage_filter not in valid_stages:
            return self._write_json({"error": "invalid stage", "error_code": "MONITOR_INVALID_STAGE"}, 400)

        cursor_dt: datetime | None = None
        if cursor:
            try:
                cursor_dt = datetime.fromisoformat(cursor.replace("Z", ""))
            except Exception:
                return self._write_json({"error": "invalid cursor", "error_code": "MONITOR_INVALID_CURSOR"}, 400)

        selected_stage_count = 1 if stage_filter else len(valid_stages)
        # Cost optimization: divide query budget by active stage count.
        per_stage_limit = max(20, min(160, (limit // selected_stage_count) + 12))
        events: list[dict] = []
        try:
            with session_scope() as session:
                if stage_filter in {"", "collect"}:
                    stmt = (
                        select(
                            CrawlJob.id,
                            CrawlJob.keyword_id,
                            CrawlJob.channel_code,
                            CrawlJob.status,
                            CrawlJob.error_message,
                            CrawlJob.created_at,
                            Keyword.keyword,
                        )
                        .select_from(CrawlJob)
                        .outerjoin(Keyword, CrawlJob.keyword_id == Keyword.id)
                        .order_by(CrawlJob.created_at.desc())
                        .limit(per_stage_limit)
                    )
                    if cursor_dt:
                        stmt = stmt.where(CrawlJob.created_at < cursor_dt)
                    for row in session.execute(stmt).all():
                        keyword_name = row.keyword if row.keyword else f"keyword:{row.keyword_id}"
                        message = f"{keyword_name} / {row.channel_code}"
                        if row.error_message:
                            message = f"{message} / {row.error_message}"
                        events.append({
                            "stage": "collect",
                            "status": row.status,
                            "message": message,
                            "time": _dt_to_iso(row.created_at),
                            "entity_id": row.id,
                            "retryable": True,
                        })

                if stage_filter in {"", "label_content"}:
                    stmt = (
                        select(ContentLabel.id, ContentLabel.content_id, ContentLabel.quality_score, ContentLabel.labeled_at)
                        .order_by(ContentLabel.labeled_at.desc())
                        .limit(per_stage_limit)
                    )
                    if cursor_dt:
                        stmt = stmt.where(ContentLabel.labeled_at < cursor_dt)
                    for row in session.execute(stmt).all():
                        events.append({
                            "stage": "label_content",
                            "status": "done",
                            "message": f"content_id={row.content_id}, score={row.quality_score}",
                            "time": _dt_to_iso(row.labeled_at),
                            "entity_id": row.content_id,
                            "retryable": False,
                        })

                if stage_filter in {"", "label_image"}:
                    stmt = (
                        select(ImageLabel.id, ImageLabel.image_id, ImageLabel.quality_score, ImageLabel.labeled_at)
                        .order_by(ImageLabel.labeled_at.desc())
                        .limit(per_stage_limit)
                    )
                    if cursor_dt:
                        stmt = stmt.where(ImageLabel.labeled_at < cursor_dt)
                    for row in session.execute(stmt).all():
                        events.append({
                            "stage": "label_image",
                            "status": "done",
                            "message": f"image_id={row.image_id}, score={row.quality_score}",
                            "time": _dt_to_iso(row.labeled_at),
                            "entity_id": row.image_id,
                            "retryable": False,
                        })

                if stage_filter in {"", "writer"}:
                    stmt = (
                        select(GeneratedArticle.id, GeneratedArticle.title, GeneratedArticle.status, GeneratedArticle.created_at)
                        .order_by(GeneratedArticle.created_at.desc())
                        .limit(per_stage_limit)
                    )
                    if cursor_dt:
                        stmt = stmt.where(GeneratedArticle.created_at < cursor_dt)
                    for row in session.execute(stmt).all():
                        events.append({
                            "stage": "writer",
                            "status": row.status,
                            "message": f"{row.id} / {row.title}",
                            "time": _dt_to_iso(row.created_at),
                            "entity_id": row.id,
                            "retryable": False,
                        })

                if stage_filter in {"", "publish"}:
                    stmt = (
                        select(PublishJob.id, PublishJob.article_id, PublishJob.target_channel, PublishJob.status, PublishJob.message, PublishJob.created_at)
                        .order_by(PublishJob.created_at.desc())
                        .limit(per_stage_limit)
                    )
                    if cursor_dt:
                        stmt = stmt.where(PublishJob.created_at < cursor_dt)
                    for row in session.execute(stmt).all():
                        events.append({
                            "stage": "publish",
                            "status": row.status,
                            "message": f"{row.article_id} / {row.target_channel} / {row.message or ''}".strip(" /"),
                            "time": _dt_to_iso(row.created_at),
                            "entity_id": row.id,
                            "retryable": str(row.status).lower() in {"failed", "queued"},
                        })
        except Exception as exc:
            return self._write_json({"items": [], "total": 0, "next_cursor": "", "error_code": "MONITOR_QUERY_ERROR", "error": str(exc)}, 500)

        events.sort(key=lambda item: item.get("time") or "", reverse=True)
        page = events[:limit]
        next_cursor = page[-1].get("time") if len(page) >= limit else ""
        return self._write_json({"items": page, "total": len(events), "next_cursor": next_cursor, "error_code": ""})

    def _create_persona(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        fields: dict[str, str] = {}
        name = str(data.get("name") or "").strip()
        if not name:
            fields["name"] = "이름은 필수입니다."
        if fields:
            return self._write_validation_error(fields, "페르소나 입력값을 확인하세요.")
        ok = PersonaRepository.add(name=str(data.get("name") or ""), age_group=str(data.get("age_group") or ""), gender=str(data.get("gender") or ""),
            personality=str(data.get("personality") or ""), interests=str(data.get("interests") or ""), speech_style=str(data.get("speech_style") or ""),
            tone=str(data.get("tone") or ""), style_guide=str(data.get("style_guide") or ""), banned_words=str(data.get("banned_words") or ""))
        if not ok:
            return self._write_json({"error": "페르소나 추가 실패"}, 400)
        return self._write_json({"ok": True})

    def _update_persona(self, persona_id: int) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        fields: dict[str, str] = {}
        name = str(data.get("name") or "").strip()
        if not name:
            fields["name"] = "이름은 필수입니다."
        if fields:
            return self._write_validation_error(fields, "페르소나 입력값을 확인하세요.")
        ok = PersonaRepository.update(persona_id=persona_id, name=str(data.get("name") or ""), age_group=str(data.get("age_group") or ""),
            gender=str(data.get("gender") or ""), personality=str(data.get("personality") or ""), interests=str(data.get("interests") or ""),
            speech_style=str(data.get("speech_style") or ""), tone=str(data.get("tone") or ""), style_guide=str(data.get("style_guide") or ""),
            banned_words=str(data.get("banned_words") or ""), is_active=bool(data.get("is_active")))
        if not ok:
            return self._write_json({"error": "페르소나 수정 실패"}, 400)
        return self._write_json({"ok": True})

    def _create_template(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        fields: dict[str, str] = {}
        name = str(data.get("name") or "").strip()
        template_type = str(data.get("template_type") or "").strip()
        user_prompt = str(data.get("user_prompt") or "").strip()
        if not name:
            fields["name"] = "템플릿 이름은 필수입니다."
        if template_type not in {"blog", "sns", "board"}:
            fields["template_type"] = "템플릿 유형이 유효하지 않습니다."
        if not user_prompt:
            fields["user_prompt"] = "프롬프트 템플릿은 필수입니다."
        if fields:
            return self._write_validation_error(fields, "템플릿 입력값을 확인하세요.")
        ok = ArticleTemplateRepository.add(name=str(data.get("name") or ""), template_type=str(data.get("template_type") or ""),
            user_prompt=str(data.get("user_prompt") or ""), output_schema=str(data.get("output_schema") or ""))
        if not ok:
            return self._write_json({"error": "템플릿 추가 실패"}, 400)
        return self._write_json({"ok": True})

    def _update_template(self, template_id: int) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        fields: dict[str, str] = {}
        name = str(data.get("name") or "").strip()
        template_type = str(data.get("template_type") or "").strip()
        user_prompt = str(data.get("user_prompt") or "").strip()
        if not name:
            fields["name"] = "템플릿 이름은 필수입니다."
        if template_type not in {"blog", "sns", "board"}:
            fields["template_type"] = "템플릿 유형이 유효하지 않습니다."
        if not user_prompt:
            fields["user_prompt"] = "프롬프트 템플릿은 필수입니다."
        if fields:
            return self._write_validation_error(fields, "템플릿 입력값을 확인하세요.")
        ok = ArticleTemplateRepository.update(template_id=template_id, name=str(data.get("name") or ""), template_type=str(data.get("template_type") or ""),
            user_prompt=str(data.get("user_prompt") or ""), system_prompt=None, output_schema=str(data.get("output_schema") or ""),
            is_active=bool(data.get("is_active")), version=max(1, _to_int(data.get("version")) or 1))
        if not ok:
            return self._write_json({"error": "템플릿 수정 실패"}, 400)
        return self._write_json({"ok": True})

    def _create_ai_provider(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        fields: dict[str, str] = {}
        provider = str(data.get("provider") or "").strip()
        model_name = str(data.get("model_name") or "").strip()
        alias = str(data.get("api_key_alias") or "").strip()
        status = str(data.get("status") or "unknown").strip()
        if not provider:
            fields["provider"] = "Provider는 필수입니다."
        if not model_name:
            fields["model_name"] = "Model은 필수입니다."
        if alias and not re.fullmatch(r"[A-Z][A-Z0-9_]{1,127}", alias):
            fields["api_key_alias"] = "KEY Alias는 대문자/숫자/_ 형식이어야 합니다."
        if status not in {"ready", "error", "blocked", "unknown"}:
            fields["status"] = "상태값이 유효하지 않습니다."
        if fields:
            return self._write_validation_error(fields, "AI Provider 입력값을 확인하세요.")
        ok = AIProviderRepository.add(provider=str(data.get("provider") or ""), model_name=str(data.get("model_name") or ""),
            api_key_alias=str(data.get("api_key_alias") or ""), is_paid=bool(data.get("is_paid")),
            priority=max(1, _to_int(data.get("priority")) or 1), rate_limit_per_min=_to_int(data.get("rate_limit_per_min")) or None,
            daily_budget_limit=_to_int(data.get("daily_budget_limit")) or None, status=str(data.get("status") or "unknown"))
        if not ok:
            return self._write_json({"error": "AI Provider 추가 실패"}, 400)
        return self._write_json({"ok": True})

    def _update_ai_provider(self, provider_id: int) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        fields: dict[str, str] = {}
        provider = str(data.get("provider") or "").strip()
        model_name = str(data.get("model_name") or "").strip()
        alias = str(data.get("api_key_alias") or "").strip()
        status = str(data.get("status") or "unknown").strip()
        if not provider:
            fields["provider"] = "Provider는 필수입니다."
        if not model_name:
            fields["model_name"] = "Model은 필수입니다."
        if alias and not re.fullmatch(r"[A-Z][A-Z0-9_]{1,127}", alias):
            fields["api_key_alias"] = "KEY Alias는 대문자/숫자/_ 형식이어야 합니다."
        if status not in {"ready", "error", "blocked", "unknown"}:
            fields["status"] = "상태값이 유효하지 않습니다."
        if fields:
            return self._write_validation_error(fields, "AI Provider 입력값을 확인하세요.")
        ok = AIProviderRepository.update(provider_id=provider_id, provider=str(data.get("provider") or ""), model_name=str(data.get("model_name") or ""),
            api_key_alias=str(data.get("api_key_alias") or ""), is_paid=bool(data.get("is_paid")), is_enabled=bool(data.get("is_enabled")),
            priority=max(1, _to_int(data.get("priority")) or 1), rate_limit_per_min=_to_int(data.get("rate_limit_per_min")) or None,
            daily_budget_limit=_to_int(data.get("daily_budget_limit")) or None, status=str(data.get("status") or "unknown"))
        if not ok:
            return self._write_json({"error": "AI Provider 수정 실패"}, 400)
        return self._write_json({"ok": True})

    def _create_writer_channel(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        fields = self._validate_writer_channel_payload(data, is_update=False)
        if fields:
            return self._write_validation_error(fields, "작성 채널 입력값을 확인하세요.")
        payload = self._writer_channel_payload(data)
        ok = WritingChannelRepository.add(**payload)
        if not ok:
            return self._write_json({"error": "작성 채널 추가 실패"}, 400)
        return self._write_json({"ok": True})

    def _update_writer_channel(self, channel_id: int) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        fields = self._validate_writer_channel_payload(data, is_update=True)
        if fields:
            return self._write_validation_error(fields, "작성 채널 입력값을 확인하세요.")
        payload = self._writer_channel_payload(data)
        ok = WritingChannelRepository.update(channel_id=channel_id, **payload)
        if not ok:
            return self._write_json({"error": "작성 채널 수정 실패"}, 400)
        return self._write_json({"ok": True})

    def _validate_writer_channel_payload(self, data: dict, is_update: bool) -> dict[str, str]:
        fields: dict[str, str] = {}
        code = str(data.get("code") or "").strip()
        display_name = str(data.get("display_name") or "").strip()
        channel_type = str(data.get("channel_type") or "blog").strip()
        connection_type = str(data.get("connection_type") or "api").strip()
        status = str(data.get("status") or "active").strip()
        auth_type = str(data.get("auth_type") or "").strip()
        api_url = str(data.get("api_endpoint_url") or "").strip()
        affiliate_required = _to_bool(data.get("affiliate_disclosure_required"))
        notes = str(data.get("notes") or "").strip()

        if not code:
            fields["code"] = "채널 코드는 필수입니다."
        elif not re.fullmatch(r"[a-z0-9_-]{2,50}", code):
            fields["code"] = "채널 코드는 소문자/숫자/_/- 2~50자여야 합니다."
        if not display_name:
            fields["display_name"] = "채널명은 필수입니다."
        if channel_type not in {"blog", "cms", "sns", "board", "custom_api"}:
            fields["channel_type"] = "채널 유형이 유효하지 않습니다."
        if connection_type not in {"api", "manual", "rss_email"}:
            fields["connection_type"] = "연결 방식이 유효하지 않습니다."
        if status not in {"active", "expiring", "auth_error", "paused"}:
            fields["status"] = "상태값이 유효하지 않습니다."
        if auth_type not in {"", "id_password", "token", "oauth", "app_password"}:
            fields["auth_type"] = "인증 방식이 유효하지 않습니다."
        if api_url and not (api_url.startswith("http://") or api_url.startswith("https://")):
            fields["api_endpoint_url"] = "API 접속 URL은 http/https만 허용됩니다."
        if affiliate_required and not notes:
            fields["notes"] = "제휴 문구 필수 사용 시 제휴 문구를 입력하세요."
        if is_update:
            # registered code immutability is validated in frontend, server still enforces basic format only.
            pass
        return fields

    def _writer_channel_payload(self, data: dict) -> dict:
        return {
            "code": str(data.get("code") or "").strip(),
            "display_name": str(data.get("display_name") or "").strip(),
            "channel_type": str(data.get("channel_type") or "blog"),
            "connection_type": str(data.get("connection_type") or "api"),
            "status": str(data.get("status") or "active"),
            "is_enabled": True if data.get("is_enabled") is None else _to_bool(data.get("is_enabled")),
            "owner_name": str(data.get("owner_name") or ""),
            "channel_identifier": str(data.get("channel_identifier") or ""),
            "default_category": str(data.get("default_category") or ""),
            "default_visibility": str(data.get("default_visibility") or ""),
            "tag_policy": str(data.get("tag_policy") or ""),
            "title_max_length": _to_int(data.get("title_max_length")),
            "body_min_length": _to_int(data.get("body_min_length")),
            "body_max_length": _to_int(data.get("body_max_length")),
            "allowed_markup": str(data.get("allowed_markup") or ""),
            "require_featured_image": _to_bool(data.get("require_featured_image")),
            "image_max_count": _to_int(data.get("image_max_count")),
            "image_max_size_kb": _to_int(data.get("image_max_size_kb")),
            "external_link_policy": str(data.get("external_link_policy") or ""),
            "affiliate_disclosure_required": _to_bool(data.get("affiliate_disclosure_required")),
            "meta_desc_max_length": _to_int(data.get("meta_desc_max_length")),
            "slug_rule": str(data.get("slug_rule") or ""),
            "publish_frequency_limit": _to_int(data.get("publish_frequency_limit")),
            "reserve_publish_enabled": True if data.get("reserve_publish_enabled") is None else _to_bool(data.get("reserve_publish_enabled")),
            "api_rate_limit": _to_int(data.get("api_rate_limit")),
            "api_endpoint_url": str(data.get("api_endpoint_url") or ""),
            "auth_type": str(data.get("auth_type") or ""),
            "auth_reference": str(data.get("auth_reference") or ""),
            "notes": str(data.get("notes") or ""),
        }

    def _writer_generate(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)

        persona_id = _to_int(data.get("persona_id"))
        template_id = _to_int(data.get("template_id"))
        writing_channel_id = _to_int(data.get("writing_channel_id"))
        ai_provider_id = _to_int(data.get("ai_provider_id"))
        raw_policies = _safe_json_object(AppSettingRepository.get_value(WriterSettingKeys.CHANNEL_POLICIES, "{}"))
        policies = _sanitize_writer_channel_policies(raw_policies)

        if not writing_channel_id:
            enabled_channels = WritingChannelRepository.list_all(enabled_only=True)
            if enabled_channels:
                writing_channel_id = int(enabled_channels[0].id)

        channel_key = str(writing_channel_id) if writing_channel_id else ""
        channel_policy = policies.get(channel_key, {}) if channel_key else {}

        auto_persona_used = False
        auto_template_used = False
        if not persona_id:
            persona_ids = [n for n in (_to_int(v) for v in (channel_policy.get("persona_ids") or [])) if n]
            if persona_ids:
                cursor = max(0, _to_int(channel_policy.get("persona_cursor")) or 0)
                idx = cursor % len(persona_ids)
                persona_id = persona_ids[idx]
                channel_policy["persona_cursor"] = cursor + 1
                auto_persona_used = True
        if not template_id:
            template_ids = [n for n in (_to_int(v) for v in (channel_policy.get("template_ids") or [])) if n]
            if template_ids:
                cursor = max(0, _to_int(channel_policy.get("template_cursor")) or 0)
                idx = cursor % len(template_ids)
                template_id = template_ids[idx]
                channel_policy["template_cursor"] = cursor + 1
                auto_template_used = True
        if not ai_provider_id:
            ai_provider_id = _to_int(channel_policy.get("default_ai_provider_id"))
        if not persona_id or not template_id:
            return self._write_json({"error": "선택된 채널 정책에 페르소나/템플릿이 없습니다. 채널별 작성 정책을 저장하세요."}, 400)

        source_limit = _to_int(channel_policy.get("min_source_count")) or 3
        source_limit = max(1, min(20, source_limit))

        if channel_key and (auto_persona_used or auto_template_used):
            policies[channel_key] = channel_policy
            AppSettingRepository.set_value(WriterSettingKeys.CHANNEL_POLICIES, json.dumps(policies, ensure_ascii=False))

        try:
            result = writer_service.generate_draft(
                persona_id=persona_id,
                template_id=template_id,
                source_limit=source_limit,
                writing_channel_id=writing_channel_id,
                ai_provider_id=ai_provider_id,
            )
        except Exception as exc:
            return self._write_json({"error": str(exc)}, 400)
        return self._write_json({"ok": True, **result})

    def _writer_run(self) -> None:
        if not writer_run_control.start():
            return self._write_json({"error": "이미 글 작성 실행 중입니다.", **writer_run_control.status()}, 409)
        try:
            data = self._read_json_body()
            if data is None:
                return self._write_json({"error": "Invalid JSON body"}, 400)

            requested_channel_ids = {
                n for n in (_to_int(v) for v in (data.get("channel_ids") or []))
                if n is not None and n > 0
            }
            channels = WritingChannelRepository.list_all(enabled_only=True)
            if requested_channel_ids:
                channels = [c for c in channels if int(c.id) in requested_channel_ids]
            if not channels:
                return self._write_json({"ok": True, "messages": ["실행 대상 채널이 없습니다."], "created_count": 0, "processed_channels": 0, "stopped": False})

            raw_policies = _safe_json_object(AppSettingRepository.get_value(WriterSettingKeys.CHANNEL_POLICIES, "{}"))
            policies = _sanitize_writer_channel_policies(raw_policies)

            messages: list[str] = []
            created_count = 0
            processed_channels = 0
            total = len(channels)

            for idx, ch in enumerate(channels, 1):
                if writer_run_control.should_stop():
                    messages.append(f"[{idx}/{total}] 중단 요청으로 실행을 종료합니다.")
                    break

                policy_key = str(ch.id)
                policy = policies.get(policy_key, {})
                persona_ids = [n for n in (_to_int(v) for v in (policy.get("persona_ids") or [])) if n]
                template_ids = [n for n in (_to_int(v) for v in (policy.get("template_ids") or [])) if n]
                if not persona_ids or not template_ids:
                    messages.append(f"[{idx}/{total}] {ch.display_name}: 정책 미완성(페르소나/템플릿 없음)으로 건너뜀")
                    continue

                batch_count = max(1, min(20, _to_int(policy.get("auto_batch_count")) or 1))
                source_limit = max(1, min(20, _to_int(policy.get("min_source_count")) or 3))
                ai_provider_id = _to_int(policy.get("default_ai_provider_id"))
                persona_cursor = max(0, _to_int(policy.get("persona_cursor")) or 0)
                template_cursor = max(0, _to_int(policy.get("template_cursor")) or 0)

                messages.append(f"[{idx}/{total}] {ch.display_name}: 실행 시작 (회차 {batch_count})")
                for run_no in range(1, batch_count + 1):
                    if writer_run_control.should_stop():
                        messages.append(f"[{idx}/{total}] {ch.display_name}: 중단 요청으로 채널 실행 종료")
                        break
                    persona_id = persona_ids[persona_cursor % len(persona_ids)]
                    template_id = template_ids[template_cursor % len(template_ids)]
                    persona_cursor += 1
                    template_cursor += 1
                    try:
                        result = writer_service.generate_draft(
                            persona_id=persona_id,
                            template_id=template_id,
                            source_limit=source_limit,
                            writing_channel_id=int(ch.id),
                            ai_provider_id=ai_provider_id,
                        )
                        created_count += 1
                        messages.append(f"[{idx}/{total}] {ch.display_name} {run_no}/{batch_count}: 생성 완료 (article_id={result.get('id')})")
                    except Exception as exc:
                        messages.append(f"[{idx}/{total}] {ch.display_name} {run_no}/{batch_count}: 생성 실패 ({exc})")

                policy["persona_cursor"] = persona_cursor
                policy["template_cursor"] = template_cursor
                policies[policy_key] = policy
                processed_channels += 1

            AppSettingRepository.set_value(WriterSettingKeys.CHANNEL_POLICIES, json.dumps(policies, ensure_ascii=False))
            stopped = writer_run_control.should_stop()
            return self._write_json({
                "ok": not stopped,
                "stopped": stopped,
                "messages": messages,
                "created_count": created_count,
                "processed_channels": processed_channels,
            })
        finally:
            writer_run_control.finish()

    def _writer_result_board_publish(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        article_id = _to_int(data.get("article_id"))
        target_channel = str(data.get("target_channel") or "").strip()
        if not article_id or not target_channel:
            return self._write_json({"error": "article_id/target_channel is required"}, 400)

        setting = PublishChannelSettingRepository.get_by_channel(target_channel)
        if not setting or str(setting.publish_mode) != "auto":
            return self._write_json({"error": "선택 채널은 자동 발행 허용 채널이 아닙니다."}, 400)

        try:
            job_id = publisher_service.enqueue_publish(article_id=article_id, target_channel=target_channel, mode="auto")
            result = publisher_service.process_job(job_id)
            return self._write_json({"ok": True, "job_id": job_id, "result": result})
        except Exception as exc:
            return self._write_json({"error": str(exc)}, 400)

    def _writer_batch_update_status(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        status = str(data.get("status") or "").strip().lower()
        if status not in {"draft", "ready", "published", "failed"}:
            return self._write_json({"error": "invalid status"}, 400)
        ids_raw = data.get("article_ids")
        if not isinstance(ids_raw, list):
            return self._write_json({"error": "article_ids(list) is required"}, 400)
        updated = 0
        for raw in ids_raw:
            article_id = _to_int(raw)
            if not article_id:
                continue
            ArticleRepository.update_status(article_id=article_id, status=status)
            updated += 1
        return self._write_json({"ok": True, "updated": updated})

    def _health_check_ai_provider(self, provider_id: int) -> None:
        row = AIProviderRepository.get_by_id(provider_id)
        if not row:
            return self._write_json({"error": "provider not found"}, 404)
        alias = str(row.api_key_alias or "").strip()
        has_env = bool(alias and os.getenv(alias))
        enabled = bool(row.is_enabled)
        if not enabled:
            return self._write_json({"ok": False, "message": "비활성 Provider", "has_env": has_env, "status": "disabled"})
        if alias and not has_env:
            return self._write_json({"ok": False, "message": f"환경변수 누락: {alias}", "has_env": False, "status": "error"})
        return self._write_json({"ok": True, "message": "기본 점검 통과", "has_env": has_env, "status": "ready"})

    def _writer_save_article(self, article_id: int) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        ArticleRepository.update_content(article_id=article_id, title=str(data.get("title") or "")[:500], content=str(data.get("content") or ""))
        return self._write_json({"ok": True})

    def _create_publish_channel(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        code = str(data.get("code") or "").strip()
        display_name = str(data.get("display_name") or "").strip()
        fields: dict[str, str] = {}
        if not code:
            fields["code"] = "채널 코드는 필수입니다."
        elif not re.fullmatch(r"[a-z0-9_-]{2,50}", code):
            fields["code"] = "채널 코드는 소문자/숫자/_/- 2~50자여야 합니다."
        if not display_name:
            fields["display_name"] = "채널명은 필수입니다."
        if fields:
            return self._write_validation_error(fields, "발행 채널 입력값을 확인하세요.")
        ok = PublishChannelRepository.add(code=code, display_name=display_name)
        if not ok:
            return self._write_json({"error": "발행채널 추가 실패"}, 400)
        PublishChannelSettingRepository.ensure_for_channels([code])
        return self._write_json({"ok": True})

    def _save_publish_channel_setting(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        channel_code = str(data.get("channel_code") or "").strip()
        if not channel_code:
            return self._write_json({"error": "channel_code is required"}, 400)
        publish_mode = str(data.get("publish_mode") or "semi_auto")
        publish_format = str(data.get("publish_format") or "blog")
        writing_style = str(data.get("writing_style") or "informative")
        api_url = str(data.get("api_url") or "").strip()
        fields: dict[str, str] = {}
        if publish_mode not in {"semi_auto", "auto"}:
            fields["publish_mode"] = "발행 모드가 유효하지 않습니다."
        if publish_format not in {"blog", "sns", "board"}:
            fields["publish_format"] = "발행 형식이 유효하지 않습니다."
        if writing_style not in {"informative", "emotional", "review"}:
            fields["writing_style"] = "작성 형식이 유효하지 않습니다."
        if api_url and not (api_url.startswith("http://") or api_url.startswith("https://")):
            fields["api_url"] = "API URL은 http/https만 허용됩니다."
        if fields:
            return self._write_validation_error(fields, "채널별 발행 설정 입력값을 확인하세요.")
        PublishChannelSettingRepository.upsert(channel_code=channel_code, publish_cycle_minutes=max(5, min(1440, _to_int(data.get("publish_cycle_minutes")) or 60)),
            publish_mode=publish_mode, publish_format=publish_format,
            writing_style=writing_style, api_url=api_url)
        return self._write_json({"ok": True})

    def _test_publish_channel_api_url(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        api_url = str(data.get("api_url") or "").strip()
        if not api_url:
            return self._write_json({"error": "api_url is required"}, 400)
        if not (api_url.startswith("http://") or api_url.startswith("https://")):
            return self._write_json({"ok": False, "status_code": 0, "message": "http/https URL만 허용됩니다."})
        try:
            req = urlrequest.Request(api_url, method="GET")
            with urlrequest.urlopen(req, timeout=5) as resp:
                code = int(getattr(resp, "status", 200) or 200)
                return self._write_json({"ok": 200 <= code < 400, "status_code": code, "message": "연결 성공"})
        except urlerror.HTTPError as exc:
            return self._write_json({"ok": False, "status_code": int(exc.code or 0), "message": f"HTTP 오류: {exc.reason}"})
        except Exception as exc:
            return self._write_json({"ok": False, "status_code": 0, "message": str(exc)})

    def _save_publish_auto_pause_until(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        raw = str(data.get("pause_until") or "").strip()
        if not raw:
            publish_auto_runner.set_pause_until(None)
            AppSettingRepository.set_value("publish.auto_pause_until", "")
            return self._write_json({"ok": True, "pause_until": None, **publish_auto_runner.status()})
        try:
            pause_until = datetime.fromisoformat(raw.replace("Z", ""))
        except Exception:
            return self._write_json({"error": "pause_until 형식이 올바르지 않습니다."}, 400)
        publish_auto_runner.set_pause_until(pause_until)
        AppSettingRepository.set_value("publish.auto_pause_until", pause_until.isoformat())
        return self._write_json({"ok": True, "pause_until": _dt_to_iso(pause_until), **publish_auto_runner.status()})

    def _publisher_enqueue(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        article_id = _to_int(data.get("article_id"))
        target_channel = str(data.get("target_channel") or "").strip()

        default_mode = str(AppSettingRepository.get_value(PublishSettingKeys.CHANNEL_MODE, "semi_auto") or "semi_auto").strip() or "semi_auto"
        mode = str(data.get("mode") or default_mode).strip() or default_mode
        require_approval = _to_bool(AppSettingRepository.get_value(PublishSettingKeys.REQUIRE_APPROVAL, "1"))
        if require_approval:
            mode = "semi_auto"

        if not article_id or not target_channel:
            return self._write_json({"error": "article_id/target_channel is required"}, 400)
        job_id = publisher_service.enqueue_publish(article_id=article_id, target_channel=target_channel, mode=mode)
        return self._write_json({"ok": True, "job_id": job_id})

    def _publisher_process_job(self, job_id: int) -> None:
        result = publisher_service.process_job(job_id)
        return self._write_json({"ok": True, "result": result})

    def _save_settings_runtime(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        related_limit = _to_int(data.get("related_keyword_limit"))
        if related_limit is not None:
            AppSettingRepository.set_related_keyword_limit(related_limit)
        return self._write_json({"ok": True})

    def _save_v2_collect_settings(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)

        scope = str(data.get("keyword_scope") or "selected").strip().lower()
        if scope not in {"all", "selected", "related"}:
            scope = "selected"

        channel_codes: list[str] = []
        for raw_code in (data.get("selected_channel_codes") or []):
            code = str(raw_code or "").strip()
            if code:
                channel_codes.append(code)
        channel_codes = sorted(set(channel_codes))

        category_ids: list[int] = []
        for raw_id in (data.get("selected_category_ids") or []):
            n = _to_int(raw_id)
            if n is not None:
                category_ids.append(n)
        category_ids = sorted(set(category_ids))

        AppSettingRepository.set_value(CollectSettingKeys.KEYWORD_SCOPE, scope)
        AppSettingRepository.set_value(CollectSettingKeys.INTERVAL_MINUTES, str(max(5, min(1440, _to_int(data.get("interval_minutes")) or 60))))
        AppSettingRepository.set_value(CollectSettingKeys.MAX_RESULTS, str(max(1, min(20, _to_int(data.get("max_results")) or 3))))
        AppSettingRepository.set_value(CollectSettingKeys.REQUEST_TIMEOUT, str(max(3, min(120, _to_int(data.get("request_timeout")) or 15))))
        AppSettingRepository.set_value(CollectSettingKeys.RETRY_COUNT, str(max(0, min(5, _to_int(data.get("retry_count")) or 1))))
        AppSettingRepository.set_value(CollectSettingKeys.SELECTED_CHANNEL_CODES, json.dumps(channel_codes, ensure_ascii=False))
        AppSettingRepository.set_value(CollectSettingKeys.SELECTED_CATEGORY_IDS, json.dumps(category_ids, ensure_ascii=False))
        AppSettingRepository.set_value(CollectSettingKeys.NAVER_RELATED_SYNC, "1" if _to_bool(data.get("naver_related_sync")) else "0")
        return self._write_json({"ok": True})

    def _save_v2_label_settings(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        AppSettingRepository.set_value(LabelSettingKeys.METHOD, str(data.get("method") or "rule"))
        AppSettingRepository.set_value(LabelSettingKeys.BATCH_SIZE, str(max(10, min(1000, _to_int(data.get("batch_size")) or 300))))
        AppSettingRepository.set_value(LabelSettingKeys.QUALITY_THRESHOLD, str(max(1, min(5, _to_int(data.get("quality_threshold")) or 3))))
        AppSettingRepository.set_value(LabelSettingKeys.RELABEL_POLICY, str(data.get("relabel_policy") or "skip"))
        AppSettingRepository.set_value(LabelSettingKeys.AUTO_ENABLED, "1" if _to_bool(data.get("auto_enabled")) else "0")
        AppSettingRepository.set_value(LabelSettingKeys.INTERVAL_MINUTES, str(max(5, min(1440, _to_int(data.get("interval_minutes")) or 15))))
        AppSettingRepository.set_value(LabelSettingKeys.FREE_API_DAILY_LIMIT, str(max(0, min(100000, _to_int(data.get("free_api_daily_limit")) or 200))))
        AppSettingRepository.set_value(LabelSettingKeys.PAID_API_DAILY_LIMIT, str(max(0, min(100000, _to_int(data.get("paid_api_daily_limit")) or 20))))
        threshold_mid = max(1, min(5, _to_int(data.get("threshold_mid")) or 3))
        threshold_high = max(threshold_mid, min(5, _to_int(data.get("threshold_high")) or 4))
        AppSettingRepository.set_value(LabelSettingKeys.THRESHOLD_MID, str(threshold_mid))
        AppSettingRepository.set_value(LabelSettingKeys.THRESHOLD_HIGH, str(threshold_high))
        return self._write_json({"ok": True})

    def _save_v2_writer_settings(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        raw_channel_policies = data.get("channel_policies")
        channel_policies = _sanitize_writer_channel_policies(raw_channel_policies if isinstance(raw_channel_policies, dict) else {})
        AppSettingRepository.set_value(WriterSettingKeys.CHANNEL_POLICIES, json.dumps(channel_policies, ensure_ascii=False))
        AppSettingRepository.set_value(WriterSettingKeys.AI_PROVIDER_PRIORITY, str(data.get("ai_provider_priority") or "cost_first"))
        return self._write_json({"ok": True})

    def _save_v2_publish_settings(self) -> None:
        data = self._read_json_body()
        if data is None:
            return self._write_json({"error": "Invalid JSON body"}, 400)
        AppSettingRepository.set_value(PublishSettingKeys.CHANNEL_MODE, str(data.get("channel_mode") or "semi_auto"))
        AppSettingRepository.set_value(PublishSettingKeys.CYCLE_MINUTES, str(max(5, min(1440, _to_int(data.get("cycle_minutes")) or 60))))
        AppSettingRepository.set_value(PublishSettingKeys.RETRY_COUNT, str(max(0, min(10, _to_int(data.get("retry_count")) or 1))))
        AppSettingRepository.set_value(PublishSettingKeys.REQUIRE_APPROVAL, "1" if _to_bool(data.get("require_approval")) else "0")
        return self._write_json({"ok": True})
    def _read_json_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _write_json(self, payload: dict | list, status: int = 200) -> None:
        request_id = self._ensure_request_id()
        final_payload = payload
        if isinstance(payload, dict):
            final_payload = dict(payload)
            final_payload.setdefault("request_id", request_id)
        body = json.dumps(final_payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Request-Id", request_id)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return


def _safe_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]


def _safe_json_object(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _sanitize_writer_channel_policies(raw: dict | None) -> dict[str, dict]:
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, dict] = {}
    for key, value in raw.items():
        channel_id = _to_int(key)
        if channel_id is None or channel_id <= 0:
            continue
        if not isinstance(value, dict):
            continue
        persona_ids: list[int] = []
        seen_persona: set[int] = set()
        for raw_persona in (value.get("persona_ids") or []):
            pid = _to_int(raw_persona)
            if pid is None or pid <= 0 or pid in seen_persona:
                continue
            seen_persona.add(pid)
            persona_ids.append(pid)

        template_ids: list[int] = []
        seen_template: set[int] = set()
        for raw_template in (value.get("template_ids") or []):
            tid = _to_int(raw_template)
            if tid is None or tid <= 0 or tid in seen_template:
                continue
            seen_template.add(tid)
            template_ids.append(tid)
        cleaned[str(channel_id)] = {
            "persona_ids": persona_ids,
            "template_ids": template_ids,
            "persona_cursor": max(0, _to_int(value.get("persona_cursor")) or 0),
            "template_cursor": max(0, _to_int(value.get("template_cursor")) or 0),
            "default_ai_provider_id": _to_int(value.get("default_ai_provider_id")),
            "min_source_count": max(1, min(20, _to_int(value.get("min_source_count")) or 3)),
            "default_tone": str(value.get("default_tone") or "informative")[:50],
            "default_reader_level": str(value.get("default_reader_level") or "general")[:30],
            "default_length": str(value.get("default_length") or "medium")[:20],
            "creativity_level": max(1, min(5, _to_int(value.get("creativity_level")) or 3)),
            "factuality_level": max(1, min(5, _to_int(value.get("factuality_level")) or 4)),
            "seo_keywords": str(value.get("seo_keywords") or "").strip()[:500],
            "auto_enabled": _to_bool(value.get("auto_enabled")),
            "auto_interval_minutes": max(5, min(10080, _to_int(value.get("auto_interval_minutes")) or 1440)),
            "auto_batch_count": max(1, min(20, _to_int(value.get("auto_batch_count")) or 1)),
            "auto_retry_count": max(0, min(10, _to_int(value.get("auto_retry_count")) or 1)),
            "auto_time_window": str(value.get("auto_time_window") or "00:00-23:59")[:50],
        }
    return cleaned


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    text = str(value or "").strip().lower()
    return text in {"1", "true", "y", "yes", "on"}

def _dt_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        return None
    return value.isoformat(sep=" ", timespec="seconds")


_WEB_SHELL_SERVER: _WebShellServer | None = None


def get_web_shell_server() -> _WebShellServer:
    global _WEB_SHELL_SERVER
    if _WEB_SHELL_SERVER is None:
        _WEB_SHELL_SERVER = _WebShellServer()
        _WEB_SHELL_SERVER.start()
    return _WEB_SHELL_SERVER


class WebShellPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_section = "dashboard"
        self._current_node: str | None = None

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        if QWebEngineView is None:
            layout.addWidget(QLabel("QWebEngineView를 사용할 수 없습니다."))
            self.setLayout(layout)
            return

        self._view = QWebEngineView()
        self._load_section(self._current_section)
        layout.addWidget(self._view)
        self.setLayout(layout)

    def _load_section(self, section: str, node_id: str | None = None, force_asset_sync: bool = False) -> None:
        server = get_web_shell_server()
        if force_asset_sync:
            server._copy_assets()
        suffix = f"&node={node_id}" if node_id else ""
        self._view.setUrl(QUrl(f"{server.base_url}/index.html?section={section}{suffix}&embed=desktop"))

    def open_section(self, section: str, node_id: str | None = None) -> None:
        normalized = (section or "dashboard").strip().lower() or "dashboard"
        self._current_section = normalized
        self._current_node = (node_id or "").strip() or None
        if hasattr(self, "_view"):
            self._load_section(self._current_section, self._current_node)

    def refresh_all(self) -> None:
        if hasattr(self, "_view"):
            self._load_section(self._current_section, self._current_node, force_asset_sync=True)







































