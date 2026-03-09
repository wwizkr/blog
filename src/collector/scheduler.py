from __future__ import annotations

import json
import time
from datetime import datetime
from threading import Event, Lock, Thread

from collector.service import crawl_service
from core.settings_keys import CollectSettingKeys
from keyword_engine.service import keyword_engine_service
from storage.repositories import AppSettingRepository, KeywordRepository


class CollectScheduler:
    def __init__(self) -> None:
        self._stop_event = Event()
        self._worker_lock = Lock()
        self._state_lock = Lock()
        self._thread = Thread(target=self._loop, name="collect-scheduler", daemon=True)
        self._running = False
        self._last_started_at: datetime | None = None
        self._last_finished_at: datetime | None = None
        self._next_run_at: datetime | None = None
        self._last_message_count = 0
        self._last_error = ""

    def start(self) -> None:
        if self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._loop, name="collect-scheduler", daemon=True)
        self._thread.start()
        with self._state_lock:
            self._last_error = ""

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=3.0)
        with self._state_lock:
            self._running = False
            self._next_run_at = None

    def _loop(self) -> None:
        next_run_at: float | None = None
        while not self._stop_event.wait(2.0):
            interval_seconds = self._read_interval_minutes() * 60
            now = time.monotonic()

            if next_run_at is None:
                next_run_at = now + interval_seconds
                with self._state_lock:
                    self._next_run_at = datetime.now() + _seconds_to_delta(interval_seconds)
                continue

            if next_run_at - now > interval_seconds:
                next_run_at = now + interval_seconds

            if now < next_run_at:
                with self._state_lock:
                    self._next_run_at = datetime.now() + _seconds_to_delta(max(0.0, next_run_at - now))
                continue

            if not self._worker_lock.acquire(blocking=False):
                next_run_at = now + interval_seconds
                with self._state_lock:
                    self._next_run_at = datetime.now() + _seconds_to_delta(interval_seconds)
                continue

            try:
                with self._state_lock:
                    self._running = True
                    self._last_started_at = datetime.now()
                    self._last_error = ""
                messages = self.run_once()
                with self._state_lock:
                    self._last_message_count = len(messages)
                if messages:
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{ts}] [collect-scheduler] {len(messages)} messages")
            except Exception as exc:
                with self._state_lock:
                    self._last_error = str(exc)
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{ts}] [collect-scheduler] error: {exc}")
            finally:
                self._worker_lock.release()
                with self._state_lock:
                    self._running = False
                    self._last_finished_at = datetime.now()
                next_run_at = time.monotonic() + interval_seconds
                with self._state_lock:
                    self._next_run_at = datetime.now() + _seconds_to_delta(interval_seconds)

    def run_once(self) -> list[str]:
        scope = str(AppSettingRepository.get_value(CollectSettingKeys.KEYWORD_SCOPE, "selected") or "selected").strip().lower()
        if scope not in {"all", "selected", "related"}:
            scope = "selected"

        max_results = _clamp_int(AppSettingRepository.get_value(CollectSettingKeys.MAX_RESULTS, "3"), 3, 1, 20)
        related_source_codes = keyword_engine_service.get_enabled_source_codes()
        auto_related_sync = _to_bool(AppSettingRepository.get_value(CollectSettingKeys.AUTO_RELATED_SYNC, "0"))
        sync_related = auto_related_sync and bool(related_source_codes)

        selected_channel_codes = _safe_json_list(AppSettingRepository.get_value(CollectSettingKeys.SELECTED_CHANNEL_CODES, "[]"))
        selected_category_ids = {
            n for n in (_to_int(v) for v in _safe_json_list(AppSettingRepository.get_value(CollectSettingKeys.SELECTED_CATEGORY_IDS, "[]")))
            if n is not None
        }

        all_active_keywords = {k.id: k for k in KeywordRepository.list_all() if k.is_active}
        root_keywords = [k for k in all_active_keywords.values() if not k.is_auto_generated]

        target_ids: list[int] = []
        if scope == "all":
            target_ids = self._expand_with_active_related([k.id for k in root_keywords], all_active_keywords)
        elif scope == "related":
            base_ids = [k.id for k in root_keywords if (k.category_id or 0) in selected_category_ids]
            if not base_ids:
                return ["자동수집 생략: 키워드 확장 모드에 체크된 카테고리가 없습니다."]
            target_ids = self._expand_with_active_related(base_ids, all_active_keywords)
        else:
            if not selected_category_ids:
                return ["자동수집 생략: 체크된 내역 모드에 체크된 카테고리가 없습니다."]
            base_ids = [k.id for k in root_keywords if (k.category_id or 0) in selected_category_ids]
            target_ids = self._expand_with_active_related(base_ids, all_active_keywords)

        if not target_ids:
            return ["자동수집 생략: 실행 대상 키워드가 없습니다."]

        messages: list[str] = []
        total = len(target_ids)
        for idx, keyword_id in enumerate(target_ids, 1):
            messages.append(f"[auto {idx}/{total}] 키워드 실행 시작")
            messages.extend(
                crawl_service.run_for_keyword(
                    keyword_id=keyword_id,
                    max_results=max_results,
                    sync_related=sync_related,
                    related_source_codes=related_source_codes,
                    allowed_channels=(selected_channel_codes or None) if scope != "all" else None,
                )
            )
        return messages

    @staticmethod
    def _expand_with_active_related(base_ids: list[int], all_active_keywords: dict[int, object]) -> list[int]:
        ordered: list[int] = []
        seen: set[int] = set()
        for base_id in base_ids:
            if base_id in all_active_keywords and base_id not in seen:
                seen.add(base_id)
                ordered.append(base_id)
            for rel in KeywordRepository.list_related_keywords(base_id):
                rid = int(rel.related_keyword_id)
                if rid in all_active_keywords and rid not in seen:
                    seen.add(rid)
                    ordered.append(rid)
        return ordered

    @staticmethod
    def _read_interval_minutes() -> int:
        return _clamp_int(AppSettingRepository.get_value(CollectSettingKeys.INTERVAL_MINUTES, "60"), 60, 5, 1440)

    def status(self) -> dict:
        with self._state_lock:
            return {
                "worker_started": self._thread.is_alive(),
                "running": self._running,
                "interval_minutes": self._read_interval_minutes(),
                "next_run_at": self._next_run_at.isoformat(sep=" ", timespec="seconds") if self._next_run_at else None,
                "last_started_at": self._last_started_at.isoformat(sep=" ", timespec="seconds") if self._last_started_at else None,
                "last_finished_at": self._last_finished_at.isoformat(sep=" ", timespec="seconds") if self._last_finished_at else None,
                "last_message_count": self._last_message_count,
                "last_error": self._last_error,
            }


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


def _clamp_int(value, default: int, lower: int, upper: int) -> int:
    n = _to_int(value)
    if n is None:
        n = default
    return max(lower, min(upper, n))


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


def _seconds_to_delta(seconds: float):
    # local helper to avoid importing timedelta for a single use
    from datetime import timedelta
    return timedelta(seconds=max(0.0, float(seconds)))


collect_scheduler = CollectScheduler()
