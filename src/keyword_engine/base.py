from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class KeywordCandidate:
    keyword: str
    source_type: str
    score: float | None = None
    source_detail: str | None = None


class KeywordSourceProvider(Protocol):
    code: str

    def fetch(self, keyword: str, limit: int) -> list[KeywordCandidate]:
        ...
