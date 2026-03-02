from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path

from collector.base import BaseCollector


class CollectorManager:
    def __init__(self):
        self._collectors: dict[str, BaseCollector] = {}
        self._load_collectors()

    def _load_collectors(self) -> None:
        package_path = Path(__file__).resolve().parent
        package_name = "collector"

        for module_info in pkgutil.iter_modules([str(package_path)]):
            if module_info.name in {"base", "manager", "service", "scheduler", "__init__"}:
                continue
            module = importlib.import_module(f"{package_name}.{module_info.name}")
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if not issubclass(cls, BaseCollector) or cls is BaseCollector:
                    continue
                channel_code = getattr(cls, "channel_code", None)
                display_name = getattr(cls, "display_name", None)
                if not channel_code or not display_name:
                    continue
                instance = cls()
                self._collectors[channel_code] = instance

    def collect(self, channel_code: str, keyword: str, limit: int = 5) -> list[dict]:
        collector = self._collectors.get(channel_code)
        if not collector:
            raise ValueError(f"Unsupported channel: {channel_code}")
        return collector.collect(keyword=keyword, limit=limit)

    def list_channels(self) -> list[tuple[str, str]]:
        channels: list[tuple[str, str]] = []
        for _, collector in sorted(self._collectors.items(), key=lambda x: x[0]):
            channels.append(collector.get_channel_info())
        return channels


collector_manager = CollectorManager()



