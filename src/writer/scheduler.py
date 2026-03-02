from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from threading import Event, Lock, Thread

from core.settings_keys import WriterSettingKeys
from storage.repositories import AppSettingRepository, WritingChannelRepository
from writer.service import writer_service


class WriterAutoScheduler:
    def __init__(self) -> None:
        self._stop_event = Event()
        self._worker_lock = Lock()
        self._state_lock = Lock()
        self._thread = Thread(target=self._loop, name="writer-auto-scheduler", daemon=True)
        self._running = False
        self._last_tick_at: datetime | None = None
        self._last_tick_processed = 0
        self._last_error = ""
        self._last_run_by_channel: dict[int, datetime] = {}
        self._logs: list[str] = []

    def start(self) -> None:
        if self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._loop, name="writer-auto-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=3.0)
        with self._state_lock:
            self._running = False

    def _loop(self) -> None:
        while not self._stop_event.wait(5.0):
            if not self._worker_lock.acquire(blocking=False):
                continue
            try:
                with self._state_lock:
                    self._running = True
                    self._last_error = ""
                processed = self.run_once()
                with self._state_lock:
                    self._last_tick_at = datetime.utcnow()
                    self._last_tick_processed = processed
            except Exception as exc:
                with self._state_lock:
                    self._last_error = str(exc)
                self._append_log(f"자동 작성 워커 오류: {exc}")
            finally:
                with self._state_lock:
                    self._running = False
                self._worker_lock.release()

    def status(self) -> dict:
        channels = WritingChannelRepository.list_all(enabled_only=True)
        policies = _load_channel_policies()
        now = datetime.utcnow()
        rows: list[dict] = []
        auto_count = 0
        for ch in channels:
            p = policies.get(str(ch.id), {})
            auto_enabled = _to_bool(p.get("auto_enabled"))
            if auto_enabled:
                auto_count += 1
            interval = max(5, min(10080, _to_int(p.get("auto_interval_minutes")) or 1440))
            last = self._last_run_by_channel.get(int(ch.id))
            next_run = (last + timedelta(minutes=interval)) if last else now
            rows.append(
                {
                    "channel_id": ch.id,
                    "channel_code": ch.code,
                    "channel_name": ch.display_name,
                    "auto_enabled": auto_enabled,
                    "interval_minutes": interval,
                    "time_window": str(p.get("auto_time_window") or "00:00-23:59"),
                    "next_run_at": _dt_to_iso(next_run),
                }
            )
        with self._state_lock:
            return {
                "worker_started": self._thread.is_alive(),
                "running": self._running,
                "auto_channel_count": auto_count,
                "last_tick_at": _dt_to_iso(self._last_tick_at),
                "last_tick_processed": self._last_tick_processed,
                "last_error": self._last_error,
                "channels": rows,
                "logs": list(self._logs[:80]),
            }

    def run_once(self) -> int:
        channels = WritingChannelRepository.list_all(enabled_only=True)
        if not channels:
            return 0
        policies = _load_channel_policies()
        if not policies:
            return 0
        now = datetime.utcnow()
        now_hm = now.strftime("%H:%M")
        processed = 0
        touched_policy = False

        for ch in channels:
            key = str(ch.id)
            policy = dict(policies.get(key) or {})
            if not _to_bool(policy.get("auto_enabled")):
                continue

            window = str(policy.get("auto_time_window") or "00:00-23:59")
            if not _is_time_in_window(now_hm, window):
                self._append_log(f"[{ch.code}] 자동 작성 대기: 시간대 외 ({window})")
                continue

            interval = max(5, min(10080, _to_int(policy.get("auto_interval_minutes")) or 1440))
            last = self._last_run_by_channel.get(int(ch.id))
            if last and (now - last).total_seconds() < interval * 60:
                continue

            persona_ids = [n for n in (_to_int(v) for v in (policy.get("persona_ids") or [])) if n]
            template_ids = [n for n in (_to_int(v) for v in (policy.get("template_ids") or [])) if n]
            if not persona_ids or not template_ids:
                self._append_log(f"[{ch.code}] 자동 작성 스킵: 페르소나/템플릿 정책 없음")
                self._last_run_by_channel[int(ch.id)] = now
                continue

            batch_count = max(1, min(20, _to_int(policy.get("auto_batch_count")) or 1))
            source_limit = max(1, min(20, _to_int(policy.get("min_source_count")) or 3))
            retry_count = max(0, min(10, _to_int(policy.get("auto_retry_count")) or 1))
            ai_provider_id = _to_int(policy.get("default_ai_provider_id"))
            persona_cursor = max(0, _to_int(policy.get("persona_cursor")) or 0)
            template_cursor = max(0, _to_int(policy.get("template_cursor")) or 0)

            for run_no in range(1, batch_count + 1):
                persona_id = persona_ids[persona_cursor % len(persona_ids)]
                template_id = template_ids[template_cursor % len(template_ids)]
                persona_cursor += 1
                template_cursor += 1

                attempt = 0
                success = False
                while attempt <= retry_count and not success:
                    attempt += 1
                    try:
                        result = writer_service.generate_draft(
                            persona_id=persona_id,
                            template_id=template_id,
                            source_limit=source_limit,
                            writing_channel_id=int(ch.id),
                            ai_provider_id=ai_provider_id,
                        )
                        processed += 1
                        success = True
                        self._append_log(f"[{ch.code}] 자동 작성 성공 {run_no}/{batch_count} article_id={result.get('id')}")
                    except Exception as exc:
                        if attempt > retry_count:
                            self._append_log(f"[{ch.code}] 자동 작성 실패 {run_no}/{batch_count}: {exc}")
                        else:
                            self._append_log(f"[{ch.code}] 자동 작성 재시도 {run_no}/{batch_count} ({attempt}/{retry_count})")

            policy["persona_cursor"] = persona_cursor
            policy["template_cursor"] = template_cursor
            policies[key] = policy
            touched_policy = True
            self._last_run_by_channel[int(ch.id)] = now

        if touched_policy:
            AppSettingRepository.set_value(WriterSettingKeys.CHANNEL_POLICIES, json.dumps(policies, ensure_ascii=False))
        return processed

    def _append_log(self, message: str) -> None:
        stamp = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        line = f"[{stamp}] {message}"
        with self._state_lock:
            self._logs.insert(0, line)
            self._logs = self._logs[:80]


def _load_channel_policies() -> dict[str, dict]:
    raw = AppSettingRepository.get_value(WriterSettingKeys.CHANNEL_POLICIES, "{}")
    try:
        data = json.loads(raw or "{}")
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    cleaned: dict[str, dict] = {}
    for k, v in data.items():
        if _to_int(k) is None or not isinstance(v, dict):
            continue
        cleaned[str(_to_int(k))] = dict(v)
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


def _is_time_in_window(now_hm: str, window: str) -> bool:
    text = str(window or "").strip()
    if "-" not in text:
        return True
    start, end = [s.strip() for s in text.split("-", 1)]
    if len(start) != 5 or len(end) != 5:
        return True
    if start <= end:
        return start <= now_hm <= end
    # overnight window: 22:00-06:00
    return now_hm >= start or now_hm <= end


def _dt_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(sep=" ", timespec="seconds")


writer_auto_scheduler = WriterAutoScheduler()
