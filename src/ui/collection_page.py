from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from collector.service import crawl_service
from storage.repositories import (
    CrawlRepository,
    KeywordRepository,
    SourceChannelRepository,
)


class CollectionPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("수집 실행 / 채널 관리")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        top = QGridLayout()
        top.addWidget(self._build_channel_box(), 0, 0)
        top.addWidget(self._build_run_box(), 0, 1)
        root.addLayout(top)

        root.addWidget(self._build_job_box(), 2)
        root.addWidget(self._build_content_box(), 2)
        root.addWidget(self._build_log_box(), 1)
        self.setLayout(root)

    def _build_channel_box(self) -> QGroupBox:
        box = QGroupBox("채널")
        layout = QVBoxLayout()
        self.channel_table = QTableWidget(0, 4)
        self.channel_table.setHorizontalHeaderLabels(["ID", "코드", "이름", "활성"])
        self.channel_table.verticalHeader().setVisible(False)
        self.channel_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.channel_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.channel_table.setColumnWidth(0, 60)
        self.channel_table.setColumnWidth(1, 140)
        self.channel_table.horizontalHeader().setStretchLastSection(True)

        btn_row = QHBoxLayout()
        toggle_btn = QPushButton("활성/비활성 전환")
        toggle_btn.clicked.connect(self.toggle_channel)
        btn_row.addWidget(toggle_btn)
        btn_row.addStretch(1)

        layout.addWidget(self.channel_table)
        layout.addLayout(btn_row)
        box.setLayout(layout)
        return box

    def _build_run_box(self) -> QGroupBox:
        box = QGroupBox("수집 실행")
        layout = QVBoxLayout()

        self.keyword_combo = QComboBox()
        self.max_results = QSpinBox()
        self.max_results.setRange(1, 20)
        self.max_results.setValue(3)

        layout.addWidget(QLabel("키워드"))
        layout.addWidget(self.keyword_combo)
        layout.addWidget(QLabel("채널별 최대 수집 건수"))
        layout.addWidget(self.max_results)

        run_btn = QPushButton("수집 실행")
        run_btn.clicked.connect(self.run_collect)
        layout.addWidget(run_btn)
        layout.addStretch(1)

        box.setLayout(layout)
        return box

    def _build_job_box(self) -> QGroupBox:
        box = QGroupBox("최근 수집 작업")
        layout = QVBoxLayout()
        self.job_table = QTableWidget(0, 6)
        self.job_table.setHorizontalHeaderLabels(["ID", "키워드", "채널", "상태", "수집", "생성시각"])
        self.job_table.verticalHeader().setVisible(False)
        self.job_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.job_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.job_table.setColumnWidth(0, 60)
        self.job_table.setColumnWidth(3, 90)
        self.job_table.setColumnWidth(4, 70)
        self.job_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.job_table)
        box.setLayout(layout)
        return box

    def _build_log_box(self) -> QGroupBox:
        box = QGroupBox("실행 로그")
        layout = QVBoxLayout()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        box.setLayout(layout)
        return box

    def _build_content_box(self) -> QGroupBox:
        box = QGroupBox("최근 수집 원문")
        layout = QVBoxLayout()
        self.content_table = QTableWidget(0, 5)
        self.content_table.setHorizontalHeaderLabels(["ID", "키워드", "채널", "제목", "생성시각"])
        self.content_table.verticalHeader().setVisible(False)
        self.content_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.content_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.content_table.setColumnWidth(0, 60)
        self.content_table.setColumnWidth(1, 150)
        self.content_table.setColumnWidth(2, 110)
        self.content_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.content_table)
        box.setLayout(layout)
        return box

    def refresh_all(self) -> None:
        self.refresh_channels()
        self.refresh_keywords()
        self.refresh_jobs()
        self.refresh_contents()

    def refresh_channels(self) -> None:
        channels = SourceChannelRepository.list_all()
        self.channel_table.setRowCount(len(channels))
        for row, channel in enumerate(channels):
            self.channel_table.setItem(row, 0, QTableWidgetItem(str(channel.id)))
            self.channel_table.setItem(row, 1, QTableWidgetItem(channel.code))
            self.channel_table.setItem(row, 2, QTableWidgetItem(channel.display_name))
            self.channel_table.setItem(row, 3, QTableWidgetItem("Y" if channel.is_enabled else "N"))

    def refresh_keywords(self) -> None:
        keywords = KeywordRepository.list_active()
        self.keyword_combo.clear()
        for keyword in keywords:
            label = keyword.keyword if not keyword.category_name else f"[{keyword.category_name}] {keyword.keyword}"
            self.keyword_combo.addItem(label, keyword.id)

    def refresh_jobs(self) -> None:
        jobs = CrawlRepository.list_recent_jobs(100)
        self.job_table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            self.job_table.setItem(row, 0, QTableWidgetItem(str(job.id)))
            self.job_table.setItem(row, 1, QTableWidgetItem(job.keyword))
            self.job_table.setItem(row, 2, QTableWidgetItem(job.channel_code))
            self.job_table.setItem(row, 3, QTableWidgetItem(job.status))
            self.job_table.setItem(row, 4, QTableWidgetItem(str(job.collected_count)))
            self.job_table.setItem(row, 5, QTableWidgetItem(job.created_at.strftime("%Y-%m-%d %H:%M:%S")))

    def refresh_contents(self) -> None:
        rows = CrawlRepository.list_recent_contents(100)
        self.content_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            self.content_table.setItem(row, 0, QTableWidgetItem(str(item.id)))
            self.content_table.setItem(row, 1, QTableWidgetItem(item.keyword or "-"))
            self.content_table.setItem(row, 2, QTableWidgetItem(item.channel_code))
            self.content_table.setItem(row, 3, QTableWidgetItem(item.title))
            self.content_table.setItem(row, 4, QTableWidgetItem(item.created_at.strftime("%Y-%m-%d %H:%M:%S")))

    def _selected_channel_id(self) -> int | None:
        row = self.channel_table.currentRow()
        if row < 0:
            return None
        item = self.channel_table.item(row, 0)
        if not item:
            return None
        return int(item.text())

    def toggle_channel(self) -> None:
        channel_id = self._selected_channel_id()
        if channel_id is None:
            QMessageBox.information(self, "알림", "채널을 선택하세요.")
            return
        SourceChannelRepository.toggle(channel_id)
        self.refresh_channels()

    def run_collect(self) -> None:
        keyword_id = self.keyword_combo.currentData()
        if keyword_id is None:
            QMessageBox.warning(self, "알림", "활성 키워드가 없습니다.")
            return
        messages = crawl_service.run_for_keyword(keyword_id=keyword_id, max_results=self.max_results.value())
        for message in messages:
            self.log_view.append(message)
        self.refresh_jobs()
        self.refresh_contents()

