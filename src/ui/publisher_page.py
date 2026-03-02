from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from publisher import publisher_service
from storage.repositories import ArticleRepository, PublishChannelRepository, PublishRepository


class PublisherPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("발행 관리")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        controls = QGroupBox("반자동/자동 발행")
        controls_layout = QHBoxLayout()
        self.channel_combo = QComboBox()
        self._refresh_channel_combo()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("반자동", "semi_auto")
        self.mode_combo.addItem("자동", "auto")
        enqueue_btn = QPushButton("선택 글 발행 큐 등록")
        enqueue_btn.clicked.connect(self.enqueue_selected_article)
        run_btn = QPushButton("선택 작업 즉시 처리")
        run_btn.clicked.connect(self.process_selected_job)
        controls_layout.addWidget(QLabel("채널"))
        controls_layout.addWidget(self.channel_combo)
        controls_layout.addWidget(QLabel("모드"))
        controls_layout.addWidget(self.mode_combo)
        controls_layout.addWidget(enqueue_btn)
        controls_layout.addWidget(run_btn)
        controls_layout.addStretch(1)
        controls.setLayout(controls_layout)
        root.addWidget(controls)

        article_box = QGroupBox("최근 생성 글")
        article_layout = QVBoxLayout()
        self.article_table = QTableWidget(0, 4)
        self.article_table.setHorizontalHeaderLabels(["ID", "형식", "상태", "제목"])
        self.article_table.verticalHeader().setVisible(False)
        self.article_table.setColumnWidth(0, 60)
        self.article_table.setColumnWidth(1, 80)
        self.article_table.setColumnWidth(2, 80)
        self.article_table.horizontalHeader().setStretchLastSection(True)
        article_layout.addWidget(self.article_table)
        article_box.setLayout(article_layout)
        root.addWidget(article_box, 1)

        job_box = QGroupBox("발행 작업")
        job_layout = QVBoxLayout()
        self.job_table = QTableWidget(0, 7)
        self.job_table.setHorizontalHeaderLabels(["ID", "글ID", "채널", "모드", "상태", "메시지", "생성시각"])
        self.job_table.verticalHeader().setVisible(False)
        self.job_table.setColumnWidth(0, 50)
        self.job_table.setColumnWidth(1, 50)
        self.job_table.setColumnWidth(2, 90)
        self.job_table.setColumnWidth(3, 80)
        self.job_table.setColumnWidth(4, 80)
        self.job_table.setColumnWidth(5, 230)
        self.job_table.horizontalHeader().setStretchLastSection(True)
        job_layout.addWidget(self.job_table)
        job_box.setLayout(job_layout)
        root.addWidget(job_box, 1)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        root.addWidget(self.log_view, 1)

        self.setLayout(root)

    def refresh_all(self) -> None:
        self._refresh_channel_combo()
        self.refresh_articles()
        self.refresh_jobs()

    def refresh_articles(self) -> None:
        rows = ArticleRepository.list_recent(100)
        self.article_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            self.article_table.setItem(row, 0, QTableWidgetItem(str(item.id)))
            self.article_table.setItem(row, 1, QTableWidgetItem(item.format_type))
            self.article_table.setItem(row, 2, QTableWidgetItem(item.status))
            self.article_table.setItem(row, 3, QTableWidgetItem(item.title))

    def refresh_jobs(self) -> None:
        rows = PublishRepository.list_recent(100)
        self.job_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            self.job_table.setItem(row, 0, QTableWidgetItem(str(item.id)))
            self.job_table.setItem(row, 1, QTableWidgetItem(str(item.article_id)))
            self.job_table.setItem(row, 2, QTableWidgetItem(item.target_channel))
            self.job_table.setItem(row, 3, QTableWidgetItem(item.mode))
            self.job_table.setItem(row, 4, QTableWidgetItem(item.status))
            self.job_table.setItem(row, 5, QTableWidgetItem(item.message or ""))
            self.job_table.setItem(row, 6, QTableWidgetItem(item.created_at.strftime("%Y-%m-%d %H:%M:%S")))

    def _refresh_channel_combo(self) -> None:
        self.channel_combo.clear()
        channels = PublishChannelRepository.list_enabled()
        for channel in channels:
            self.channel_combo.addItem(channel.display_name, channel.code)

    def _selected_article_id(self) -> int | None:
        row = self.article_table.currentRow()
        if row < 0:
            return None
        item = self.article_table.item(row, 0)
        return int(item.text()) if item else None

    def _selected_job_id(self) -> int | None:
        row = self.job_table.currentRow()
        if row < 0:
            return None
        item = self.job_table.item(row, 0)
        return int(item.text()) if item else None

    def enqueue_selected_article(self) -> None:
        article_id = self._selected_article_id()
        if article_id is None:
            QMessageBox.information(self, "알림", "발행할 글을 선택하세요.")
            return
        job_id = publisher_service.enqueue_publish(
            article_id=article_id,
            target_channel=self.channel_combo.currentData(),
            mode=self.mode_combo.currentData(),
        )
        self.log_view.append(f"발행 큐 등록: job_id={job_id}")
        self.refresh_all()

    def process_selected_job(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            QMessageBox.information(self, "알림", "처리할 작업을 선택하세요.")
            return
        result = publisher_service.process_job(job_id)
        self.log_view.append(f"작업 {job_id}: {result}")
        self.refresh_jobs()

