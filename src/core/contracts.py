"""Stage execution contracts for independent pipeline steps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class StageRunRequest:
    stage: str
    trigger: str
    requested_by: str | None = None


@dataclass(frozen=True)
class StageRunResult:
    stage: str
    started_at: datetime
    finished_at: datetime
    success: bool
    processed_count: int
    message: str


class CollectStage(Protocol):
    def run(self, request: StageRunRequest) -> StageRunResult:
        ...


class LabelStage(Protocol):
    def run(self, request: StageRunRequest) -> StageRunResult:
        ...


class WriterStage(Protocol):
    def run(self, request: StageRunRequest) -> StageRunResult:
        ...


class PublishStage(Protocol):
    def run(self, request: StageRunRequest) -> StageRunResult:
        ...

