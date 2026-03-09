from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from storage.repositories import ArticleTemplateRepository


class TemplatePage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("템플릿 관리")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        box = QGroupBox("글 발행 템플릿")
        layout = QVBoxLayout()

        self.template_table = QTableWidget(0, 6)
        self.template_table.setHorizontalHeaderLabels(["ID", "이름", "유형", "버전", "활성", "프롬프트"])
        self.template_table.verticalHeader().setVisible(False)
        self.template_table.setColumnWidth(0, 60)
        self.template_table.setColumnWidth(1, 180)
        self.template_table.setColumnWidth(2, 90)
        self.template_table.setColumnWidth(3, 70)
        self.template_table.setColumnWidth(4, 70)
        self.template_table.horizontalHeader().setStretchLastSection(True)
        self.template_table.itemSelectionChanged.connect(self._fill_template_form)
        layout.addWidget(self.template_table)

        row1 = QHBoxLayout()
        self.template_name = QLineEdit()
        self.template_name.setPlaceholderText("템플릿 이름")
        self.template_type = QComboBox()
        self.template_type.addItem("블로그형", "blog")
        self.template_type.addItem("SNS형", "sns")
        self.template_type.addItem("게시판형", "board")
        self.template_version = QSpinBox()
        self.template_version.setRange(1, 999)
        self.template_version.setValue(1)
        self.template_active = QCheckBox("활성")
        self.template_active.setChecked(True)
        row1.addWidget(QLabel("이름"))
        row1.addWidget(self.template_name, 1)
        row1.addWidget(QLabel("유형"))
        row1.addWidget(self.template_type)
        row1.addWidget(QLabel("버전"))
        row1.addWidget(self.template_version)
        row1.addWidget(self.template_active)
        layout.addLayout(row1)

        self.template_prompt = QTextEdit()
        self.template_prompt.setPlaceholderText(
            "예시:\n# {{keyword}} 글 초안\n\n페르소나: {{persona_name}}\n연령: {{persona_age_group}}\n성별: {{persona_gender}}\n성격: {{persona_personality}}\n말투: {{persona_speech_style}}\n\nSEO 전략:\n{{seo_strategy}}\n\nSEO 정량 가이드:\n{{seo_metrics}}\n\n원문 개요:\n{{source_outline}}\n\n이미지 계획:\n{{image_plan}}\n\n이미지 슬롯:\n{{image_slots}}"
        )
        layout.addWidget(QLabel("사용자 프롬프트 템플릿"))
        layout.addWidget(self.template_prompt, 1)

        self.template_schema = QLineEdit()
        self.template_schema.setPlaceholderText("출력 형식 메모(선택)")
        layout.addWidget(self.template_schema)

        actions = QHBoxLayout()
        add_btn = QPushButton("추가")
        add_btn.clicked.connect(self.add_template)
        save_btn = QPushButton("수정 저장")
        save_btn.clicked.connect(self.update_template)
        delete_btn = QPushButton("삭제")
        delete_btn.clicked.connect(self.delete_template)
        actions.addWidget(add_btn)
        actions.addWidget(save_btn)
        actions.addWidget(delete_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        box.setLayout(layout)
        root.addWidget(box, 1)
        self.setLayout(root)

    def refresh_all(self) -> None:
        rows = ArticleTemplateRepository.list_all()
        self.template_table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            self.template_table.setItem(r, 0, QTableWidgetItem(str(item.id)))
            self.template_table.setItem(r, 1, QTableWidgetItem(item.name))
            self.template_table.setItem(r, 2, QTableWidgetItem(item.template_type))
            self.template_table.setItem(r, 3, QTableWidgetItem(str(item.version)))
            self.template_table.setItem(r, 4, QTableWidgetItem("Y" if item.is_active else "N"))
            self.template_table.setItem(r, 5, QTableWidgetItem(item.user_prompt))

    def _selected_template_id(self) -> int | None:
        row = self.template_table.currentRow()
        if row < 0:
            return None
        item = self.template_table.item(row, 0)
        return int(item.text()) if item else None

    def _fill_template_form(self) -> None:
        template_id = self._selected_template_id()
        if template_id is None:
            return
        row = ArticleTemplateRepository.get_by_id(template_id)
        if not row:
            return
        self.template_name.setText(row.name)
        idx = self.template_type.findData(row.template_type)
        if idx >= 0:
            self.template_type.setCurrentIndex(idx)
        self.template_version.setValue(max(1, row.version))
        self.template_active.setChecked(row.is_active)
        self.template_prompt.setPlainText(row.user_prompt)
        self.template_schema.setText(row.output_schema or "")

    def add_template(self) -> None:
        ok = ArticleTemplateRepository.add(
            name=self.template_name.text(),
            template_type=self.template_type.currentData(),
            user_prompt=self.template_prompt.toPlainText(),
            output_schema=self.template_schema.text(),
        )
        if not ok:
            QMessageBox.warning(self, "실패", "템플릿 추가에 실패했습니다. (이름/유형 중복 또는 빈 값)")
            return
        self.refresh_all()

    def update_template(self) -> None:
        template_id = self._selected_template_id()
        if template_id is None:
            QMessageBox.information(self, "알림", "수정할 템플릿을 먼저 선택하세요.")
            return
        ok = ArticleTemplateRepository.update(
            template_id=template_id,
            name=self.template_name.text(),
            template_type=self.template_type.currentData(),
            user_prompt=self.template_prompt.toPlainText(),
            system_prompt=None,
            output_schema=self.template_schema.text(),
            is_active=self.template_active.isChecked(),
            version=self.template_version.value(),
        )
        if not ok:
            QMessageBox.warning(self, "실패", "템플릿 수정에 실패했습니다.")
            return
        self.refresh_all()

    def delete_template(self) -> None:
        template_id = self._selected_template_id()
        if template_id is None:
            QMessageBox.information(self, "알림", "삭제할 템플릿을 먼저 선택하세요.")
            return
        ArticleTemplateRepository.delete(template_id)
        self.refresh_all()

