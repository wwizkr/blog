from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from storage.repositories import PersonaRepository


class PersonaPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("페르소나 관리")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        box = QGroupBox("상세 페르소나")
        layout = QVBoxLayout()

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["ID", "이름", "연령", "성별", "성격", "말투", "활성"])
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 180)
        self.table.setColumnWidth(5, 160)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._fill_form)
        layout.addWidget(self.table)

        row1 = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("이름")
        self.age_input = QLineEdit()
        self.age_input.setPlaceholderText("연령대 (예: 30대)")
        self.gender_input = QLineEdit()
        self.gender_input.setPlaceholderText("성별")
        self.personality_input = QLineEdit()
        self.personality_input.setPlaceholderText("성격")
        row1.addWidget(QLabel("이름"))
        row1.addWidget(self.name_input)
        row1.addWidget(QLabel("연령"))
        row1.addWidget(self.age_input)
        row1.addWidget(QLabel("성별"))
        row1.addWidget(self.gender_input)
        row1.addWidget(QLabel("성격"))
        row1.addWidget(self.personality_input)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.interests_input = QLineEdit()
        self.interests_input.setPlaceholderText("주요 관심사 (쉼표 구분)")
        self.speech_style_input = QLineEdit()
        self.speech_style_input.setPlaceholderText("말투")
        self.tone_input = QLineEdit()
        self.tone_input.setPlaceholderText("톤")
        self.active_check = QCheckBox("활성")
        self.active_check.setChecked(True)
        row2.addWidget(QLabel("관심사"))
        row2.addWidget(self.interests_input, 2)
        row2.addWidget(QLabel("말투"))
        row2.addWidget(self.speech_style_input)
        row2.addWidget(QLabel("톤"))
        row2.addWidget(self.tone_input)
        row2.addWidget(self.active_check)
        layout.addLayout(row2)

        self.style_input = QTextEdit()
        self.style_input.setPlaceholderText("스타일 가이드")
        self.style_input.setMaximumHeight(90)
        layout.addWidget(self.style_input)

        self.banned_input = QLineEdit()
        self.banned_input.setPlaceholderText("금칙어 (쉼표 구분)")
        layout.addWidget(self.banned_input)

        actions = QHBoxLayout()
        add_btn = QPushButton("추가")
        add_btn.clicked.connect(self.add_persona)
        save_btn = QPushButton("수정 저장")
        save_btn.clicked.connect(self.update_persona)
        delete_btn = QPushButton("삭제")
        delete_btn.clicked.connect(self.delete_persona)
        actions.addWidget(add_btn)
        actions.addWidget(save_btn)
        actions.addWidget(delete_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        box.setLayout(layout)
        root.addWidget(box, 1)
        self.setLayout(root)

    def refresh_all(self) -> None:
        rows = PersonaRepository.list_all()
        self.table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(str(item.id)))
            self.table.setItem(r, 1, QTableWidgetItem(item.name))
            self.table.setItem(r, 2, QTableWidgetItem(item.age_group or ""))
            self.table.setItem(r, 3, QTableWidgetItem(item.gender or ""))
            self.table.setItem(r, 4, QTableWidgetItem(item.personality or ""))
            self.table.setItem(r, 5, QTableWidgetItem(item.speech_style or ""))
            self.table.setItem(r, 6, QTableWidgetItem("Y" if item.is_active else "N"))

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def _fill_form(self) -> None:
        persona_id = self._selected_id()
        if persona_id is None:
            return
        row = PersonaRepository.get_by_id(persona_id)
        if not row:
            return
        self.name_input.setText(row.name)
        self.age_input.setText(row.age_group or "")
        self.gender_input.setText(row.gender or "")
        self.personality_input.setText(row.personality or "")
        self.interests_input.setText(row.interests or "")
        self.speech_style_input.setText(row.speech_style or "")
        self.tone_input.setText(row.tone or "")
        self.style_input.setPlainText(row.style_guide or "")
        self.banned_input.setText(row.banned_words or "")
        self.active_check.setChecked(row.is_active)

    def add_persona(self) -> None:
        ok = PersonaRepository.add(
            name=self.name_input.text(),
            age_group=self.age_input.text(),
            gender=self.gender_input.text(),
            personality=self.personality_input.text(),
            interests=self.interests_input.text(),
            speech_style=self.speech_style_input.text(),
            tone=self.tone_input.text(),
            style_guide=self.style_input.toPlainText(),
            banned_words=self.banned_input.text(),
        )
        if not ok:
            QMessageBox.warning(self, "실패", "페르소나 추가에 실패했습니다. (중복 또는 빈 이름)")
            return
        self.refresh_all()

    def update_persona(self) -> None:
        persona_id = self._selected_id()
        if persona_id is None:
            QMessageBox.information(self, "알림", "수정할 페르소나를 먼저 선택하세요.")
            return
        ok = PersonaRepository.update(
            persona_id=persona_id,
            name=self.name_input.text(),
            age_group=self.age_input.text(),
            gender=self.gender_input.text(),
            personality=self.personality_input.text(),
            interests=self.interests_input.text(),
            speech_style=self.speech_style_input.text(),
            tone=self.tone_input.text(),
            style_guide=self.style_input.toPlainText(),
            banned_words=self.banned_input.text(),
            is_active=self.active_check.isChecked(),
        )
        if not ok:
            QMessageBox.warning(self, "실패", "페르소나 수정에 실패했습니다.")
            return
        self.refresh_all()

    def delete_persona(self) -> None:
        persona_id = self._selected_id()
        if persona_id is None:
            QMessageBox.information(self, "알림", "삭제할 페르소나를 먼저 선택하세요.")
            return
        PersonaRepository.delete(persona_id)
        self.refresh_all()

