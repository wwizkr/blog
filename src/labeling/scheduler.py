from __future__ import annotations

import time
from datetime import datetime
from threading import Event, Lock, Thread

from core.settings_keys import LabelSettingKeys
from labeling.service import labeling_service
from storage.repositories import AppSettingRepository


class LabelingAutoScheduler:
    def __init__(self) -> None:
        self._stop_event = Event()
        self._worker_lock = Lock()
        self._state_lock = Lock()
        self._thread = Thread(target=self._loop, name="labeling-auto-scheduler", daemon=True)
        self._running = False
        self._last_started_at: datetime | None = None
        self._last_finished_at: datetime | None = None
        self._next_run_at: datetime | None = None
        self._last_content_processed = 0
        self._last_image_processed = 0
        self._last_error = ""
        self._logs: list[str] = []

    def start(self) -> None:
        if self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._loop, name="labeling-auto-scheduler", daemon=True)
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

            if now < next_run_at:
                with self._state_lock:
                    self._next_run_at = datetime.now() + _seconds_to_delta(max(0.0, next_run_at - now))
                continue

            if not self._read_auto_enabled():
                next_run_at = now + interval_seconds
                with self._state_lock:
                    self._next_run_at = datetime.now() + _seconds_to_delta(interval_seconds)
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
                result = self.run_once()
                with self._state_lock:
                    self._last_content_processed = int(result.get("content_labeled") or 0)
                    self._last_image_processed = int(result.get("image_labeled") or 0)
            except Exception as exc:
                with self._state_lock:
                    self._last_error = str(exc)
                self._append_log(f"자동 라벨링 오류: {exc}")
            finally:
                self._worker_lock.release()
                with self._state_lock:
                    self._running = False
                    self._last_finished_at = datetime.now()
                next_run_at = time.monotonic() + interval_seconds
                with self._state_lock:
                    self._next_run_at = datetime.now() + _seconds_to_delta(interval_seconds)

    def run_once(self) -> dict:
        batch_size = self._read_batch_size()
        content_result = labeling_service.label_unlabeled_contents(limit=batch_size)
        image_result = labeling_service.label_unlabeled_images(limit=batch_size)
        content_labeled = int(content_result.get("labeled") or 0)
        image_labeled = int(image_result.get("labeled") or 0)
        self._append_log(f"자동 라벨링 실행: 텍스트 {content_labeled}건 / 이미지 {image_labeled}건")
        return {
            "content_labeled": content_labeled,
            "image_labeled": image_labeled,
            "batch_size": batch_size,
        }

    def status(self) -> dict:
        with self._state_lock:
            return {
                "worker_started": self._thread.is_alive(),
                "running": self._running,
                "auto_enabled": self._read_auto_enabled(),
                "interval_minutes": self._read_interval_minutes(),
                "batch_size": self._read_batch_size(),
                "next_run_at": _dt_to_iso(self._next_run_at),
                "last_started_at": _dt_to_iso(self._last_started_at),
                "last_finished_at": _dt_to_iso(self._last_finished_at),
                "last_content_processed": self._last_content_processed,
                "last_image_processed": self._last_image_processed,
                "last_error": self._last_error,
                "logs": list(self._logs[:80]),
            }

    def _append_log(self, message: str) -> None:
        stamp = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
        line = f"[{stamp}] {message}"
        with self._state_lock:
            self._logs.insert(0, line)
            self._logs = self._logs[:80]

    @staticmethod
    def _read_auto_enabled() -> bool:
        return _to_bool(AppSettingRepository.get_value(LabelSettingKeys.AUTO_ENABLED, "0"))

    @staticmethod
    def _read_interval_minutes() -> int:
        return _clamp_int(AppSettingRepository.get_value(LabelSettingKeys.INTERVAL_MINUTES, "15"), 15, 5, 1440)

    @staticmethod
    def _read_batch_size() -> int:
        return _clamp_int(AppSettingRepository.get_value(LabelSettingKeys.BATCH_SIZE, "300"), 300, 10, 1000)


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


def _seconds_to_delta(seconds: float):
    from datetime import timedelta
    return timedelta(seconds=max(0.0, float(seconds)))


def _dt_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(sep=" ", timespec="seconds")


labeling_auto_scheduler = LabelingAutoScheduler()
