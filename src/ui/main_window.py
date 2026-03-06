from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ui.web_shell import WebShellPage
from core.menu import get_v2_menu_tree


NODE_TO_SECTION = {
    "dashboard": "dashboard",
    "dashboard.overview": "dashboard",
    "dashboard.stages": "dashboard",

    "keyword": "keyword",
    "collect.run": "collection",
    "collect.settings": "collect_settings",
    "collect.jobs": "collection",
    "collect.contents": "collected_data",
    "label.run": "labeling",
    "label.settings": "label_settings",
    "label.results": "labeling",
    "writer.run": "writer_run",
    "writer.channels": "writer_settings",
    "writer.settings": "writer_settings",
    "writer.persona": "persona",
    "writer.template": "template",
    "writer.ai": "ai_provider",
    "writer.editor": "writer_result",
    "publish.run": "publisher",
    "publish.settings": "publish_settings",
    "publish.history": "publisher",
    "monitor.logs": "monitor",
    "monitor.failures": "monitor",
    "monitor.retry": "monitor",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BlogWriter")
        self._group_bodies: dict[str, QWidget] = {}
        self._init_size()
        self._build_ui()
        self._open_node("dashboard")

    def _init_size(self) -> None:
        screen = self.screen()
        if not screen and self.windowHandle():
            screen = self.windowHandle().screen()
        if not screen:
            self.resize(1440, 900)
            return
        geo = screen.availableGeometry()
        width = int(geo.width() * 0.9)
        height = int(geo.height() * 0.9)
        self.resize(width, height)
        self.move(geo.x() + (geo.width() - width) // 2, geo.y() + (geo.height() - height) // 2)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = self._build_sidebar()
        root.addWidget(sidebar)

        self.web_shell_page = WebShellPage()
        root.addWidget(self.web_shell_page, 1)

        central.setLayout(root)
        self.setCentralWidget(central)

        status = QStatusBar()
        status.showMessage("준비됨")
        self.setStatusBar(status)

    def _build_sidebar(self) -> QWidget:
        frame = QFrame()
        frame.setFixedWidth(260)
        frame.setStyleSheet("background-color: #111827; color: #f9fafb;")

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(8)

        title = QLabel("BlogWriter")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #f9fafb;")
        layout.addWidget(title)

        subtitle = QLabel("Accordion Menu")
        subtitle.setStyleSheet("font-size: 11px; color: #93a3b8;")
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        menu_root = QWidget()
        menu_layout = QVBoxLayout()
        menu_layout.setContentsMargins(0, 6, 0, 0)
        menu_layout.setSpacing(8)

        for primary in get_v2_menu_tree():
            primary_id = str(primary.get("id") or "")
            primary_label = str(primary.get("label") or primary_id)
            children = primary.get("children") or []

            group = QFrame()
            group.setStyleSheet("QFrame { background-color: #1f2937; border: 1px solid #374151; border-radius: 8px; }")
            group_layout = QVBoxLayout()
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(0)

            head = QPushButton(primary_label)
            head.setMinimumHeight(36)
            head.setCursor(Qt.PointingHandCursor)
            head.setAttribute(Qt.WA_Hover, True)
            head.setStyleSheet(
                """
                QPushButton {
                    background-color: transparent;
                    border: 0;
                    border-bottom: 1px solid #374151;
                    text-align: left;
                    padding-left: 12px;
                    color: #e5eefc;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #435b79;
                    color: #ffffff;
                    border-bottom: 1px solid #9db7d8;
                }
                QPushButton:pressed { background-color: #2f435b; }
                """
            )
            if children:
                head.clicked.connect(partial(self._toggle_group, primary_id))
            else:
                head.clicked.connect(partial(self._open_node, primary_id))
            group_layout.addWidget(head)

            if children:
                body = QWidget()
                body_layout = QVBoxLayout()
                body_layout.setContentsMargins(8, 8, 8, 8)
                body_layout.setSpacing(6)

                for child in children:
                    node_id = str(child.get("id") or "")
                    label = str(child.get("label") or node_id)
                    btn = QPushButton(label)
                    btn.setMinimumHeight(32)
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.setAttribute(Qt.WA_Hover, True)
                    btn.setStyleSheet(
                        """
                        QPushButton {
                            background-color: #334155;
                            border: 1px solid #475569;
                            border-radius: 6px;
                            text-align: left;
                            padding-left: 10px;
                            color: #f8fafc;
                        }
                        QPushButton:hover {
                            background-color: #5b789b;
                            border: 1px solid #b3cae6;
                            color: #ffffff;
                        }
                        QPushButton:pressed { background-color: #405774; }
                        """
                    )
                    btn.clicked.connect(partial(self._open_node, node_id))
                    body_layout.addWidget(btn)

                body.setLayout(body_layout)
                body.setVisible(False)
                self._group_bodies[primary_id] = body
                group_layout.addWidget(body)

            group.setLayout(group_layout)
            menu_layout.addWidget(group)

        menu_layout.addStretch(1)
        menu_root.setLayout(menu_layout)
        scroll.setWidget(menu_root)
        layout.addWidget(scroll, 1)

        frame.setLayout(layout)
        return frame

    def _toggle_group(self, group_id: str) -> None:
        target = self._group_bodies.get(group_id)
        if target is None:
            return
        should_open = not target.isVisible()
        for body in self._group_bodies.values():
            body.setVisible(False)
        if should_open:
            target.setVisible(True)

    def _open_node(self, node_id: str) -> None:
        section = NODE_TO_SECTION.get(node_id, "dashboard")
        self._open_section(section=section, node_id=node_id)
        primary = (node_id or "").split(".")[0]
        if primary:
            for pid, body in self._group_bodies.items():
                body.setVisible(pid == primary)
    def _open_section(self, section: str, node_id: str | None = None) -> None:
        self.web_shell_page.open_section(section, node_id=node_id)






