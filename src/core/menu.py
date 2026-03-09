from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class MenuNode:
    id: str
    label: str
    children: tuple["MenuNode", ...] = field(default_factory=tuple)

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0


def _node(id: str, label: str, children: Iterable[MenuNode] | None = None) -> MenuNode:
    return MenuNode(id=id, label=label, children=tuple(children or ()))


def build_primary_menu() -> tuple[MenuNode, ...]:
    return (
        _node("dashboard", "대시보드"),
        _node("keyword", "키워드 관리"),
        _node("collect", "수집", (_node("collect.settings", "수집 설정"), _node("collect.run", "수집 실행"), _node("collect.jobs", "작업 이력"), _node("collect.contents", "수집 데이터"))),
        _node("label", "라벨링", (_node("label.settings", "라벨링 설정"), _node("label.run", "라벨링 실행"), _node("label.results", "라벨링 결과"))),
        _node(
            "writer",
            "글 작성",
            (
                _node("writer.channels", "작성 채널관리"),
                _node("writer.settings", "글 작성 설정"),
                _node("writer.run", "글 작성 실행"),
                _node("writer.persona", "페르소나 관리"),
                _node("writer.template", "템플릿 관리"),
                _node("writer.ai", "AI 설정"),
                _node("writer.editor", "작성 결과/에디터"),
            ),
        ),
        _node("publish", "발행", (_node("publish.settings", "발행 설정"), _node("publish.run", "발행 실행"), _node("publish.history", "발행 이력"))),
        _node("monitor", "로그/모니터링", (_node("monitor.logs", "실행 로그"), _node("monitor.failures", "실패 로그"), _node("monitor.retry", "재시도 큐"))),
    )


def default_entry_node_id() -> str:
    return "dashboard"


def get_v2_menu_tree() -> tuple[dict, ...]:
    return tuple(_to_dict(node) for node in build_primary_menu())


def get_v2_default_entry() -> str:
    return default_entry_node_id()


def _to_dict(node: MenuNode) -> dict:
    return {
        "id": node.id,
        "label": node.label,
        "children": [_to_dict(child) for child in node.children],
    }

