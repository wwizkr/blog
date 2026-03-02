from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from storage.repositories import (
    ArticleRepository,
    ArticleTemplateRepository,
    PersonaRepository,
)
from ui.web_editor import MubloWebEditor
from writer import writer_service


class WriterPage(QWidget):
    def __init__(self):
        super().__init__()
        self.current_article_id: int | None = None
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("글 생성 / 에디터")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        top_box = QGroupBox("초안 생성 (페르소나 + 템플릿)")
        top_layout = QHBoxLayout()

        self.persona_combo = QComboBox()

        self.template_type_combo = QComboBox()
        self.template_type_combo.addItem("블로그형", "blog")
        self.template_type_combo.addItem("SNS형", "sns")
        self.template_type_combo.addItem("게시판형", "board")
        self.template_type_combo.currentIndexChanged.connect(self.refresh_templates)

        self.template_combo = QComboBox()

        generate_btn = QPushButton("초안 생성")
        generate_btn.clicked.connect(self.generate_draft)
        save_btn = QPushButton("현재 글 저장")
        save_btn.clicked.connect(self.save_current_article)

        top_layout.addWidget(QLabel("페르소나"))
        top_layout.addWidget(self.persona_combo)
        top_layout.addWidget(QLabel("템플릿 유형"))
        top_layout.addWidget(self.template_type_combo)
        top_layout.addWidget(QLabel("템플릿"))
        top_layout.addWidget(self.template_combo, 1)
        top_layout.addWidget(generate_btn)
        top_layout.addWidget(save_btn)
        top_box.setLayout(top_layout)
        root.addWidget(top_box)

        splitter = QSplitter()
        left = QGroupBox("최근 생성 글")
        left_layout = QVBoxLayout()
        self.article_table = QTableWidget(0, 4)
        self.article_table.setHorizontalHeaderLabels(["ID", "형식", "상태", "제목"])
        self.article_table.verticalHeader().setVisible(False)
        self.article_table.setColumnWidth(0, 60)
        self.article_table.setColumnWidth(1, 80)
        self.article_table.setColumnWidth(2, 80)
        self.article_table.horizontalHeader().setStretchLastSection(True)
        self.article_table.itemSelectionChanged.connect(self.load_selected_article)
        left_layout.addWidget(self.article_table)
        left.setLayout(left_layout)

        right = QGroupBox("에디터")
        right_layout = QVBoxLayout()
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("제목")
        self.editor = MubloWebEditor()
        right_layout.addWidget(QLabel("제목"))
        right_layout.addWidget(self.title_input)
        right_layout.addWidget(QLabel("본문"))
        right_layout.addWidget(self.editor, 1)
        right.setLayout(right_layout)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([450, 950])
        root.addWidget(splitter, 1)

        self.setLayout(root)

    def refresh_all(self) -> None:
        self.refresh_personas()
        self.refresh_templates()
        self.refresh_articles()

    def refresh_personas(self) -> None:
        selected = self.persona_combo.currentData()
        self.persona_combo.clear()
        rows = PersonaRepository.list_all(active_only=True)
        for item in rows:
            label = item.name if not item.tone else f"{item.name} ({item.tone})"
            self.persona_combo.addItem(label, item.id)
        if selected is not None:
            idx = self.persona_combo.findData(selected)
            if idx >= 0:
                self.persona_combo.setCurrentIndex(idx)

    def refresh_templates(self) -> None:
        selected = self.template_combo.currentData()
        template_type = self.template_type_combo.currentData()
        self.template_combo.clear()
        rows = ArticleTemplateRepository.list_all(template_type=template_type, active_only=True)
        for item in rows:
            self.template_combo.addItem(f"{item.name} (v{item.version})", item.id)
        if selected is not None:
            idx = self.template_combo.findData(selected)
            if idx >= 0:
                self.template_combo.setCurrentIndex(idx)

    def refresh_articles(self) -> None:
        rows = ArticleRepository.list_recent(100)
        self.article_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            self.article_table.setItem(row, 0, QTableWidgetItem(str(item.id)))
            self.article_table.setItem(row, 1, QTableWidgetItem(item.format_type))
            self.article_table.setItem(row, 2, QTableWidgetItem(item.status))
            self.article_table.setItem(row, 3, QTableWidgetItem(item.title))

    def generate_draft(self) -> None:
        persona_id = self.persona_combo.currentData()
        template_id = self.template_combo.currentData()
        if persona_id is None:
            QMessageBox.warning(self, "입력 필요", "활성 페르소나를 먼저 등록/선택하세요.")
            return
        if template_id is None:
            QMessageBox.warning(self, "입력 필요", "활성 템플릿을 먼저 등록/선택하세요.")
            return
        try:
            result = writer_service.generate_draft(persona_id=int(persona_id), template_id=int(template_id))
            self.current_article_id = result["id"]
            self.title_input.setText(result["title"])
            self.editor.set_html(result["content"])
            self.refresh_articles()
        except Exception as exc:
            QMessageBox.warning(self, "생성 실패", str(exc))

    def _selected_article_id(self) -> int | None:
        row = self.article_table.currentRow()
        if row < 0:
            return None
        item = self.article_table.item(row, 0)
        if not item:
            return None
        return int(item.text())

    def load_selected_article(self) -> None:
        article_id = self._selected_article_id()
        if article_id is None:
            return
        row = ArticleRepository.get_by_id(article_id)
        if not row:
            return
        self.current_article_id = article_id
        self.title_input.setText(row.title)
        self.editor.set_html(row.content)

    def save_current_article(self) -> None:
        if self.current_article_id is None:
            QMessageBox.information(self, "알림", "저장할 글을 먼저 선택하거나 생성하세요.")
            return

        def _save(html: str) -> None:
            ArticleRepository.update_content(
                article_id=self.current_article_id,
                title=self.title_input.text().strip(),
                content=html,
            )
            self.refresh_articles()
            QMessageBox.information(self, "저장 완료", "글이 저장되었습니다.")

        self.editor.get_html(_save)

