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
    QVBoxLayout,
    QWidget,
)

from storage.repositories import AIProviderRepository


class AIProviderPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("AI API 관리")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        box = QGroupBox("AI Provider 목록")
        layout = QVBoxLayout()

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["ID", "Provider", "Model", "유무료", "활성", "우선순위", "상태", "Key Alias"])
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(4, 70)
        self.table.setColumnWidth(5, 80)
        self.table.setColumnWidth(6, 90)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._fill_form)
        layout.addWidget(self.table)

        row1 = QHBoxLayout()
        self.provider_input = QLineEdit()
        self.provider_input.setPlaceholderText("provider (openai/google)")
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("model name")
        self.key_alias_input = QLineEdit()
        self.key_alias_input.setPlaceholderText("API key alias")
        row1.addWidget(QLabel("Provider"))
        row1.addWidget(self.provider_input)
        row1.addWidget(QLabel("Model"))
        row1.addWidget(self.model_input, 1)
        row1.addWidget(QLabel("Key Alias"))
        row1.addWidget(self.key_alias_input)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.is_paid = QCheckBox("유료")
        self.is_enabled = QCheckBox("활성")
        self.is_enabled.setChecked(True)
        self.priority = QSpinBox()
        self.priority.setRange(1, 999)
        self.priority.setValue(1)
        self.rpm = QSpinBox()
        self.rpm.setRange(0, 5000)
        self.rpm.setValue(60)
        self.daily_budget = QSpinBox()
        self.daily_budget.setRange(0, 1000000)
        self.daily_budget.setValue(100)
        self.status = QComboBox()
        self.status.addItems(["ready", "error", "blocked", "unknown"])
        row2.addWidget(self.is_paid)
        row2.addWidget(self.is_enabled)
        row2.addWidget(QLabel("우선순위"))
        row2.addWidget(self.priority)
        row2.addWidget(QLabel("RPM"))
        row2.addWidget(self.rpm)
        row2.addWidget(QLabel("일예산"))
        row2.addWidget(self.daily_budget)
        row2.addWidget(QLabel("상태"))
        row2.addWidget(self.status)
        layout.addLayout(row2)

        actions = QHBoxLayout()
        add_btn = QPushButton("추가")
        add_btn.clicked.connect(self.add_provider)
        save_btn = QPushButton("수정 저장")
        save_btn.clicked.connect(self.update_provider)
        delete_btn = QPushButton("삭제")
        delete_btn.clicked.connect(self.delete_provider)
        actions.addWidget(add_btn)
        actions.addWidget(save_btn)
        actions.addWidget(delete_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        box.setLayout(layout)
        root.addWidget(box, 1)
        self.setLayout(root)

    def refresh_all(self) -> None:
        rows = AIProviderRepository.list_all()
        self.table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(str(item.id)))
            self.table.setItem(r, 1, QTableWidgetItem(item.provider))
            self.table.setItem(r, 2, QTableWidgetItem(item.model_name))
            self.table.setItem(r, 3, QTableWidgetItem("유료" if item.is_paid else "무료"))
            self.table.setItem(r, 4, QTableWidgetItem("Y" if item.is_enabled else "N"))
            self.table.setItem(r, 5, QTableWidgetItem(str(item.priority)))
            self.table.setItem(r, 6, QTableWidgetItem(item.status))
            self.table.setItem(r, 7, QTableWidgetItem(item.api_key_alias or ""))

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def _fill_form(self) -> None:
        provider_id = self._selected_id()
        if provider_id is None:
            return
        row = AIProviderRepository.get_by_id(provider_id)
        if not row:
            return
        self.provider_input.setText(row.provider)
        self.model_input.setText(row.model_name)
        self.key_alias_input.setText(row.api_key_alias or "")
        self.is_paid.setChecked(row.is_paid)
        self.is_enabled.setChecked(row.is_enabled)
        self.priority.setValue(max(1, row.priority))
        self.rpm.setValue(max(0, row.rate_limit_per_min or 0))
        self.daily_budget.setValue(max(0, row.daily_budget_limit or 0))
        idx = self.status.findText(row.status)
        if idx >= 0:
            self.status.setCurrentIndex(idx)

    def add_provider(self) -> None:
        ok = AIProviderRepository.add(
            provider=self.provider_input.text(),
            model_name=self.model_input.text(),
            api_key_alias=self.key_alias_input.text(),
            is_paid=self.is_paid.isChecked(),
            priority=self.priority.value(),
            rate_limit_per_min=self.rpm.value() or None,
            daily_budget_limit=self.daily_budget.value() or None,
            status=self.status.currentText(),
        )
        if not ok:
            QMessageBox.warning(self, "실패", "AI Provider 추가에 실패했습니다.")
            return
        self.refresh_all()

    def update_provider(self) -> None:
        provider_id = self._selected_id()
        if provider_id is None:
            QMessageBox.information(self, "알림", "수정할 항목을 먼저 선택하세요.")
            return
        ok = AIProviderRepository.update(
            provider_id=provider_id,
            provider=self.provider_input.text(),
            model_name=self.model_input.text(),
            api_key_alias=self.key_alias_input.text(),
            is_paid=self.is_paid.isChecked(),
            is_enabled=self.is_enabled.isChecked(),
            priority=self.priority.value(),
            rate_limit_per_min=self.rpm.value() or None,
            daily_budget_limit=self.daily_budget.value() or None,
            status=self.status.currentText(),
        )
        if not ok:
            QMessageBox.warning(self, "실패", "AI Provider 수정에 실패했습니다.")
            return
        self.refresh_all()

    def delete_provider(self) -> None:
        provider_id = self._selected_id()
        if provider_id is None:
            QMessageBox.information(self, "알림", "삭제할 항목을 먼저 선택하세요.")
            return
        AIProviderRepository.delete(provider_id)
        self.refresh_all()

