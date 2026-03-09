from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storage.repositories import AppSettingRepository, CategoryRepository, KeywordRepository


class KeywordPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("키워드 관리")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        splitter = QSplitter()
        splitter.addWidget(self._build_category_box())
        splitter.addWidget(self._build_keyword_side())
        splitter.setSizes([420, 980])
        root.addWidget(splitter, 1)

        self.setLayout(root)

    def _build_category_box(self) -> QGroupBox:
        box = QGroupBox("카테고리")
        layout = QVBoxLayout()

        form_row = QHBoxLayout()
        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("예: IT, 뷰티, 반려동물")
        add_btn = QPushButton("카테고리 추가")
        add_btn.clicked.connect(self.add_category)
        del_btn = QPushButton("선택 삭제")
        del_btn.clicked.connect(self.delete_selected_category)
        form_row.addWidget(self.category_input, 1)
        form_row.addWidget(add_btn)
        form_row.addWidget(del_btn)

        self.category_table = QTableWidget(0, 2)
        self.category_table.setHorizontalHeaderLabels(["ID", "카테고리"])
        self.category_table.verticalHeader().setVisible(False)
        self.category_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.category_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.category_table.setColumnWidth(0, 70)
        self.category_table.horizontalHeader().setStretchLastSection(True)
        self.category_table.itemSelectionChanged.connect(self.on_select_category)

        layout.addLayout(form_row)
        layout.addWidget(self.category_table)
        box.setLayout(layout)
        return box

    def _build_keyword_side(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(self._build_keyword_box(), 2)
        layout.addWidget(self._build_related_box(), 3)

        page.setLayout(layout)
        return page

    def _build_keyword_box(self) -> QGroupBox:
        box = QGroupBox("키워드")
        layout = QVBoxLayout()

        form = QFormLayout()
        self.keyword_category = QComboBox()
        self.keyword_category.setMinimumWidth(240)
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("예: 생성형 AI 툴")
        form.addRow("카테고리", self.keyword_category)
        form.addRow("키워드", self.keyword_input)
        layout.addLayout(form)

        action_row = QHBoxLayout()
        add_btn = QPushButton("키워드 추가")
        add_btn.clicked.connect(self.add_keyword)
        toggle_btn = QPushButton("활성/비활성 전환")
        toggle_btn.clicked.connect(self.toggle_selected_keyword)
        del_btn = QPushButton("선택 삭제")
        del_btn.clicked.connect(self.delete_selected_keyword)
        action_row.addWidget(add_btn)
        action_row.addWidget(toggle_btn)
        action_row.addWidget(del_btn)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.keyword_table = QTableWidget(0, 8)
        self.keyword_table.setHorizontalHeaderLabels(
            ["ID", "키워드", "카테고리", "활성", "총 수집횟수", "최종 수집일", "총 발행횟수", "최종 발행일"]
        )
        self.keyword_table.verticalHeader().setVisible(False)
        self.keyword_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.keyword_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.keyword_table.setColumnWidth(0, 70)
        self.keyword_table.setColumnWidth(3, 80)
        self.keyword_table.setColumnWidth(4, 100)
        self.keyword_table.setColumnWidth(5, 150)
        self.keyword_table.setColumnWidth(6, 100)
        self.keyword_table.setColumnWidth(7, 150)
        self.keyword_table.horizontalHeader().setStretchLastSection(True)
        self.keyword_table.itemSelectionChanged.connect(self.on_select_source_keyword)
        layout.addWidget(self.keyword_table, 1)

        box.setLayout(layout)
        return box

    def _build_related_box(self) -> QGroupBox:
        box = QGroupBox("연관키워드 (자동 승인)")
        layout = QVBoxLayout()

        top_row = QHBoxLayout()
        self.source_keyword_combo = QComboBox()
        top_row.addWidget(QLabel("원본 키워드"))
        top_row.addWidget(self.source_keyword_combo, 1)
        self.related_limit_label = QLabel("현재 상한: -")
        self.related_limit_label.setStyleSheet("color: #666;")
        top_row.addWidget(self.related_limit_label)
        reload_btn = QPushButton("조회")
        reload_btn.clicked.connect(self.refresh_related_section)
        top_row.addWidget(reload_btn)
        layout.addLayout(top_row)

        self.related_table = QTableWidget(0, 7)
        self.related_table.setHorizontalHeaderLabels(["연결ID", "연관 키워드", "소스", "활성", "반영횟수", "최종반영일", "연관키워드ID"])
        self.related_table.verticalHeader().setVisible(False)
        self.related_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.related_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.related_table.setColumnWidth(0, 70)
        self.related_table.setColumnWidth(1, 220)
        self.related_table.setColumnWidth(2, 140)
        self.related_table.setColumnWidth(3, 80)
        self.related_table.setColumnWidth(4, 90)
        self.related_table.setColumnWidth(5, 150)
        self.related_table.setColumnHidden(6, True)
        self.related_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(QLabel("연관키워드 목록"))
        layout.addWidget(self.related_table, 1)

        action_row = QHBoxLayout()
        toggle_btn = QPushButton("선택 연관키워드 활성/비활성")
        toggle_btn.clicked.connect(self.toggle_selected_related_keyword)
        action_row.addWidget(toggle_btn)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        box.setLayout(layout)
        return box

    def refresh_all(self) -> None:
        self.refresh_categories()
        self.refresh_keywords()
        self.refresh_source_keyword_combo()
        self.refresh_related_limit_label()
        self.refresh_related_section()

    def refresh_categories(self) -> None:
        categories = CategoryRepository.list_all()
        selected_category_id = self.keyword_category.currentData()

        self.category_table.setRowCount(len(categories))
        self.keyword_category.clear()
        self.keyword_category.addItem("카테고리 선택", None)

        for row, category in enumerate(categories):
            self.category_table.setItem(row, 0, QTableWidgetItem(str(category.id)))
            self.category_table.setItem(row, 1, QTableWidgetItem(category.name))
            self.keyword_category.addItem(category.name, category.id)

        if selected_category_id is not None:
            idx = self.keyword_category.findData(selected_category_id)
            if idx >= 0:
                self.keyword_category.setCurrentIndex(idx)

    def refresh_keywords(self) -> None:
        keywords = KeywordRepository.list_all()
        self.keyword_table.setRowCount(len(keywords))
        for row, keyword in enumerate(keywords):
            self.keyword_table.setItem(row, 0, QTableWidgetItem(str(keyword.id)))
            self.keyword_table.setItem(row, 1, QTableWidgetItem(keyword.keyword))
            self.keyword_table.setItem(row, 2, QTableWidgetItem(keyword.category_name or "-"))
            active_item = QTableWidgetItem("Y" if keyword.is_active else "N")
            active_item.setTextAlignment(Qt.AlignCenter)
            self.keyword_table.setItem(row, 3, active_item)
            self.keyword_table.setItem(row, 4, QTableWidgetItem(str(keyword.total_collected_count)))
            self.keyword_table.setItem(
                row,
                5,
                QTableWidgetItem(keyword.last_collected_at.strftime("%Y-%m-%d %H:%M:%S") if keyword.last_collected_at else "-"),
            )
            self.keyword_table.setItem(row, 6, QTableWidgetItem(str(keyword.total_published_count)))
            self.keyword_table.setItem(
                row,
                7,
                QTableWidgetItem(keyword.last_published_at.strftime("%Y-%m-%d %H:%M:%S") if keyword.last_published_at else "-"),
            )

    def refresh_source_keyword_combo(self) -> None:
        selected = self.source_keyword_combo.currentData()
        self.source_keyword_combo.clear()
        rows = KeywordRepository.list_all()
        for row in rows:
            self.source_keyword_combo.addItem(row.keyword, row.id)
        if selected is not None:
            idx = self.source_keyword_combo.findData(selected)
            if idx >= 0:
                self.source_keyword_combo.setCurrentIndex(idx)

    def refresh_related_limit_label(self) -> None:
        limit = AppSettingRepository.get_related_keyword_limit(10)
        self.related_limit_label.setText(f"현재 상한: {limit}개")

    def refresh_related_section(self) -> None:
        self.refresh_related_keywords()

    def refresh_related_keywords(self) -> None:
        source_keyword_id = self.source_keyword_combo.currentData()
        if source_keyword_id is None:
            self.related_table.setRowCount(0)
            return
        rows = KeywordRepository.list_related_keywords(int(source_keyword_id))
        self.related_table.setRowCount(len(rows))
        for i, item in enumerate(rows):
            self.related_table.setItem(i, 0, QTableWidgetItem(str(item.relation_id)))
            self.related_table.setItem(i, 1, QTableWidgetItem(item.related_keyword))
            self.related_table.setItem(i, 2, QTableWidgetItem(item.source_type))
            active_item = QTableWidgetItem("Y" if item.is_active else "N")
            active_item.setTextAlignment(Qt.AlignCenter)
            self.related_table.setItem(i, 3, active_item)
            self.related_table.setItem(i, 4, QTableWidgetItem(str(item.collect_count)))
            self.related_table.setItem(i, 5, QTableWidgetItem(item.last_seen_at.strftime("%Y-%m-%d %H:%M:%S")))
            self.related_table.setItem(i, 6, QTableWidgetItem(str(item.related_keyword_id)))

    def _selected_row_id(self, table: QTableWidget) -> int | None:
        row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, 0)
        if not item:
            return None
        return int(item.text())

    def on_select_category(self) -> None:
        category_id = self._selected_row_id(self.category_table)
        if category_id is None:
            return
        idx = self.keyword_category.findData(category_id)
        if idx >= 0:
            self.keyword_category.setCurrentIndex(idx)

    def on_select_source_keyword(self) -> None:
        keyword_id = self._selected_row_id(self.keyword_table)
        if keyword_id is None:
            return
        idx = self.source_keyword_combo.findData(keyword_id)
        if idx >= 0:
            self.source_keyword_combo.setCurrentIndex(idx)
            self.refresh_related_section()

    def add_category(self) -> None:
        if not CategoryRepository.add(self.category_input.text()):
            QMessageBox.warning(self, "알림", "카테고리를 확인하세요. (빈 값 또는 중복)")
            return
        self.category_input.clear()
        self.refresh_categories()

    def delete_selected_category(self) -> None:
        category_id = self._selected_row_id(self.category_table)
        if category_id is None:
            QMessageBox.information(self, "알림", "삭제할 카테고리를 선택하세요.")
            return
        CategoryRepository.delete(category_id)
        self.refresh_all()

    def add_keyword(self) -> None:
        category_id = self.keyword_category.currentData()
        if category_id is None:
            QMessageBox.warning(self, "알림", "키워드 등록 전 카테고리를 먼저 선택하세요.")
            return
        if not KeywordRepository.add(self.keyword_input.text(), category_id, is_auto_generated=False):
            QMessageBox.warning(self, "알림", "키워드를 확인하세요. (빈 값 또는 중복)")
            return
        self.keyword_input.clear()
        self.refresh_keywords()
        self.refresh_source_keyword_combo()

    def delete_selected_keyword(self) -> None:
        keyword_id = self._selected_row_id(self.keyword_table)
        if keyword_id is None:
            QMessageBox.information(self, "알림", "삭제할 키워드를 선택하세요.")
            return
        KeywordRepository.delete(keyword_id)
        self.refresh_keywords()
        self.refresh_source_keyword_combo()
        self.refresh_related_section()

    def toggle_selected_keyword(self) -> None:
        keyword_id = self._selected_row_id(self.keyword_table)
        if keyword_id is None:
            QMessageBox.information(self, "알림", "키워드를 선택하세요.")
            return
        KeywordRepository.toggle(keyword_id)
        self.refresh_keywords()

    def toggle_selected_related_keyword(self) -> None:
        row = self.related_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "알림", "연관키워드를 선택하세요.")
            return
        related_id_item = self.related_table.item(row, 6)
        if not related_id_item:
            QMessageBox.warning(self, "알림", "연관키워드 ID를 찾을 수 없습니다.")
            return
        related_keyword_id = int(related_id_item.text())
        KeywordRepository.toggle(related_keyword_id)
        self.refresh_related_section()
        QMessageBox.information(self, "완료", "연관키워드 활성 상태가 변경되었습니다.")

